const express = require('express');
const { getDb } = require('../db');
const router = express.Router();

// GET /api/intelligence/macro
// Fetches the latest global AI briefing
router.get('/macro', (req, res) => {
    try {
        const db = getDb();
        const briefing = db.prepare(`
            SELECT * FROM global_briefings
            ORDER BY created_at DESC
            LIMIT 1
        `).get();

        if (!briefing) {
            return res.json(null);
        }

        let situations = [];
        try { situations = JSON.parse(briefing.major_situations_json || '[]'); } catch (e) { }

        let predictions = [];
        try { predictions = JSON.parse(briefing.macro_predictions_json || '[]'); } catch (e) { }

        res.json({
            id: briefing.id,
            global_risk_score: briefing.global_risk_score,
            major_situations: situations,
            macro_predictions: predictions,
            created_at: briefing.created_at
        });
    } catch (err) {
        console.error('Error fetching global briefing:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = router;
