const express = require('express');
const cors = require('cors');
const http = require('http');
const net = require('net');
const morgan = require('morgan');
const helmet = require('helmet');
const { WebSocketServer } = require('ws');

// Loads server/.env regardless of process CWD, and validates it.
const { validateEnv, resolveJwtSecret, configStatus } = require('./env');
validateEnv();

const { getDb, closeDb } = require('./db');
const { authMiddleware, apiKeyMiddleware, requireAdminRole, securityHeaders, verifyToken } = require('./middleware/auth');
const { isUnset } = require('./env');
const { safeEqual } = require('./middleware/auth');
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
const vaultRoutes = require('./routes/vault');
const { logAction } = require('./services/audit-log');

const rateLimit = require('express-rate-limit');

const app = express();
const PORT = process.env.PORT || 3001;

/**
 * Resolve the real client address for rate-limiting purposes.
 *
 * Background: this app is deployed behind exactly one TLS-terminating proxy, so
 * X-Forwarded-For arrives as "<spoofable...>, <address the proxy observed>".
 * Express's `req.ip` under `trust proxy = 1` can return the attacker-supplied
 * part of that chain, which meant a client could send a fresh X-Forwarded-For on
 * every request and be handed a fresh rate-limit bucket each time — fully
 * defeating the login brute-force limiter, while also letting the limiter's
 * in-memory store grow by one entry per forged value.
 *
 * `TRUSTED_PROXY_HOPS` makes the trust decision explicit instead of implied:
 *
 *   unset / 0  -> the TCP peer address is authoritative and the header is
 *                 ignored entirely. Unforgeable. Use this whenever the server
 *                 is bound to a publicly routable interface.
 *   1          -> exactly one trusted proxy sits in front; the rightmost header
 *                 entry is the address that proxy observed. This is the correct
 *                 setting for the Render deployment.
 *
 * Any value is rejected as malformed rather than silently coerced, because
 * "trust the client's own header" is precisely the vulnerability this replaced.
 */
const TRUSTED_PROXY_HOPS = (() => {
    const raw = String(process.env.TRUSTED_PROXY_HOPS ?? '1').trim();
    const n = Number.parseInt(raw, 10);
    if (!Number.isInteger(n) || n < 0 || n > 10) {
        console.warn(
            `[security] Ignoring invalid TRUSTED_PROXY_HOPS=${JSON.stringify(raw)}; using 0 (trust TCP peer only).`
        );
        return 0;
    }
    return n;
})();

// Express must agree with the limiter about how many proxies are in front of us.
// Left at a hard-coded 1 it silently disagreed with TRUSTED_PROXY_HOPS=0, which
// is how `req.ip` ended up reading the attacker-controlled end of X-Forwarded-For
// on the login route even after the limiter itself had been fixed.
app.set('trust proxy', TRUSTED_PROXY_HOPS);

function realClientIp(req) {
    // Derive from the socket, not from req.ip: the latter is already influenced by
    // the trust setting above and this keeps a single source of truth.
    const peer = req.socket?.remoteAddress || '';

    if (TRUSTED_PROXY_HOPS === 0) {
        return net.isIP(peer) ? peer : 'unknown';
    }

    const header = req.headers['x-forwarded-for'];
    const chain = Array.isArray(header)
        ? header
        : (typeof header === 'string' && header ? header.split(',') : []);

    // Walk right-to-left and skip exactly the number of proxy hops we trust. If
    // the client sent fewer entries than there are trusted hops, the chain is
    // short and cannot be trusted at all: fall back to the peer address.
    for (let i = chain.length - TRUSTED_PROXY_HOPS; i >= 0; i--) {
        const candidate = String(chain[i]).trim();
        if (net.isIP(candidate)) return candidate;
    }

    return net.isIP(peer) ? peer : 'unknown';
}

/**
 * Build a rate-limit key from a client address.
 *
 * express-rate-limit v7+ refuses custom key generators that can return a bare
 * IPv6 address, because a single host is routinely handed a whole /64 and can
 * trivially rotate addresses within it to get fresh buckets — the same class of
 * bypass as the X-Forwarded-For problem above. Normalising to the /64 prefix
 * (or /48 for the larger allocations) is the vendor-documented remedy.
 */
function rateLimitKey(req) {
    const ip = realClientIp(req);
    // Strip the IPv4-mapped IPv6 wrapper ("::ffff:1.2.3.4") so a dual-stack
    // client cannot get separate buckets for its two representations.
    const bare = ip.startsWith('::ffff:') && net.isIPv4(ip.slice(7)) ? ip.slice(7) : ip;
    if (!net.isIPv6(bare)) return bare;
    const parts = bare.split(':');
    return net.isIPv4(parts[0]) ? parts[0] : `${parts.slice(0, 3).join(':')}::/64`;
}

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
    keyGenerator: rateLimitKey,
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
    keyGenerator: rateLimitKey,
    message: { error: 'Data feed rate limit reached, please retry shortly.' }
});

const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 20,
    standardHeaders: true,
    legacyHeaders: false,
    keyGenerator: rateLimitKey,
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

// Explicit origin allowlist instead of cors()'s `Access-Control-Allow-Origin: *`.
// Tokens are bearer-only today so a wildcard is not directly exploitable, but it
// leaves the app one move away from leaking data the moment ambient auth
// (cookies) is introduced. Unlisted origins still work from non-browser clients
// such as the desktop app, which sends no Origin header at all.
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || '')
    .split(',')
    .map((o) => o.trim())
    .filter(Boolean);

app.use(cors({
    origin(origin, callback) {
        if (!origin || ALLOWED_ORIGINS.length === 0 || ALLOWED_ORIGINS.includes(origin)) {
            return callback(null, true);
        }
        return callback(null, false);
    },
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-API-Key'],
    maxAge: 600
}));

app.use(securityHeaders);

// Throttling is registered before body parsing and logging on purpose. Body
// parsing and morgan were previously ahead of the limiter, so an unauthenticated
// client could force a full 100 kB JSON parse plus a synchronous stdout write per
// request at line rate — and every request the limiter then rejected had still
// been parsed and logged.
app.use(generalLimiter);
app.use(express.json({ limit: '100kb' }));
app.use(morgan('combined'));
app.use(apiKeyMiddleware);

// ─── SSE Clients ────────────────────────────────────────────────
const sseClients = new Set();

// Handles are hoisted out of start() so shutdown() can drain them. Previously the
// HTTP server was never closed at all, and the WebSocket server was unreachable
// from the shutdown path.
let httpServer = null;
let wss = null;
let wsPing = null;

// A stalled reader would otherwise let the write buffer grow without limit.
// Beyond this we drop the subscriber; the desktop client reconnects on its own.
const SSE_MAX_BUFFERED_BYTES = 1024 * 1024;
const SSE_MAX_CLIENTS = 50;

function broadcastSSE(event, data) {
    const msg = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    for (const client of sseClients) {
        try {
            if (client.writableLength > SSE_MAX_BUFFERED_BYTES) {
                sseClients.delete(client);
                client.end();
                continue;
            }
            client.write(msg);
        } catch (e) {
            sseClients.delete(client);
        }
    }
}

/**
 * Public health check — no auth, for load balancers.
 *
 * Source state and broadcaster internals used to be returned verbatim. Each
 * source's `lastError` carries raw upstream error strings and the broadcaster
 * block exposed retry counters and internal row ids, all readable without a
 * token. Only a coarse per-source status is published now; the full detail
 * stays behind the authenticated admin surface.
 */
app.get('/api/health', (req, res) => {
    const db = getDb();
    const eventCount = db.prepare('SELECT COUNT(*) as count FROM events').get();
    const alertCount = db.prepare('SELECT COUNT(*) as count FROM alerts WHERE is_read = 0').get();

    // Iterate the source list itself. Object.entries(sourceHealth()) walked the
    // summary object's keys instead (coverage/total/healthy/...), so every entry
    // resolved to info?.status === undefined and the public endpoint advertised
    // seven sources all reported as "unknown" regardless of real state.
    const health = sourceHealth();
    const sources = {};
    for (const source of health.sources || []) {
        // Coarse on purpose: name + status only. lastError can carry upstream
        // response bodies and query fragments, so it stays on the admin surface.
        sources[source.name] = { status: source.status };
    }

    res.json({
        status: health.broken > 0 ? 'degraded' : 'ok',
        timestamp: new Date().toISOString(),
        events: eventCount.count,
        unread_alerts: alertCount.count,
        broadcaster: { running: broadcasterStatus().running },
        coverage: health.coverage,
        sources,
        version: '1.0.0'
    });
});

app.get('/', (req, res) => {
    res.json({ service: 'SENTINEL API', health: '/api/health' });
});

// ─── SSE Stream (JWT required) ──────────────────────────────────
app.get('/api/events/stream', authMiddleware, (req, res) => {
    // The subscriber set was previously unbounded and unmonitored, so anonymous
    // or forgotten clients could accumulate and hold server memory open.
    if (sseClients.size >= SSE_MAX_CLIENTS) {
        return res.status(503).json({ error: 'Too many live streams, retry shortly.' });
    }

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
// Aircraft that have not been heard from in this long are dropped so the map
// does not keep showing aircraft that have already landed.
const AIRCRAFT_MAX_AGE_SECONDS = 120;
const FEET_TO_METRES = 0.3048;
const KT_TO_MS = 0.514444;
const FT_MIN_TO_MS = 0.00508;
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
    return (raw.ac || [])
        .filter(a => a.lat != null && a.lon != null)
        .filter(a => !(Number.isFinite(a.seen) && a.seen > AIRCRAFT_MAX_AGE_SECONDS))
        .map(a => ({
        icao24: a.icao24 || a.hex || '',
        callsign: (a.flight || '').trim(),
        aircraft_type: (a.t || '').trim(),
        registration: (a.r || '').trim(),
        origin_country: a.country_iso_name || '',
        lat: a.lat,
        lng: a.lon,
        // adsb.lol reports feet and knots. OpenSky reports metres and m/s, and
        // the map converts using those units, so convert here to keep one
        // contract and avoid altitudes that are 3x too high and speeds 2x off.
        // alt_baro is the string "ground" for aircraft on the ground, which
        // must not be coerced into NaN.
        altitude: Number.isFinite(a.alt_baro) ? a.alt_baro * FEET_TO_METRES : null,
        geometric_altitude: Number.isFinite(a.alt_geom) ? a.alt_geom * FEET_TO_METRES : null,
        velocity: Number.isFinite(a.gs) ? a.gs * KT_TO_MS : null,
        vertical_rate: Number.isFinite(a.geom_rate) ? a.geom_rate * FT_MIN_TO_MS : null,
        heading: a.true_heading != null ? a.true_heading : (a.track != null ? a.track : null),
        on_ground: a.alt_baro === 'ground' || !(Number.isFinite(a.gs) || Number.isFinite(a.alt_baro)),
        squawk: a.squawk || null,
        category: a.category || null,
        emergency: (a.emergency && a.emergency !== 'none') ? a.emergency : null,
        age_seconds: Number.isFinite(a.seen) ? a.seen : null,
        nic: a.nic != null ? a.nic : null,
        nac_p: a.nac_p != null ? a.nac_p : null,
        sil: a.sil != null ? a.sil : null,
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
        const observedAt = Number(raw.time) || Math.floor(Date.now() / 1000);
        const states = (raw.states || []).filter(s => s[5] && s[6]).map(s => ({
            icao24: s[0],
            callsign: (s[1] || '').trim(),
            aircraft_type: '',
            registration: '',
            origin_country: s[2] || '',
            lat: s[6],
            lng: s[5],
            altitude: s[7],
            geometric_altitude: s[13] != null ? s[13] : null,
            velocity: s[9],
            vertical_rate: s[11] != null ? s[11] : null,
            heading: s[10],
            on_ground: !!s[8],
            squawk: s[14] || null,
            category: s[17] != null ? s[17] : null,
            emergency: null,
            age_seconds: Number.isFinite(s[4]) ? Math.max(0, observedAt - s[4]) : null,
            nic: null,
            nac_p: null,
            sil: null,
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
app.use('/api/vault', authMiddleware, vaultRoutes);

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
// Full-database dump. Admin-only: the export includes the `assets` table, which
// stores Credential rows, so leaving this behind authMiddleware alone let the
// read-only analyst role extract credentials that POST /api/assets restricts to
// admins.
const { exportAll } = require('./services/export');
app.get('/api/export', authMiddleware, requireAdminRole, (req, res) => {
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
    res.status(err.status || 500).json({
        error: err.status && err.status < 500 ? err.message : 'Internal server error',
    });
});

// ─── Start Server ──────────────────────────────────────────────
function start() {
    getDb();

    const server = http.createServer(app);
    httpServer = server;

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
    // noServer: true so the upgrade is authenticated by our own handler *before*
    // the handshake completes. The feed used to accept any anonymous socket: the
    // HTTP upgrade never touched the Express middleware chain, so every field
    // that /api/events protects with a JWT — titles, summaries, AI briefs, bias
    // analysis, coordinates, risk levels — was streamed to whoever asked. It was
    // also an unbounded memory-exhaustion path, since the client set was never
    // capped and send() was called with no backpressure check.
    const WS_MAX_CLIENTS = 50;
    const WS_MAX_BUFFERED_BYTES = 1024 * 1024;
    const WS_PING_INTERVAL_MS = 30000;

    wss = new WebSocketServer({ noServer: true, maxPayload: 64 * 1024 });

    wss.on('error', (err) => console.error('WebSocket server error:', err.message));

    server.on('upgrade', (req, socket, head) => {
        let pathname = '';
        try {
            pathname = new URL(req.url, `http://${req.headers.host || 'localhost'}`).pathname;
        } catch {
            pathname = '';
        }
        if (pathname !== '/ws') {
            socket.destroy();
            return;
        }

        let decoded;
        try {
            decoded = verifyWebSocketToken(req);
        } catch (err) {
            const status = err.status || 401;
            socket.write(
                `HTTP/1.1 ${status} ${status === 401 ? 'Unauthorized' : status === 403 ? 'Forbidden' : 'Service Unavailable'}\r\n` +
                'Connection: close\r\n' +
                'Content-Length: 0\r\n\r\n'
            );
            socket.destroy();
            return;
        }

        wss.handleUpgrade(req, socket, head, (ws) => {
            ws.user = decoded;
            ws.isAlive = true;
            wss.emit('connection', ws, req);
        });
    });

    function verifyWebSocketToken(req) {
        if (wss.clients.size >= WS_MAX_CLIENTS) {
            const err = new Error('Too many websocket clients');
            err.status = 503;
            throw err;
        }

        // An HTTP upgrade never traverses the Express chain, so apiKeyMiddleware
        // never runs for /ws. If API_SECRET_KEY is configured, the socket stream
        // would otherwise be reachable with nothing but a stolen JWT — i.e. the
        // second factor that guards every HTTP route was silently absent here.
        const configuredKey = process.env.API_SECRET_KEY;
        if (configuredKey && !isUnset(configuredKey)) {
            const supplied = req.headers['x-api-key'];
            if (!supplied || !safeEqual(String(supplied), configuredKey)) {
                const err = new Error('Invalid API key');
                err.status = 403;
                throw err;
            }
        }

        // Desktop clients can set headers freely; browsers cannot, so the token
        // may also arrive as a query parameter.
        let token = null;
        const authHeader = req.headers.authorization;
        if (authHeader && authHeader.startsWith('Bearer ')) {
            token = authHeader.slice(7).trim();
        }
        if (!token) {
            try {
                token = new URL(req.url, 'http://localhost').searchParams.get('token');
            } catch {
                token = null;
            }
        }
        if (!token) {
            const err = new Error('Missing token');
            err.status = 401;
            throw err;
        }

        try {
            return verifyToken(token);
        } catch (err) {
            const wrapped = new Error('Invalid or expired token');
            wrapped.status = 401;
            throw wrapped;
        }
    }

    // Keepalive: half-open sockets otherwise linger in wss.clients forever and
    // are re-iterated on every single broadcast.
    const wsPingTimer = setInterval(() => {
        for (const client of wss.clients) {
            if (client.isAlive === false) {
                client.terminate();
                continue;
            }
            client.isAlive = false;
            try { client.ping(); } catch { /* closing */ }
        }
    }, WS_PING_INTERVAL_MS);
    wsPingTimer.unref();
    wsPing = wsPingTimer;

    wss.on('connection', (ws, req) => {
        console.log(`🔌 WS client connected (${req.socket.remoteAddress}, ${ws.user?.role || 'unknown'})`);

        ws.send(JSON.stringify({ type: 'connected', timestamp: new Date().toISOString() }));

        ws.on('pong', () => { ws.isAlive = true; });

        ws.on('close', () => {
            console.log('🔌 WS client disconnected');
        });

        ws.on('error', (err) => {
            console.error('WS error:', err.message);
        });
    });

    /** Send only if the socket is open and its buffer is not already saturated. */
    function sendToSocket(client, payload) {
        if (client.readyState !== 1) return;
        if (client.bufferedAmount > WS_MAX_BUFFERED_BYTES) {
            try { client.close(1013, 'Client too slow'); } catch { /* closing */ }
            return;
        }
        try { client.send(payload); } catch { /* closing */ }
    }

    // ─── Event Broadcast ──────────────────────────────────────
    eventBus.on('new_event', (event) => {
        broadcastSSE('new_event', event);
        const payload = JSON.stringify({ type: 'new_event', data: event });
        wss.clients.forEach((client) => sendToSocket(client, payload));
    });

    eventBus.on('new_alert', (alert) => {
        broadcastSSE('new_alert', alert);
        const payload = JSON.stringify({ type: 'new_alert', data: alert });
        wss.clients.forEach((client) => sendToSocket(client, payload));
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

    // Hard deadline: Render only grants a short grace period before SIGKILL, so
    // a stuck connection cannot be allowed to hold the process open.
    const forcedExit = setTimeout(() => {
        console.error('⚠️  Graceful shutdown timed out after 10s — forcing exit.');
        process.exit(1);
    }, 10000);
    forcedExit.unref();

    if (wsPing) clearInterval(wsPing);

    stopBroadcaster();

    // Tell every live subscriber we are going away so the desktop client shows a
    // disconnected state immediately instead of silently stalling on a stream
    // that will never produce another event.
    for (const client of sseClients) {
        try { client.end(); } catch { /* already closed */ }
    }
    sseClients.clear();

    if (wss) {
        for (const client of wss.clients) {
            try { client.close(1001, 'Server shutting down'); } catch { /* already closing */ }
        }
    }

    // server.close() stops new connections but waits for in-flight requests to
    // finish. Without it the previous shutdown called closeDb() and process.exit()
    // immediately, cutting every live request and SSE stream mid-response on
    // each deploy.
    const finish = (err) => {
        if (err) console.error('Error while closing HTTP server:', err.message);
        clearTimeout(forcedExit);
        closeDb();
        console.log('👋 Shutdown complete.');
        process.exit(err ? 1 : 0);
    };

    if (!httpServer) return finish(null);
    httpServer.close(finish);
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// Node ≥15 terminates the process on an unhandled rejection by default, and no
// guard existed anywhere in the codebase — so a single missed .catch in a cron
// job or a background feed would take the whole server down. Log loudly, then
// keep serving for rejections; an uncaught exception is not safely recoverable.
process.on('unhandledRejection', (reason) => {
    console.error('❌ Unhandled promise rejection:', reason instanceof Error ? reason.stack : reason);
});

process.on('uncaughtException', (err) => {
    console.error('❌ Uncaught exception:', err && err.stack ? err.stack : err);
    shutdown('uncaughtException');
});

// Exporting the app lets a test suite drive it in-process. Guarded on
// require.main so that `require('./server')` for testing does not also bind a
// port, start the scheduler, or install the signal/exception handlers above.
module.exports = { app, realClientIp, rateLimitKey, shutdown };

if (require.main === module) {
    try {
        start();
    } catch (err) {
        console.error('\n❌ Server failed to start:', err.message);
        process.exit(1);
    }
}
