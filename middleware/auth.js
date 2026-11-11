const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { resolveJwtSecret, isUnset } = require('../env');

/**
 * The only signing algorithm this service accepts.
 *
 * Neither sign nor verify previously pinned an algorithm, which leaves the
 * token layer exposed to algorithm-confusion classes of bug. Pinning HS256 on
 * both sides makes that impossible.
 */
const JWT_ALGORITHM = 'HS256';

/**
 * Token generation counter.
 *
 * Tokens used to be valid for 30 days with no revocation path at all: the only
 * way to invalidate a leaked token was to rotate JWT_SECRET, which also forced
 * every legitimate user to re-authenticate and, worse, is the same secret the
 * server signs with — so it is not something you can do casually. Carrying a
 * version claim means invalidating every outstanding token is now a one-value
 * environment change that does not disturb signing.
 */
function currentTokenVersion() {
    return String(process.env.TOKEN_VERSION || '1');
}

/**
 * Verify a JWT and confirm it belongs to the current token generation.
 * Used by both the HTTP middleware and the WebSocket upgrade handler so the two
 * can never diverge on secret, algorithm or revocation rules.
 */
function verifyToken(token, secret) {
    let key = secret;
    if (!key) {
        key = resolveJwtSecret();
    }
    const decoded = jwt.verify(token, key, { algorithms: [JWT_ALGORITHM] });

    // Tokens minted before versioning existed carry no claim. Accept them only
    // while the generation is still the default, so enabling versioning later
    // still forces a clean re-authentication instead of silently keeping old
    // tokens alive.
    const presented = decoded.ver === undefined ? '1' : String(decoded.ver);
    if (presented !== currentTokenVersion()) {
        const err = new Error('Token has been revoked');
        err.status = 401;
        throw err;
    }

    return decoded;
}

const MAX_BODY_STRING_LENGTH = 10000;

/**
 * Normalize incoming string fields.
 *
 * This used to strip HTML tags from every top-level string. That was not
 * encoding: it only covered depth 1, and it silently rewrote legitimate stored
 * data — a Credential whose value legitimately contained `<` or `>` was mangled
 * on the way into the database, which is worse than the XSS it was meant to
 * prevent. Every server response is JSON and the service emits no HTML at all,
 * so the correct defence is escaping at the render layer in the client.
 *
 * What is enforced here is only what cannot corrupt valid content: a length
 * ceiling and removal of NUL / control characters.
 */
function normalizeString(value) {
    if (typeof value !== 'string') return value;

    let out = value;
    // eslint-disable-next-line no-control-regex
    out = out.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '');
    if (out.length > MAX_BODY_STRING_LENGTH) {
        out = out.slice(0, MAX_BODY_STRING_LENGTH);
    }
    return out.trim();
}

function normalizeBody(req) {
    const body = req.body;
    if (!body || typeof body !== 'object' || Array.isArray(body) || Buffer.isBuffer(body)) return;
    for (const key of Object.keys(body)) {
        body[key] = normalizeString(body[key]);
    }
}

/**
 * Constant-time string comparison, so a key cannot be recovered by timing.
 */
function safeEqual(a, b) {
    const bufA = Buffer.from(String(a));
    const bufB = Buffer.from(String(b));
    if (bufA.length !== bufB.length) return false;
    return crypto.timingSafeEqual(bufA, bufB);
}

/**
 * API Key Middleware — requires X-API-Key header on ALL requests
 * This is a second layer of security beyond JWT tokens.
 * Set API_SECRET_KEY in your Render env vars.
 */
function apiKeyMiddleware(req, res, next) {
    // Skip for health check
    if (req.path === '/' || req.path === '/api/health') return next();

    const apiKey = req.headers['x-api-key'];
    const validKey = process.env.API_SECRET_KEY;

    // If no API_SECRET_KEY is configured, skip this check (backward compatible)
    if (isUnset(validKey)) return next();

    if (!apiKey || !safeEqual(apiKey, validKey)) {
        return res.status(403).json({ error: 'Invalid API key' });
    }
    next();
}

/**
 * JWT Auth Middleware — verifies Bearer token
 */
function authMiddleware(req, res, next) {
    // Skip auth for login and health endpoints
    if (req.path === '/api/auth/login' || req.path === '/api/health') {
        return next();
    }

    normalizeBody(req);

    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ error: 'No token provided' });
    }

    // resolveJwtSecret() throws at boot if unset (see env.js), so verification
    // can never silently use a different key than signing did. Previously this
    // read process.env.JWT_SECRET with no fallback while routes/auth.js signed
    // with a fallback, which produced a total lockout on an unset secret.
    let secret;
    try {
        secret = resolveJwtSecret();
    } catch (err) {
        console.error('Auth configuration error:', err.message);
        return res.status(500).json({ error: 'Server auth not configured' });
    }

    const token = authHeader.split(' ')[1];
    try {
        req.user = verifyToken(token, secret);
        next();
    } catch (err) {
        return res.status(401).json({ error: 'Invalid or expired token' });
    }
}

function requireAdminRole(req, res, next) {
    if (req.user?.role !== 'admin') {
        return res.status(403).json({ error: 'Admin access required' });
    }
    next();
}

/**
 * Security Headers Middleware — add defense headers to all responses
 *
 * X-XSS-Protection was dropped: it has been removed from every major browser and
 * in old ones it could itself introduce vulnerabilities, so advertising it is
 * pure noise. HSTS is only emitted over TLS, where it is actually meaningful;
 * sending it on a plaintext response is ignored by browsers.
 */
function securityHeaders(req, res, next) {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    if (req.secure || req.headers['x-forwarded-proto'] === 'https') {
        res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    }
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    res.removeHeader('X-Powered-By');
    next();
}

module.exports = {
    authMiddleware,
    apiKeyMiddleware,
    requireAdminRole,
    securityHeaders,
    verifyToken,
    currentTokenVersion,
    JWT_ALGORITHM,
    // Reused by the WebSocket upgrade handler in server.js: an upgrade bypasses
    // the whole Express chain, so it has to re-check the API key by hand.
    safeEqual,
};