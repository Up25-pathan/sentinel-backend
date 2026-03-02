const express = require('express');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const router = express.Router();
require('dotenv').config();

// Generate hash on first boot for migration convenience
let _passwordHash = process.env.AUTH_PASSWORD_HASH || null;

async function getPasswordHash() {
    if (!_passwordHash) {
        const plainPassword = process.env.AUTH_PASSWORD || 'intel2024';
        _passwordHash = await bcrypt.hash(plainPassword, 12);
        console.log('🔐 Password hash generated (set AUTH_PASSWORD_HASH env var for production)');
    }
    return _passwordHash;
}

// Pre-generate on module load
getPasswordHash();

// POST /api/auth/login — Single-user authentication with bcrypt
router.post('/login', async (req, res) => {
    const { username, password } = req.body;

    const validUsername = process.env.AUTH_USERNAME || 'admin';

    if (username !== validUsername) {
        return res.status(401).json({ error: 'Invalid credentials' });
    }

    try {
        const hash = await getPasswordHash();
        const isValid = await bcrypt.compare(password, hash);

        if (isValid) {
            const token = jwt.sign(
                { username, role: 'admin' },
                process.env.JWT_SECRET,
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

// GET /api/auth/verify — Verify token is still valid
router.get('/verify', (req, res) => {
    const authHeader = req.headers.authorization;
    if (!authHeader) return res.status(401).json({ valid: false });

    try {
        const token = authHeader.split(' ')[1];
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        res.json({ valid: true, user: decoded });
    } catch {
        res.status(401).json({ valid: false });
    }
});

module.exports = router;
