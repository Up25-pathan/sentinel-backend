const express = require('express');
const cors = require('cors');
const http = require('http');
const morgan = require('morgan');
const helmet = require('helmet');
const { WebSocketServer } = require('ws');

// Loads server/.env regardless of process CWD, and validates it.
const { validateEnv, resolveJwtSecret, configStatus } = require('./env');
validateEnv();

const { getDb, closeDb } = require('./db');
const { authMiddleware, apiKeyMiddleware, requireAdminRole, securityHeaders } = require('./middleware/auth');
const { startScheduler } = require('./scheduler');
const { startBroadcaster, stopBroadcaster, broadcasterStatus } = require('./broadcaster');
const { sourceHealth } = require('./services/source-health');
const { clampDays } = require('./lib/query');
const eventBus = require('./eventbus');

const authRoutes = require('./routes/auth');
const eventRoutes = require('./routes/events');
const alertRoutes = require('./routes/alerts');
const mapRoutes = require('./routes/map');
const watchlistsRoutes = require('./routes/watchlists');
const intelligenceRoutes = require('./routes/intelligence');
const osintRoutes = require('./routes/osint');
const darkwebRoutes = require('./routes/darkweb');
const auditRoutes = require('./routes/audit');
const assetRoutes = require('./routes/assets');
const { logAction } = require('./services/audit-log');

const rateLimit = require('express-rate-limit');

const app = express();
const PORT = process.env.PORT || 3001;
app.set('trust proxy', 1);

// ─── Rate Limiting ─────────────────────────────────────────────
const generalLimiter = rateLimit({
    windowMs: 60 * 1000,
    // 120/min was below what a single authenticated desktop client uses on a
    // normal pass: dashboard 2/min + health 2/min + audit + several panels, all
    // of which can land in the same window on a cold start. That produced 429s
    // that the UI reported as a broken feed. This is still far below abuse.
    max: 600,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many requests, please try again later.' }
});

// Map and intelligence routes get their own allowance. Every route shares the
// general limiter, so one panel's polling previously starved the rest — the map
// returned 429 for all three of its layers while the dashboard looked healthy.
const dataLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 90,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Data feed rate limit reached, please retry shortly.' }
});

const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 20,
    standardHeaders: true,
    legacyHeaders: false,
    // A successful login must not consume the budget. Otherwise the desktop
    // app — which authenticates once per launch — burns attempts and locks
    // itself out of its own server after a handful of restarts.
    skipSuccessfulRequests: true,
    message: { error: 'Too many login attempts. Try again in 15 minutes.' }
});

// ─── Global Middleware ──────────────────────────────────────────
// Registered BEFORE any route so that every response — including the public
// health check — receives security headers and rate limiting. Previously these
// were registered after five data-bearing routes, leaving /api/events/stream,
// /api/map/conflicts, /api/map/aviation, /api/auth/check and /api/health with
// no auth, no API key and no rate limit at all.
app.disable('x-powered-by');
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(morgan('combined'));
app.use(securityHeaders);
app.use(generalLimiter);
app.use(apiKeyMiddleware);

// ─── SSE Clients ────────────────────────────────────────────────
const sseClients = new Set();

function broadcastSSE(event, data) {
    const msg = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    for (const client of sseClients) {
        try { client.write(msg); } catch (e) { sseClients.delete(client); }
    }
}

// ─── Health Check (public — no auth, for load balancers) ───────
app.get('/api/health', (req, res) => {
    const db = getDb();
    const eventCount = db.prepare('SELECT COUNT(*) as count FROM events').get();
    const alertCount = db.prepare('SELECT COUNT(*) as count FROM alerts WHERE is_read = 0').get();

    res.json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        events: eventCount.count,
        unread_alerts: alertCount.count,
        broadcaster: broadcasterStatus(),
        sources: sourceHealth(),
        version: '1.0.0'
    });
});

app.get('/', (req, res) => {
    res.json({ service: 'SENTINEL API', health: '/api/health' });
});

// ─── SSE Stream (JWT required) ──────────────────────────────────
app.get('/api/events/stream', authMiddleware, (req, res) => {
    res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
    });

    res.write(`data: ${JSON.stringify({ type: 'connected', timestamp: new Date().toISOString() })}\n\n`);

    sseClients.add(res);

    // Heartbeat: proxies and load balancers drop idle connections, and a dead
    // broadcaster is otherwise indistinguishable from a healthy idle stream.
    const keepalive = setInterval(() => {
        try {
            res.write(': keepalive\n\n');
        } catch (e) {
            sseClients.delete(res);
            clearInterval(keepalive);
        }
    }, 15000);

    req.on('close', () => {
        sseClients.delete(res);
        clearInterval(keepalive);
    });
});

// ─── Conflict Zones (JWT required — proxies GDELT) ──────────────
let conflictCache = { data: null, time: 0 };
const GDELT_GEO_URL = 'https://api.gdeltproject.org/api/v2/geo/geo?query=conflict%20OR%20violence%20OR%20war&format=geojson&timespan=14d';

app.get('/api/map/conflicts', authMiddleware, async (req, res) => {
    const CACHE_TTL = 120000;
    if (Date.now() - conflictCache.time < CACHE_TTL && conflictCache.data) {
        return res.json(conflictCache.data);
    }
    try {
        const resp = await fetch(GDELT_GEO_URL, { signal: AbortSignal.timeout(8000) });
        if (!resp.ok) throw new Error(`GDELT request failed (HTTP ${resp.status})`);
        const raw = await resp.json();
        const features = (raw.features || []).filter(f => {
            const coords = f.geometry && f.geometry.coordinates;
            return f.geometry && f.geometry.type === 'Point' && Array.isArray(coords)
                && Number.isFinite(coords[0]) && Number.isFinite(coords[1]);
        }).map(f => {
            const properties = f.properties || {};
            const articles = Number(properties.NumArticles) || 0;
            return {
                name: properties.Name || properties.Actor1Name || properties.Actor2Name || 'Unknown',
                label: properties.EventCode || 'Conflict Event',
                lat: f.geometry.coordinates[1],
                lng: f.geometry.coordinates[0],
                article_count: articles,
                source: 'GDELT',
                url: properties.SOURCEURL || '',
            };
        });
        const result = { zones: [], events: features, count: features.length };
        conflictCache = { data: result, time: Date.now() };
        res.json(result);
    } catch (err) {
        if (conflictCache.data) {
            res.json({ ...conflictCache.data, stale: true, error: 'GDELT feed unavailable; showing cached data' });
        } else {
            res.json({ zones: [], events: [], count: 0, error: 'GDELT feed unavailable' });
        }
    }
});

// ─── Aviation Data (JWT required — proxies OpenSky) ─────────────
let aviationCache = { data: null, time: 0 };
let aviationFailureCache = { data: null, time: 0 };
const AVIATION_FAILURE_CACHE_TTL = 20000;
const OPENSKY_CLIENT_ID = process.env.OPENSKY_CLIENT_ID || '';
const OPENSKY_CLIENT_SECRET = process.env.OPENSKY_CLIENT_SECRET || '';
const OPENSKY_TOKEN_URL = 'https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token';
const OPENSKY_URL = 'https://opensky-network.org/api/states/all';
const ADSB_LOL_ENDPOINTS = [
    { url: 'https://api.adsb.lol/v2/lat/0/0/dist/250', label: 'adsb.lol/global' },
    { url: 'https://api.adsb.lol/v2/mil', label: 'adsb.lol/mil' },
];
// adsb.lol answers 403 to Node's default undici User-Agent, so every upstream
// call identifies itself explicitly.
const UPSTREAM_HEADERS = { 'User-Agent': 'SENTINEL/1.0 (geopolitical-intelligence)' };
const OPENSKY_RETRY_MS = 10 * 60 * 1000;
let openSkyBlockedUntil = 0;
let openSkyToken = null;
let openSkyTokenExpiresAt = 0;
let openSkyTokenRequest = null;

async function getOpenSkyAccessToken() {
    if (!OPENSKY_CLIENT_ID || !OPENSKY_CLIENT_SECRET) return null;
    if (openSkyToken && Date.now() < openSkyTokenExpiresAt) return openSkyToken;
    if (!openSkyTokenRequest) {
        openSkyTokenRequest = (async () => {
            const response = await fetch(OPENSKY_TOKEN_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({
                    grant_type: 'client_credentials',
                    client_id: OPENSKY_CLIENT_ID,
                    client_secret: OPENSKY_CLIENT_SECRET,
                }),
                signal: AbortSignal.timeout(30000),
            });
            if (!response.ok) {
                const error = new Error(`OpenSky token request failed (HTTP ${response.status})`);
                error.status = response.status;
                throw error;
            }
            const data = await response.json();
            if (!data.access_token) throw new Error('OpenSky token response had no access token');
            openSkyToken = data.access_token;
            openSkyTokenExpiresAt = Date.now() + Math.max(0, (Number(data.expires_in) || 1800) - 30) * 1000;
            return openSkyToken;
        })().finally(() => {
            openSkyTokenRequest = null;
        });
    }
    return openSkyTokenRequest;
}

function normaliseAdsbLol(raw) {
    return (raw.ac || []).filter(a => a.lat != null && a.lon != null).map(a => ({
        icao24: a.icao24 || a.hex || '',
        callsign: (a.flight || '').trim(),
        origin_country: a.country_iso_name || '',
        lat: a.lat,
        lng: a.lon,
        // adsb.lol reports feet and knots. OpenSky reports metres and m/s, and
        // the map converts using those units, so convert here to keep one
        // contract and avoid altitudes that are 3x too high and speeds 2x off.
        // alt_baro is the string "ground" for aircraft on the ground, which
        // must not be coerced into NaN.
        altitude: Number.isFinite(a.alt_baro) ? a.alt_baro / 3.28084 : null,
        velocity: Number.isFinite(a.gs) ? a.gs / 1.94384 : null,
        heading: a.true_heading != null ? a.true_heading : (a.track != null ? a.track : null),
    }));
}

async function fetchAircraftFromAdsbLol() {
    const failures = [];
    for (const endpoint of ADSB_LOL_ENDPOINTS) {
        try {
            const resp = await fetch(endpoint.url, {
                signal: AbortSignal.timeout(15000),
                headers: { ...UPSTREAM_HEADERS },
            });
            if (!resp.ok) {
                failures.push(`${endpoint.label}[upstream HTTP ${resp.status}]`);
                continue;
            }
            const states = normaliseAdsbLol(await resp.json());
            if (!states.length) {
                failures.push(`${endpoint.label}[0 aircraft with position]`);
                continue;
            }
            return {
                aircraft: states,
                count: states.length,
                source: endpoint.label,
                timestamp: new Date().toISOString(),
            };
        } catch (err) {
            failures.push(`${endpoint.label}[${aviationDiagnostic(err)}]`);
        }
    }
    throw new Error(failures.join(' '));
}

function aviationDiagnostic(err) {
    const parts = [];
    if (err.status) parts.push('upstream HTTP ' + err.status);
    if (err.name && err.name !== 'Error') parts.push('name=' + err.name);
    let cause = err.cause;
    let depth = 0;
    while (cause && depth < 3) {
        if (cause.code) parts.push('cause=' + cause.code);
        else if (cause.message) parts.push('cause=' + String(cause.message).slice(0, 60));
        cause = cause.cause;
        depth++;
    }
    return parts.join(' ') || 'unknown';
}

app.get('/api/map/aviation', authMiddleware, async (req, res) => {
    const CACHE_TTL = 120000;
    if (Date.now() - aviationCache.time < CACHE_TTL && aviationCache.data) {
        return res.json(aviationCache.data);
    }
    if (Date.now() - aviationFailureCache.time < AVIATION_FAILURE_CACHE_TTL && aviationFailureCache.data) {
        return res.json(aviationFailureCache.data);
    }
    const primaryFailures = [];
    // When OpenSky is unreachable it costs ~11s of connect timeout per call, so
    // it is skipped for a cooldown rather than retried on every poll.
    if (Date.now() < openSkyBlockedUntil) {
        primaryFailures.push(`opensky[skipped, backoff for ${Math.ceil((openSkyBlockedUntil - Date.now()) / 60000)}m]`);
    } else {
    try {
        const opts = { signal: AbortSignal.timeout(30000), headers: { ...UPSTREAM_HEADERS } };
        const accessToken = await getOpenSkyAccessToken();
        if (accessToken) opts.headers = { ...UPSTREAM_HEADERS, 'Authorization': `Bearer ${accessToken}` };
        const resp = await fetch(OPENSKY_URL, opts);
        if (!resp.ok) {
            const error = new Error(`OpenSky API request failed (HTTP ${resp.status})`);
            error.status = resp.status;
            throw error;
        }
        const raw = await resp.json();
        const states = (raw.states || []).filter(s => s[5] && s[6]).map(s => ({
            icao24: s[0],
            callsign: (s[1] || '').trim(),
            origin_country: s[2],
            lat: s[6],
            lng: s[5],
            altitude: s[7],
            velocity: s[9],
            heading: s[10],
        }));
        const result = { aircraft: states, count: states.length, source: 'opensky', timestamp: new Date().toISOString() };
        aviationCache = { data: result, time: Date.now() };
        aviationFailureCache = { data: null, time: 0 };
        openSkyBlockedUntil = 0;
        return res.json(result);
    } catch (err) {
        openSkyBlockedUntil = Date.now() + OPENSKY_RETRY_MS;
        primaryFailures.push(`opensky[${aviationDiagnostic(err)}]`);
        console.warn('OpenSky proxy failed, falling back:', aviationDiagnostic(err));
    }
    }

    // OpenSky blocks cloud/datacenter egress ranges, so a Render deploy cannot
    // reach it even though the same call works from a home connection. Fall
    // back to a second ADS-B aggregator rather than showing an empty layer.
    try {
        const result = await fetchAircraftFromAdsbLol();
        aviationCache = { data: result, time: Date.now() };
        aviationFailureCache = { data: null, time: 0 };
        res.json(result);
    } catch (err) {
        const detail = primaryFailures.join(' ') + ' adsb.lol[' + (err.message || aviationDiagnostic(err)) + ']';
        const message = 'Aviation feed unavailable';
        console.warn('All aviation providers failed:', detail);
        const result = aviationCache.data
            ? { ...aviationCache.data, stale: true, error: message, detail }
            : { aircraft: [], count: 0, error: message, detail };
        aviationFailureCache = { data: result, time: Date.now() };
        res.json(result);
    }
});

// ─── Auth Routes ───────────────────────────────────────────────
app.use('/api/auth', authLimiter, authRoutes);

// ─── Protected Routes ──────────────────────────────────────────
app.use('/api/events', authMiddleware, eventRoutes);
app.use('/api/alerts', authMiddleware, alertRoutes);
app.use('/api/map', dataLimiter, authMiddleware, mapRoutes);
app.use('/api/watchlists', authMiddleware, requireAdminRole, watchlistsRoutes);
app.use('/api/intelligence', authMiddleware, intelligenceRoutes);
app.use('/api/osint', authMiddleware, osintRoutes);
app.use('/api/darkweb', authMiddleware, darkwebRoutes);
app.use('/api/audit', authMiddleware, requireAdminRole, auditRoutes);
app.use('/api/assets', authMiddleware, requireAdminRole, assetRoutes);

// ─── Seed Endpoint (protected, dev-only) ────────────────────────
// db/seed.js inserts INVENTED geopolitical events, alerts and dark-web
// posts so the UI has something to render during development. Those rows are
// indistinguishable from real intel once written, so seeding is refused on a
// deployed instance: a live dashboard must only ever show collected data.
const SEED_BLOCKED = process.env.NODE_ENV === 'production' || process.env.RENDER === 'true';

app.post('/api/seed', authMiddleware, requireAdminRole, (req, res) => {
    if (SEED_BLOCKED) {
        return res.status(403).json({
            error: 'Seeding is disabled on a deployed instance',
            detail: 'db/seed.js writes fabricated events that would be shown as real intel.',
        });
    }
    try {
        const seed = require('./db/seed');
        seed();
        res.json({ success: true, message: 'Database reseeded (development only)' });
    } catch (err) {
        console.error('Seed error:', err);
        res.status(500).json({ error: 'Seed failed' });
    }
});

// ─── Export/Backup Route ───────────────────────────────────────
const { exportAll } = require('./services/export');
app.get('/api/export', authMiddleware, (req, res) => {
    try {
        const days = clampDays(req.query.days, { min: 1, max: 3650, fallback: 30 });
        const data = exportAll(days);
        res.json(data);
    } catch (err) {
        console.error('Export error:', err);
        res.status(500).json({ error: 'Export failed' });
    }
});

// ─── 404 Handler ───────────────────────────────────────────────
app.use((req, res) => {
    res.status(404).json({ error: 'Endpoint not found' });
});

// ─── Error Handler ─────────────────────────────────────────────
app.use((err, req, res, next) => {
    // Log the stack, not just the message. The previous handler printed only
    // `err.message`, which is why a 3,190-line error log contained zero stack
    // traces and no root cause could be recovered.
    console.error(`❌ ${req.method} ${req.originalUrl} — ${err.message}`);
    if (err.stack) console.error(err.stack);
    res.status(err.status || 500).json({ error: 'Internal server error' });
});

// ─── Start Server ──────────────────────────────────────────────
function start() {
    getDb();

    const server = http.createServer(app);

    // A port conflict surfaces as an async 'error' event on the WebSocketServer,
    // which is outside the try/catch around start(). Unhandled, it killed the
    // process with a bare EADDRINUSE stack and no explanation.
    server.on('error', (err) => {
        if (err.code === 'EADDRINUSE') {
            console.error(
                `\n❌ Port ${PORT} is already in use — another Sentinel instance is running.\n` +
                `   Set PORT to a free port, or stop the other process.\n`
            );
        } else {
            console.error('HTTP server error:', err.message);
        }
        closeDb();
        process.exit(1);
    });

    // ─── WebSocket Server ──────────────────────────────────────
    const wss = new WebSocketServer({ server, path: '/ws' });

    wss.on('error', (err) => console.error('WebSocket server error:', err.message));

    wss.on('connection', (ws, req) => {
        console.log(`🔌 WS client connected from ${req.socket.remoteAddress}`);

        ws.send(JSON.stringify({ type: 'connected', timestamp: new Date().toISOString() }));

        ws.on('close', () => {
            console.log('🔌 WS client disconnected');
        });

        ws.on('error', (err) => {
            console.error('WS error:', err.message);
        });
    });

    // ─── Event Broadcast ──────────────────────────────────────
    eventBus.on('new_event', (event) => {
        broadcastSSE('new_event', event);
        wss.clients.forEach((client) => {
            if (client.readyState === 1) {
                client.send(JSON.stringify({ type: 'new_event', data: event }));
            }
        });
    });

    eventBus.on('new_alert', (alert) => {
        broadcastSSE('new_alert', alert);
        wss.clients.forEach((client) => {
            if (client.readyState === 1) {
                client.send(JSON.stringify({ type: 'new_alert', data: alert }));
            }
        });
    });

    server.listen(PORT, '0.0.0.0', () => {
        const cfg = configStatus();
        console.log(`\n${'═'.repeat(55)}`);
        console.log(`  🌍 Sentinel Intelligence Server`);
        console.log(`  📡 HTTP:   http://localhost:${PORT}`);
        console.log(`  🔌 WS:     ws://localhost:${PORT}/ws`);
        console.log(`  📡 SSE:    http://localhost:${PORT}/api/events/stream  (JWT required)`);
        console.log(`${'─'.repeat(55)}`);
        console.log(`  💾 DB:         ${cfg.db}`);
        console.log(`  🔒 JWT secret: ${cfg.jwtSecret}`);
        console.log(`  🔑 API key:    ${cfg.apiSecretKey}`);
        console.log(`${'─'.repeat(55)}`);
        console.log(`  📰 NewsAPI:  ${cfg.newsApi === 'configured' ? '✅ configured' : '⚠️  not set (ingestion off)'}`);
        console.log(`  🧠 Groq AI:  ${cfg.groq === 'configured' ? '✅ configured' : '⚠️  not set (heuristic fallback)'}`);
        console.log(`  ✈️  OpenSky:  ${cfg.openSky === 'configured' ? '✅ configured' : '⚠️  anonymous (rate limited)'}`);
        console.log(`${'═'.repeat(55)}\n`);

        startScheduler();
        startBroadcaster();
        logAction('SYSTEM_START', `Sentinel server started on port ${PORT}`);
        logAction('SCHEDULER_CREATED', 'Intelligence scheduler initialised');
    });
}

function shutdown(signal) {
    console.log(`\n🛑 Shutting down (${signal})...`);
    stopBroadcaster();
    for (const client of sseClients) {
        try { client.end(); } catch { /* already closed */ }
    }
    sseClients.clear();
    closeDb();
    process.exit(0);
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

try {
    start();
} catch (err) {
    console.error('\n❌ Server failed to start:', err.message);
    process.exit(1);
}
