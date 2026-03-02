const express = require('express');
const { getDb } = require('../db');
const router = express.Router();

// GET /api/darkweb — Get dark web intelligence feed
router.get('/', (req, res) => {
    try {
        const db = getDb();
        const limit = parseInt(req.query.limit) || 50;
        const category = req.query.category; // MALWARE, BOTNET_C2, RANSOMWARE, THREAT_INTEL, EXPOSED_INFRA
        const threatLevel = req.query.threat_level; // LOW, MEDIUM, HIGH, CRITICAL

        let query = 'SELECT * FROM dark_web_intel';
        const conditions = [];
        const params = [];

        if (category) {
            conditions.push('category = ?');
            params.push(category);
        }
        if (threatLevel) {
            conditions.push('threat_level = ?');
            params.push(threatLevel);
        }

        if (conditions.length > 0) {
            query += ' WHERE ' + conditions.join(' AND ');
        }

        query += ' ORDER BY discovered_at DESC LIMIT ?';
        params.push(limit);

        const items = db.prepare(query).all(...params);

        // Parse tags JSON
        const parsed = items.map(item => ({
            ...item,
            tags: item.tags ? JSON.parse(item.tags) : [],
        }));

        res.json({
            count: parsed.length,
            items: parsed,
        });
    } catch (err) {
        console.error('Dark web route error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/darkweb/stats — Summary stats
router.get('/stats', (req, res) => {
    try {
        const db = getDb();

        const total = db.prepare('SELECT COUNT(*) as count FROM dark_web_intel').get();
        const critical = db.prepare("SELECT COUNT(*) as count FROM dark_web_intel WHERE threat_level = 'CRITICAL'").get();
        const today = db.prepare("SELECT COUNT(*) as count FROM dark_web_intel WHERE discovered_at > datetime('now', '-24 hours')").get();

        const byCategory = db.prepare(`
            SELECT category, COUNT(*) as count 
            FROM dark_web_intel 
            GROUP BY category 
            ORDER BY count DESC
        `).all();

        const bySource = db.prepare(`
            SELECT source, COUNT(*) as count 
            FROM dark_web_intel 
            GROUP BY source 
            ORDER BY count DESC
        `).all();

        res.json({
            total: total?.count || 0,
            critical: critical?.count || 0,
            today: today?.count || 0,
            byCategory,
            bySource,
        });
    } catch (err) {
        console.error('Dark web stats error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = router;
