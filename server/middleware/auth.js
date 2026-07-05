const jwt = require('jsonwebtoken');
require('dotenv').config();

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
    if (!validKey) return next();

    if (!apiKey || apiKey !== validKey) {
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

    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ error: 'No token provided' });
    }

    const token = authHeader.split(' ')[1];
    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        req.user = decoded;
        next();
    } catch (err) {
        return res.status(401).json({ error: 'Invalid or expired token' });
    }
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

module.exports = { authMiddleware, apiKeyMiddleware, securityHeaders };
