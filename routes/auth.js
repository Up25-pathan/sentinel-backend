const express = require('express');
const jwt = require('jsonwebtoken');
const router = express.Router();
require('dotenv').config();

// POST /api/auth/login — Single-user authentication
router.post('/login', (req, res) => {
    const { username, password } = req.body;

    const validUsername = process.env.AUTH_USERNAME || 'admin';
    const validPassword = process.env.AUTH_PASSWORD || 'intel2024';

    if (username === validUsername && password === validPassword) {
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
