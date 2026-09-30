const express = require('express');
const { getLatestLogs, logAction } = require('../services/audit-log');
const { clampInt } = require('../lib/query');
const router = express.Router();

// GET /api/audit — Recent audit log entries (optionally POST to record actions)
router.get('/', (req, res) => {
    try {
        const limit = clampInt(req.query.limit, { min: 1, max: 500, fallback: 100 });
        const logs = getLatestLogs(limit);
        res.json({ logs });
    } catch (err) {
        console.error('Audit route error:', err);
        res.status(500).json({ error: 'Failed to load audit log' });
    }
});

// POST /api/audit — Record an action into the shared audit log
router.post('/', (req, res) => {
    try {
        const action = req.body ? (req.body.action || '').trim() : '';
        const details = req.body ? (req.body.details || '').trim() : '';
        if (!action) {
            return res.status(400).json({ error: 'action is required' });
        }
        logAction(action, details);
        res.status(201).json({ success: true });
    } catch (err) {
        console.error('Audit insert error:', err);
        res.status(500).json({ error: 'Failed to record audit entry' });
    }
});

module.exports = router;