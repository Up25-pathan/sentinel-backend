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

// GET /api/intelligence/predictions — Forecast data
router.get('/predictions', (req, res) => {
    try {
        const db = getDb();
        const limit = parseInt(req.query.limit) || 10;
        
        const briefing = db.prepare(`
            SELECT macro_predictions_json FROM global_briefings 
            ORDER BY created_at DESC LIMIT 1
        `).get();
        
        if (!briefing || !briefing.macro_predictions_json) {
            return res.json([]);
        }
        
        let rawPredictions = JSON.parse(briefing.macro_predictions_json);
        
        // Normalize: handle both string arrays (from local NLP) and object arrays (from AI)
        const predictions = rawPredictions.map((p, i) => {
            if (typeof p === 'string') {
                return {
                    prediction_text: p,
                    impact_level: i === 0 ? 'HIGH' : 'MEDIUM',
                    probability: 0.65 - (i * 0.1),
                    timeline_estimate: 'Next 24-48h',
                };
            }
            return {
                ...p,
                timeline_estimate: p.timeline_estimate || 'Next 24-48h',
            };
        });

        res.json(predictions.slice(0, limit));
    } catch (err) {
        console.error('Predictions error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/dashboard — Command center aggregated stats
router.get('/dashboard', (req, res) => {
    try {
        const db = getDb();

        // Event counts
        const totalEvents = db.prepare('SELECT COUNT(*) as count FROM events').get().count;
        const criticalEvents = db.prepare("SELECT COUNT(*) as count FROM events WHERE risk_level = 'CRITICAL'").get().count;
        const highEvents = db.prepare("SELECT COUNT(*) as count FROM events WHERE risk_level = 'HIGH'").get().count;
        const breakingEvents = db.prepare("SELECT COUNT(*) as count FROM events WHERE is_breaking = 1").get().count;
        const last24h = db.prepare("SELECT COUNT(*) as count FROM events WHERE created_at > datetime('now', '-1 day')").get().count;

        // Unread alerts
        const unreadAlerts = db.prepare("SELECT COUNT(*) as count FROM alerts WHERE is_read = 0").get().count;

        // Entity counts
        const totalEntities = db.prepare('SELECT COUNT(*) as count FROM entities').get().count;
        const totalLinks = db.prepare('SELECT COUNT(*) as count FROM nexus_links').get().count;

        // Latest global risk
        const latestBriefing = db.prepare(`
            SELECT global_risk_score, created_at FROM global_briefings 
            WHERE id NOT LIKE 'daily-%'
            ORDER BY created_at DESC LIMIT 1
        `).get();

        // Category distribution
        const categoryDist = db.prepare(`
            SELECT category, COUNT(*) as count FROM events 
            WHERE category IS NOT NULL
            GROUP BY category 
            ORDER BY count DESC
        `).all();

        // Top countries
        const topCountries = db.prepare(`
            SELECT country, COUNT(*) as count FROM events 
            WHERE country IS NOT NULL
            GROUP BY country 
            ORDER BY count DESC 
            LIMIT 10
        `).all();

        // Data sources (count distinct source names)
        const activeSources = db.prepare('SELECT COUNT(DISTINCT name) as count FROM sources').get().count;

        // Risk trend (last 7 days)
        const riskTrend = db.prepare(`
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total,
                SUM(CASE WHEN risk_level = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
                SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN risk_level = 'LOW' THEN 1 ELSE 0 END) as low
            FROM events 
            WHERE created_at > datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        `).all();

        res.json({
            overview: {
                total_events: totalEvents,
                critical_events: criticalEvents,
                high_events: highEvents,
                breaking_events: breakingEvents,
                events_last_24h: last24h,
                unread_alerts: unreadAlerts,
                global_risk_score: latestBriefing?.global_risk_score || 0,
                last_briefing: latestBriefing?.created_at || null,
                total_entities: totalEntities,
                total_nexus_links: totalLinks,
                active_sources: activeSources,
            },
            category_distribution: categoryDist,
            top_countries: topCountries,
            risk_trend: riskTrend,
        });
    } catch (err) {
        console.error('Dashboard error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/pattern — Detect anomalies/patterns in recent events
router.get('/pattern', (req, res) => {
    try {
        const db = getDb();
        // Spikes: multiple events in a country in the last 24h
        const spikeCountries = db.prepare(`
            SELECT country, COUNT(*) as count 
            FROM events 
            WHERE created_at > datetime('now', '-24 hours') AND country IS NOT NULL
            GROUP BY country
            HAVING count > 3
            ORDER BY count DESC
            LIMIT 5
        `).all();

        // Correlations: pairs of entities frequently linked to the same recent events
        const recentEvents = db.prepare(`SELECT id FROM events WHERE created_at > datetime('now', '-48 hours')`).all().map(e => e.id);
        const placeholders = recentEvents.map(() => '?').join(',');
        
        let relatedPairs = [];
        if (recentEvents.length > 0) {
            relatedPairs = db.prepare(`
                SELECT e1.name as entity1, e2.name as entity2, COUNT(*) as sync_count
                FROM nexus_links l1
                JOIN nexus_links l2 ON l1.source_id = l2.source_id AND l1.target_id != l2.target_id
                JOIN entities e1 ON l1.target_id = e1.id
                JOIN entities e2 ON l2.target_id = e2.id
                WHERE l1.source_id IN (${placeholders})
                GROUP BY e1.name, e2.name
                HAVING sync_count > 1
                ORDER BY sync_count DESC
                LIMIT 5
            `).all(...recentEvents);
        }

        res.json({
            anomalous_locations: spikeCountries,
            entity_correlations: relatedPairs
        });
    } catch (err) {
        console.error('Pattern api error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/timeline/:entityId — Timeline of events for an entity
router.get('/timeline/:entityId', (req, res) => {
    try {
        const db = getDb();
        const entityId = req.params.entityId;

        const timeline = db.prepare(`
            SELECT DISTINCT ev.* 
            FROM events ev
            JOIN nexus_links l ON ev.id = l.source_id 
            WHERE l.target_id = ?
            ORDER BY ev.created_at DESC
            LIMIT 20
        `).all(entityId);

        res.json(timeline);
    } catch (err) {
        console.error('Timeline error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = router;
