const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { resolveJwtSecret, isUnset } = require('../env');

/**
 * Sanitize input — strip HTML tags and trim whitespace
 */
function sanitizeInput(str) {
    if (typeof str !== 'string') return str;
    return str.replace(/<[^>]*>/g, '').trim();
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
    if (req.path === '/api/health') return next();

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

    // Sanitize request body fields
    if (req.body && typeof req.body === 'object') {
        for (const key of Object.keys(req.body)) {
            if (typeof req.body[key] === 'string') {
                req.body[key] = sanitizeInput(req.body[key]);
            }
        }
    }

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
        const decoded = jwt.verify(token, secret);
        req.user = decoded;
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
 */
function securityHeaders(req, res, next) {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    // Don't reveal server tech stack
    res.removeHeader('X-Powered-By');
    next();
}

module.exports = { authMiddleware, apiKeyMiddleware, requireAdminRole, securityHeaders };
