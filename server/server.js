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
const { authMiddleware, apiKeyMiddleware, securityHeaders } = require('./middleware/auth');
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

// ─── Rate Limiting ─────────────────────────────────────────────
const generalLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 120,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many requests, please try again later.' }
});

const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 20,
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
        const raw = await resp.json();
        const features = (raw.features || []).filter(f => f.geometry && f.geometry.coordinates).map(f => ({
            name: f.properties.Name || f.properties.Actor1Name || f.properties.Actor2Name || 'Unknown',
            label: f.properties.EventCode || 'Conflict Event',
            lat: f.geometry.coordinates[1],
            lng: f.geometry.coordinates[0],
            severity: f.properties.NumArticles ? (parseInt(f.properties.NumArticles) > 10 ? 'high' : parseInt(f.properties.NumArticles) > 3 ? 'medium' : 'low') : 'low',
            source: 'GDELT',
            url: f.properties.SOURCEURL || '',
        }));
        const result = { zones: [], events: features, count: features.length };
        conflictCache = { data: result, time: Date.now() };
        res.json(result);
    } catch (err) {
        if (conflictCache.data) {
            res.json({ ...conflictCache.data, stale: true });
        } else {
            res.json({ zones: [], events: [], count: 0 });
        }
    }
});

// ─── Aviation Data (JWT required — proxies OpenSky) ─────────────
let aviationCache = { data: null, time: 0 };
const OPENSKY_USER = process.env.OPENSKY_USERNAME || '';
const OPENSKY_PASS = process.env.OPENSKY_PASSWORD || '';
const OPENSKY_URL = 'https://opensky-network.org/api/states/all';

app.get('/api/map/aviation', authMiddleware, async (req, res) => {
    const CACHE_TTL = 30000;
    if (Date.now() - aviationCache.time < CACHE_TTL && aviationCache.data) {
        return res.json(aviationCache.data);
    }
    try {
        const opts = { signal: AbortSignal.timeout(10000) };
        if (OPENSKY_USER && OPENSKY_PASS) {
            const b64 = Buffer.from(OPENSKY_USER + ':' + OPENSKY_PASS).toString('base64');
            opts.headers = { 'Authorization': 'Basic ' + b64 };
        }
        const resp = await fetch(OPENSKY_URL, opts);
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
        const result = { aircraft: states, count: states.length, timestamp: new Date().toISOString() };
        aviationCache = { data: result, time: Date.now() };
        res.json(result);
    } catch (err) {
        console.error('OpenSky proxy error:', err.message);
        if (aviationCache.data) {
            res.json({ ...aviationCache.data, stale: true });
        } else {
            // Do not echo upstream error text back to the caller.
            res.json({ aircraft: [], count: 0, error: 'Aviation feed unavailable' });
        }
    }
});

// ─── Auth Routes ───────────────────────────────────────────────
app.use('/api/auth', authLimiter, authRoutes);

// ─── Protected Routes ──────────────────────────────────────────
app.use('/api/events', authMiddleware, eventRoutes);
app.use('/api/alerts', authMiddleware, alertRoutes);
app.use('/api/map', authMiddleware, mapRoutes);
app.use('/api/watchlists', authMiddleware, watchlistsRoutes);
app.use('/api/intelligence', authMiddleware, intelligenceRoutes);
app.use('/api/osint', authMiddleware, osintRoutes);
app.use('/api/darkweb', authMiddleware, darkwebRoutes);
app.use('/api/audit', authMiddleware, auditRoutes);
app.use('/api/assets', authMiddleware, assetRoutes);

// ─── Seed Endpoint (protected) ──────────────────────────────────
app.post('/api/seed', authMiddleware, (req, res) => {
    try {
        const seed = require('./db/seed');
        seed();
        res.json({ success: true, message: 'Database reseeded' });
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
