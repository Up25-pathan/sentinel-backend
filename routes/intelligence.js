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

// ─── PROJECT NEXUS (Relational Intelligence) ──────────

// GET /api/intelligence/nexus/graph — Full relational graph
router.get('/nexus/graph', (req, res) => {
    try {
        const db = getDb();
        const limit = parseInt(req.query.limit) || 100;

        // Get recent events as nodes
        const events = db.prepare(`
            SELECT id, title as label, 'EVENT' as type, risk_level, category
            FROM events
            ORDER BY created_at DESC
            LIMIT ?
        `).all(limit / 2);

        // Get high-influence entities as nodes
        const entities = db.prepare(`
            SELECT id, name as label, type, influence_score
            FROM entities
            ORDER BY influence_score DESC
            LIMIT ?
        `).all(limit / 2);

        // Get links between them
        const nodes = [...events, ...entities];
        const nodeIds = nodes.map(n => n.id);

        // Filter links where both source and target are in our node list
        const placeholders = nodeIds.map(() => '?').join(',');
        const links = db.prepare(`
            SELECT source_id as source, target_id as target, link_type as label, strength
            FROM nexus_links
            WHERE source_id IN (${placeholders}) AND target_id IN (${placeholders})
        `).all(...nodeIds, ...nodeIds);

        res.json({ nodes, links });
    } catch (err) {
        console.error('Nexus graph error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/nexus/entity/:id — Detail for a specific entity
router.get('/nexus/entity/:id', (req, res) => {
    try {
        const db = getDb();
        const entity = db.prepare('SELECT * FROM entities WHERE id = ?').get(req.params.id);

        if (!entity) {
            return res.status(404).json({ error: 'Entity not found' });
        }

        // Get related links and their targets/sources
        const links = db.prepare(`
            SELECT l.*, 
                   e_target.name as target_name, e_target.type as target_type,
                   ev_target.title as target_event_title,
                   e_source.name as source_name, e_source.type as source_type,
                   ev_source.title as source_event_title
            FROM nexus_links l
            LEFT JOIN entities e_target ON l.target_id = e_target.id
            LEFT JOIN events ev_target ON l.target_id = ev_target.id
            LEFT JOIN entities e_source ON l.source_id = e_source.id
            LEFT JOIN events ev_source ON l.source_id = ev_source.id
            WHERE l.source_id = ? OR l.target_id = ?
        `).all(req.params.id, req.params.id);

        res.json({ entity, links });
    } catch (err) {
        console.error('Nexus entity error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/sector/:sector — Sector-specific dashboard data
router.get('/sector/:sector', (req, res) => {
    try {
        const db = getDb();
        const sector = req.params.sector.toUpperCase();
        
        let categories = [];
        if (sector === 'DEFENSE') {
            categories = ['WAR', 'MILITARY_MOVEMENT', 'DIPLOMATIC_ESCALATION', 'NUCLEAR_THREAT', 'TERRORISM'];
        } else if (sector === 'ENERGY') {
            categories = ['ENERGY_SECURITY', 'SANCTIONS', 'ECONOMIC_WARFARE'];
        } else if (sector === 'CYBER') {
            categories = ['CYBER_ATTACK', 'DARK_WEB'];
        } else {
            return res.status(400).json({ error: 'Invalid sector' });
        }

        const placeholders = categories.map(() => '?').join(',');
        const events = db.prepare(`
            SELECT * FROM events 
            WHERE category IN (${placeholders})
            ORDER BY created_at DESC
            LIMIT 20
        `).all(...categories);

        res.json(events);
    } catch (err) {
        console.error('Sector intel error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = router;
