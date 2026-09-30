const express = require('express');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { resolveJwtSecret, isUnset } = require('../env');
const { logAction } = require('../services/audit-log');
const router = express.Router();

let _passwordHash = process.env.AUTH_PASSWORD_HASH || null;
let _bcryptAvailable = true;

async function getPasswordHash() {
    if (_passwordHash) return _passwordHash;

    if (isUnset(process.env.AUTH_PASSWORD)) {
        throw new Error('AUTH_PASSWORD_HASH is not set');
    }
    const plainPassword = String(process.env.AUTH_PASSWORD).trim();

    if (!_bcryptAvailable) {
        _passwordHash = plainPassword;
        return _passwordHash;
    }

    try {
        const bcrypt = require('bcrypt');
        _passwordHash = await bcrypt.hash(plainPassword, 10);
        console.log('🔐 Password hash generated (set AUTH_PASSWORD_HASH env var for production)');
    } catch (err) {
        // Previously this latched off permanently and silently downgraded the
        // whole auth path to a plaintext === comparison. Now it is loud, and
        // the plain path is only used when explicitly enabled.
        console.error('❌ bcrypt unavailable:', err.message);
        if (!process.env.ALLOW_PLAINTEXT_PASSWORD) {
            throw new Error(
                'bcrypt is unavailable. Install it, set AUTH_PASSWORD_HASH, or explicitly ' +
                'set ALLOW_PLAINTEXT_PASSWORD=true to permit plaintext comparison.'
            );
        }
        _bcryptAvailable = false;
        _passwordHash = plainPassword;
    }

    return _passwordHash;
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

        const validUsername = isUnset(process.env.AUTH_USERNAME) ? 'admin' : String(process.env.AUTH_USERNAME).trim();

        if (sanitizedUsername !== validUsername) {
            logAction('AUTH_FAILED', `Login attempt with username '${sanitizedUsername}'`);
            return res.status(401).json({ error: 'Invalid credentials' });
        }

        let hash;
        try {
            hash = await getPasswordHash();
        } catch (configErr) {
            console.error('Auth configuration error:', configErr.message);
            return res.status(500).json({ error: 'Server authentication not configured' });
        }

        let isValid = false;

        if (_bcryptAvailable) {
            try {
                const bcrypt = require('bcrypt');
                isValid = await bcrypt.compare(sanitizedPassword, hash);
            } catch (err) {
                console.error('bcrypt compare failed:', err.message);
                isValid = false;
            }
        } else {
            isValid = sanitizedPassword === hash;
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
                { username: sanitizedUsername, role: 'admin' },
                secret,
                { expiresIn: '30d' }
            );

            logAction('AUTH_LOGIN', `User '${sanitizedUsername}' authenticated successfully`);
            return res.json({
                token,
                user: { username: sanitizedUsername, role: 'admin' },
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
