const express = require('express');
const { getDb } = require('../db');
const router = express.Router();

// GET /api/map/markers — All events with coordinates for map display
router.get('/markers', (req, res) => {
    try {
        const db = getDb();
        const { category, risk_level } = req.query;

        let where = ['lat IS NOT NULL', 'lng IS NOT NULL'];
        let params = [];

        if (category) {
            where.push('category = ?');
            params.push(category);
        }
        if (risk_level) {
            where.push('risk_level = ?');
            params.push(risk_level);
        }

        const markers = db.prepare(`
            SELECT id, title, category, risk_level, location_name, country, 
                   lat, lng, is_breaking, summary, created_at
            FROM events 
            WHERE ${where.join(' AND ')}
            ORDER BY created_at DESC
        `).all(...params);

        res.json({ markers, count: markers.length });
    } catch (err) {
        console.error('Error fetching map markers:', err);
        res.status(500).json({ error: 'Failed to fetch map data' });
    }
});

// GET /api/map/heatmap — Weighted GPS data for risk density mapping
router.get('/heatmap', (req, res) => {
    try {
        const db = getDb();
        const data = db.prepare(`
            SELECT lat, lng,
                (CASE WHEN risk_level = 'CRITICAL' THEN 1.0
                      WHEN risk_level = 'HIGH' THEN 0.7
                      WHEN risk_level = 'MEDIUM' THEN 0.4
                      ELSE 0.2 END) + (escalation_score * 0.1) as weight
            FROM events WHERE lat IS NOT NULL AND lng IS NOT NULL
            ORDER BY created_at DESC LIMIT 1000
        `).all();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: 'Heatmap failed' });
    }
});

// GET /api/map/choropleth — Country-level risk shading (legacy compatibility)
router.get('/choropleth', (req, res) => {
    try {
        const db = getDb();
        const data = db.prepare(`
            SELECT country, SUM(CASE WHEN risk_level = 'CRITICAL' THEN 4
                                     WHEN risk_level = 'HIGH' THEN 3
                                     WHEN risk_level = 'MEDIUM' THEN 2
                                     ELSE 1 END) as risk_score
            FROM events WHERE lat IS NOT NULL AND lng IS NOT NULL
            GROUP BY country
        `).all();
        res.json({ regions: data });
    } catch (err) {
        res.status(500).json({ error: 'Choropleth failed' });
    }
});

// GET /api/map/stats — Global statistics
router.get('/stats', (req, res) => {
    try {
        const db = getDb();

        const total = db.prepare('SELECT COUNT(*) as count FROM events').get();
        const breaking = db.prepare('SELECT COUNT(*) as count FROM events WHERE is_breaking = 1').get();
        const critical = db.prepare('SELECT COUNT(*) as count FROM events WHERE risk_level = ?').get('CRITICAL');
        const high = db.prepare('SELECT COUNT(*) as count FROM events WHERE risk_level = ?').get('HIGH');

        const byCategory = db.prepare(`
            SELECT category, COUNT(*) as count 
            FROM events 
            GROUP BY category 
            ORDER BY count DESC
        `).all();

        res.json({
            total_events: total.count,
            breaking_events: breaking.count,
            critical_events: critical.count,
            high_risk_events: high.count,
            by_category: byCategory
        });
    } catch (err) {
        console.error('Error fetching stats:', err);
        res.status(500).json({ error: 'Failed to fetch stats' });
    }
});

module.exports = router;
