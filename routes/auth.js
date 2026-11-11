const express = require('express');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { resolveJwtSecret, isUnset } = require('../env');
const { logAction } = require('../services/audit-log');
const { verifyToken, currentTokenVersion, JWT_ALGORITHM } = require('../middleware/auth');
const router = express.Router();

const passwordHashCache = new Map();

/**
 * Token lifetime. Was a flat 30 days, which meant a single leaked token stayed
 * usable for a month. A desktop client authenticates once per launch, so a much
 * shorter window costs the operator nothing while shrinking exposure sharply.
 * Override with AUTH_TOKEN_TTL (e.g. "8h", "24h").
 */
function tokenTtl() {
    const configured = process.env.AUTH_TOKEN_TTL;
    if (configured && !isUnset(configured)) return String(configured).trim();
    return '12h';
}

/**
 * Per-account lockout.
 *
 * The rate limiter is keyed by client address, so a distributed guessing
 * campaign — or any attacker able to rotate the apparent source IP — was never
 * actually throttled, and there was no account lockout at all. This counts
 * consecutive failures for the username itself.
 */
const MAX_ACCOUNT_FAILURES = 8;
const ACCOUNT_LOCKOUT_MS = 15 * 60 * 1000;
const accountFailures = new Map();

function lockoutRemaining(username) {
    const entry = accountFailures.get(username);
    if (!entry) return 0;
    const remaining = entry.until - Date.now();
    if (remaining <= 0) {
        accountFailures.delete(username);
        return 0;
    }
    return remaining;
}

function recordFailure(username) {
    const now = Date.now();
    const entry = accountFailures.get(username);
    if (!entry || now > entry.until) {
        accountFailures.set(username, { count: 1, until: now + ACCOUNT_LOCKOUT_MS });
        return 1;
    }
    entry.count += 1;
    if (entry.count >= MAX_ACCOUNT_FAILURES) {
        entry.until = now + ACCOUNT_LOCKOUT_MS;
        return entry.count;
    }
    return entry.count;
}

function clearFailures(username) {
    accountFailures.delete(username);
}

function constantTimeEqual(left, right) {
    const leftBuffer = Buffer.from(left);
    const rightBuffer = Buffer.from(right);
    return leftBuffer.length === rightBuffer.length
        && crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

async function verifyPassword(password, role) {
    const prefix = role === 'admin' ? 'AUTH' : 'AUTH_ANALYST';
    const configuredHash = process.env[`${prefix}_PASSWORD_HASH`];
    if (!isUnset(configuredHash)) {
        try {
            const bcrypt = require('bcrypt');
            return await bcrypt.compare(password, configuredHash);
        } catch (err) {
            console.error(`${role} bcrypt compare failed:`, err.message);
            throw new Error('bcrypt is unavailable');
        }
    }

    const configuredPassword = process.env[`${prefix}_PASSWORD`];
    if (isUnset(configuredPassword)) {
        throw new Error(`${prefix}_PASSWORD or ${prefix}_PASSWORD_HASH is not set`);
    }

    const cachedHash = passwordHashCache.get(role);
    if (cachedHash) {
        const bcrypt = require('bcrypt');
        return bcrypt.compare(password, cachedHash);
    }

    try {
        const bcrypt = require('bcrypt');
        const hash = await bcrypt.hash(String(configuredPassword).trim(), 10);
        passwordHashCache.set(role, hash);
        if (role === 'admin') {
            console.log('🔐 Password hash generated (set AUTH_PASSWORD_HASH env var for production)');
        }
        return bcrypt.compare(password, hash);
    } catch (err) {
        console.error('❌ bcrypt unavailable:', err.message);
        if (!process.env.ALLOW_PLAINTEXT_PASSWORD) {
            throw new Error(
                'bcrypt is unavailable. Set the password hash or explicitly allow plaintext comparison.'
            );
        }
        return constantTimeEqual(password, String(configuredPassword).trim());
    }
}

// POST /api/auth/login
router.post('/login', async (req, res) => {
    try {
        const { username, password } = req.body;

        if (typeof username !== 'string' || typeof password !== 'string' || !username.trim() || !password.trim()) {
            return res.status(400).json({ error: 'Username and password required' });
        }

        const sanitizedUsername = username.trim();
        const sanitizedPassword = password.trim();

        const adminUsername = isUnset(process.env.AUTH_USERNAME) ? 'admin' : String(process.env.AUTH_USERNAME).trim();
        const analystUsername = isUnset(process.env.AUTH_ANALYST_USERNAME)
            ? null : String(process.env.AUTH_ANALYST_USERNAME).trim();
        const role = sanitizedUsername === adminUsername
            ? 'admin'
            : analystUsername && sanitizedUsername === analystUsername
                ? 'analyst'
                : null;

        if (!role) {
            logAction('AUTH_FAILED', `Login attempt with username '${sanitizedUsername}'`);
            return res.status(401).json({ error: 'Invalid credentials' });
        }

        // Checked before the password comparison so a locked account cannot be
        // used as an oracle, and so the expensive bcrypt hash is not run for
        // every attempt against a known-locked name.
        const lockedFor = lockoutRemaining(sanitizedUsername);
        if (lockedFor > 0) {
            const minutes = Math.ceil(lockedFor / 60000);
            logAction('AUTH_FAILED', `Login blocked for '${sanitizedUsername}' (account locked)`);
            return res.status(429).json({
                error: `Account temporarily locked. Try again in ${minutes} minute${minutes === 1 ? '' : 's'}.`
            });
        }

        let isValid;
        try {
            isValid = await verifyPassword(sanitizedPassword, role);
        } catch (configErr) {
            console.error(`${role} auth configuration error:`, configErr.message);
            return res.status(500).json({ error: 'Server authentication not configured' });
        }

        if (isValid) {
            // Same resolver used by middleware/auth.js, so signing and
            // verification can never diverge.
            let secret;
            try {
                secret = resolveJwtSecret();
            } catch (configErr) {
                console.error('Auth configuration error:', configErr.message);
                return res.status(500).json({ error: 'Server authentication not configured' });
            }

            const ttl = tokenTtl();
            const token = jwt.sign(
                {
                    username: sanitizedUsername,
                    role,
                    ver: currentTokenVersion(),
                },
                secret,
                { algorithm: JWT_ALGORITHM, expiresIn: ttl }
            );

            clearFailures(sanitizedUsername);
            logAction('AUTH_LOGIN', `User '${sanitizedUsername}' authenticated successfully`);
            return res.json({
                token,
                user: { username: sanitizedUsername, role },
                expiresIn: ttl
            });
        }

        const failures = recordFailure(sanitizedUsername);
        logAction('AUTH_FAILED', `Invalid credentials for user '${sanitizedUsername}' (${failures} consecutive)`);
        return res.status(401).json({ error: 'Invalid credentials' });
    } catch (err) {
        console.error('Auth error:', err);
        return res.status(500).json({ error: 'Authentication failed' });
    }
});

// GET /api/auth/verify
router.get('/verify', (req, res) => {
    const authHeader = req.headers.authorization;
    if (!authHeader) return res.status(401).json({ valid: false });

    try {
        const token = authHeader.split(' ')[1];
        // Same verifier as the HTTP middleware and the WebSocket upgrade, so a
        // token revoked by bumping TOKEN_VERSION is rejected here too.
        const decoded = verifyToken(token);
        res.json({ valid: true, user: decoded });
    } catch {
        res.status(401).json({ valid: false });
    }
});

module.exports = router;
