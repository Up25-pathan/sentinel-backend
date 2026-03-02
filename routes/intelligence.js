const express = require('express');
const { getDb } = require('../db');
const { chat } = require('../services/ai-chat');
const { getLatestDailyBriefing } = require('../services/daily-briefing');
const { getRiskTrends, getCategoryTrends, getRegionalTrends, getSourceCredibility, getIntelSummary } = require('../services/trend-analysis');
const router = express.Router();

// GET /api/intelligence/macro — Global AI briefing
router.get('/macro', (req, res) => {
    try {
        const db = getDb();
        const briefing = db.prepare(`
            SELECT * FROM global_briefings
            WHERE id NOT LIKE 'daily-%'
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

// POST /api/intelligence/chat — AI Chat Q&A
router.post('/chat', async (req, res) => {
    try {
        const { question } = req.body;
        if (!question || question.trim().length === 0) {
            return res.status(400).json({ error: 'Question is required' });
        }

        const result = await chat(question.trim());
        res.json(result);
    } catch (err) {
        console.error('Chat error:', err);
        res.status(500).json({ error: 'Failed to process question' });
    }
});

// GET /api/intelligence/daily — Latest daily briefing
router.get('/daily', (req, res) => {
    try {
        const briefing = getLatestDailyBriefing();
        res.json(briefing || { text: 'No daily briefing available yet.', eventCount: 0 });
    } catch (err) {
        console.error('Daily briefing error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/trends — Risk trend data over time
router.get('/trends', (req, res) => {
    try {
        const days = parseInt(req.query.days) || 30;
        const trends = getRiskTrends(days);
        res.json({ trends, days });
    } catch (err) {
        console.error('Trends error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/trends/categories — Category distribution over time
router.get('/trends/categories', (req, res) => {
    try {
        const days = parseInt(req.query.days) || 14;
        const trends = getCategoryTrends(days);
        res.json({ trends, days });
    } catch (err) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/trends/regions — Regional hotspot data
router.get('/trends/regions', (req, res) => {
    try {
        const days = parseInt(req.query.days) || 14;
        const regions = getRegionalTrends(days);
        res.json({ regions, days });
    } catch (err) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/sources — Source credibility data
router.get('/sources', (req, res) => {
    try {
        const sources = getSourceCredibility();
        res.json({ sources });
    } catch (err) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/summary — Quick intel summary stats
router.get('/summary', (req, res) => {
    try {
        const summary = getIntelSummary();
        res.json(summary);
    } catch (err) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = router;
