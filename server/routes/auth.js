const express = require('express');
const jwt = require('jsonwebtoken');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
const router = express.Router();

let _passwordHash = process.env.AUTH_PASSWORD_HASH || null;
let _bcryptAvailable = true;

async function getPasswordHash() {
    if (_passwordHash) return _passwordHash;

    const plainPassword = process.env.AUTH_PASSWORD || 'intel2024';

    if (!_bcryptAvailable) {
        _passwordHash = plainPassword;
        return _passwordHash;
    }

    try {
        const bcrypt = require('bcrypt');
        _passwordHash = await bcrypt.hash(plainPassword, 10);
        console.log('🔐 Password hash generated (set AUTH_PASSWORD_HASH env var for production)');
    } catch (err) {
        console.warn('⚠️ bcrypt unavailable, using plaintext fallback. Set AUTH_PASSWORD_HASH to suppress.');
        _bcryptAvailable = false;
        _passwordHash = plainPassword;
    }

    return _passwordHash;
}

// POST /api/auth/login
router.post('/login', async (req, res) => {
    try {
        const { username, password } = req.body;

        if (!username || !password) {
            return res.status(400).json({ error: 'Username and password required' });
        }

        const validUsername = process.env.AUTH_USERNAME || 'admin';

        if (username !== validUsername) {
            return res.status(401).json({ error: 'Invalid credentials' });
        }

        const hash = await getPasswordHash();

        let isValid = false;

        if (_bcryptAvailable) {
            try {
                const bcrypt = require('bcrypt');
                isValid = await bcrypt.compare(password, hash);
            } catch {
                isValid = (password === hash);
            }
        } else {
            isValid = (password === hash);
        }

        if (isValid) {
            const secret = process.env.JWT_SECRET || 'default-dev-secret-change-in-production';
            const token = jwt.sign(
                { username, role: 'admin' },
                secret,
                { expiresIn: '30d' }
            );

            return res.json({
                token,
                user: { username, role: 'admin' },
                expiresIn: '30d'
            });
        }

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
        const secret = process.env.JWT_SECRET || 'default-dev-secret-change-in-production';
        const decoded = jwt.verify(token, secret);
        res.json({ valid: true, user: decoded });
    } catch {
        res.status(401).json({ valid: false });
    }
});

module.exports = router;
