const express = require('express');
const { getDb } = require('../db');
const router = express.Router();

// GET /api/alerts — Get alerts (recent/unread)
router.get('/', (req, res) => {
    try {
        const db = getDb();
        const { unread_only, limit = 50 } = req.query;

        let query = 'SELECT a.*, e.title as event_title, e.category, e.risk_level, e.location_name FROM alerts a JOIN events e ON a.event_id = e.id';
        let params = [];

        if (unread_only === '1' || unread_only === 'true') {
            query += ' WHERE a.is_read = 0';
        }

        query += ' ORDER BY a.created_at DESC LIMIT ?';
        params.push(parseInt(limit));

        const alerts = db.prepare(query).all(...params);
        const unreadCount = db.prepare('SELECT COUNT(*) as count FROM alerts WHERE is_read = 0').get();

        res.json({
            alerts,
            unread_count: unreadCount.count
        });
    } catch (err) {
        console.error('Error fetching alerts:', err);
        res.status(500).json({ error: 'Failed to fetch alerts' });
    }
});

// POST /api/alerts/:id/read — Mark alert as read
router.post('/:id/read', (req, res) => {
    try {
        const db = getDb();
        const result = db.prepare('UPDATE alerts SET is_read = 1 WHERE id = ?').run(req.params.id);

        if (result.changes === 0) {
            return res.status(404).json({ error: 'Alert not found' });
        }

        res.json({ success: true });
    } catch (err) {
        console.error('Error marking alert as read:', err);
        res.status(500).json({ error: 'Failed to update alert' });
    }
});

// POST /api/alerts/read-all — Mark all alerts as read
router.post('/read-all', (req, res) => {
    try {
        const db = getDb();
        const result = db.prepare('UPDATE alerts SET is_read = 1 WHERE is_read = 0').run();
        res.json({ success: true, updated: result.changes });
    } catch (err) {
        console.error('Error marking all alerts as read:', err);
        res.status(500).json({ error: 'Failed to update alerts' });
    }
});

module.exports = router;
