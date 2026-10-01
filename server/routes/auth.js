const express = require('express');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { resolveJwtSecret, isUnset } = require('../env');
const { logAction } = require('../services/audit-log');
const router = express.Router();

const passwordHashCache = new Map();

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

            const token = jwt.sign(
                { username: sanitizedUsername, role },
                secret,
                { expiresIn: '30d' }
            );

            logAction('AUTH_LOGIN', `User '${sanitizedUsername}' authenticated successfully`);
            return res.json({
                token,
                user: { username: sanitizedUsername, role },
                expiresIn: '30d'
            });
        }

        logAction('AUTH_FAILED', `Invalid credentials for user '${sanitizedUsername}'`);
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
        const decoded = jwt.verify(token, resolveJwtSecret());
        res.json({ valid: true, user: decoded });
    } catch {
        res.status(401).json({ valid: false });
    }
});

module.exports = router;
