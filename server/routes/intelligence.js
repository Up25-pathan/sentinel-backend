const express = require('express');
const { getDb } = require('../db');
const { clampInt, clampDays, pick, paginate } = require('../lib/query');
const { chat } = require('../services/ai-chat');
const { getLatestDailyBriefing } = require('../services/daily-briefing');
const { getRiskTrends, getCategoryTrends, getRegionalTrends, getSourceCredibility, getIntelSummary } = require('../services/trend-analysis');
const { vulnStats, syncVulnerabilities } = require('../services/vulnerabilities');
const { logAction } = require('../services/audit-log');
const router = express.Router();

// GET /api/intelligence/vulns
//   ?severity=CRITICAL|HIGH|MEDIUM|LOW   ?kev=1
//   ?days=N   ?q=<text>   ?sort=cvss|published   ?page=&limit=
//
// Real vulnerability data from NVD CVE + CISA KEV. The client used to call this
// endpoint, which did not exist, and fell back to a hardcoded list of 15 fake
// CVEs whenever the request failed — so it fabricated data on every run.
router.get('/vulns', (req, res) => {
    try {
        const db = getDb();
        const { limit, page, offset } = paginate(req.query, { defaultLimit: 50, maxLimit: 200 });

        const conditions = [];
        const params = [];

        const severity = String(req.query.severity || '').trim().toUpperCase();
        if (severity && severity !== 'ALL') {
            if (!['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'].includes(severity)) {
                return res.status(400).json({ error: 'Unknown severity' });
            }
            conditions.push('severity = ?');
            params.push(severity);
        }

        if (req.query.kev === '1' || req.query.kev === 'true') {
            conditions.push('in_kev = 1');
        }

        const days = clampDays(req.query.days, { min: 1, max: 3650, fallback: 0 });
        if (days > 0) {
            conditions.push("published > datetime('now', ?)");
            params.push(`-${days} days`);
        }

        const q = String(req.query.q || '').trim();
        if (q) {
            conditions.push('(cve_id LIKE ? OR description LIKE ? OR vendor LIKE ? OR product LIKE ? OR cwes LIKE ?)');
            const like = `%${q}%`;
            params.push(like, like, like, like, like);
        }

        const sort = pick(String(req.query.sort || 'cvss').toLowerCase(), ['cvss', 'published', 'cve', 'kev'], 'cvss');
        const orderBy = sort === 'published'
            ? 'published DESC'
            : sort === 'cve'
                ? 'cve_id ASC'
                : sort === 'kev'
                    ? 'in_kev DESC, kev_date_added DESC'
                    // Default. CISA KEV entries are confirmed exploited in the
                    // wild, which outranks a higher CVSS score on a CVE nobody is
                    // known to be using. KEV rows are also the ones still missing
                    // a score, so ordering by CVSS alone buried all 1,729 of them
                    // below every rated row and reported zero CRITICAL findings.
                    : 'in_kev DESC, cvss_score IS NULL ASC, cvss_score DESC, published DESC';

        const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

        const total = db.prepare(`SELECT COUNT(*) AS n FROM vulnerabilities ${where}`).get().n;
        const rows = db.prepare(`
            SELECT cve_id, description, cvss_score, severity, cvss_vector,
                   vendor, product, affected_versions, cwes, references_json,
                   exploit_status, in_kev, ransomware_use, kev_date_added, kev_due_date,
                   required_action, vuln_status, published, modified
            FROM vulnerabilities
            ${where}
            ORDER BY ${orderBy}
            LIMIT ? OFFSET ?
        `).all(...params, limit, offset);

        // Pre-compute stats over the whole table, not the page, so the client's
        // filter chips stay stable while paging.
        res.json({
            vulns: rows,
            total,
            page,
            limit,
            has_more: offset + rows.length < total,
            stats: vulnStats(),
        });
    } catch (err) {
        console.error('Vulns list error:', err);
        res.status(500).json({ error: 'Failed to load vulnerabilities' });
    }
});

// POST /api/intelligence/vulns/sync — force an immediate upstream refresh
router.post('/vulns/sync', async (req, res) => {
    try {
        const result = await syncVulnerabilities();
        logAction('VULN_SYNC', `NVD ${result.nvd} CVEs, KEV ${result.kev} entries`);
        res.json({ success: true, ...result, stats: vulnStats() });
    } catch (err) {
        console.error('Vuln sync error:', err);
        res.status(500).json({ error: 'Vulnerability sync failed' });
    }
});

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
        const days = clampDays(req.query.days, { min: 1, max: 365, fallback: 30 });
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
        const days = clampDays(req.query.days, { min: 1, max: 365, fallback: 14 });
        const trends = getCategoryTrends(days);
        res.json({ trends, days });
    } catch (err) {
        console.error('Category trends error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/trends/regions — Regional hotspot data
router.get('/trends/regions', (req, res) => {
    try {
        const days = clampDays(req.query.days, { min: 1, max: 365, fallback: 14 });
        const regions = getRegionalTrends(days);
        res.json({ regions, days });
    } catch (err) {
        console.error('Regional trends error:', err);
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
        const limit = clampInt(req.query.limit, { min: 2, max: 400, fallback: 100 });

        // Integer halves. `limit / 2` produced 25.5 for odd limits, and a float
        // bound into LIMIT is a SQLite datatype mismatch -> 500.
        const half = Math.max(1, Math.floor(limit / 2));

        // Get recent events as nodes
        const events = db.prepare(`
            SELECT id, title as label, 'EVENT' as type, risk_level, category
            FROM events
            ORDER BY created_at DESC
            LIMIT ?
        `).all(half);

        // Get high-influence entities as nodes.
        // influence_score has never been populated (every row is 0.0), so
        // ordering by it returned an arbitrary ordering. Fall back to degree —
        // the number of graph links — which is real.
        const entities = db.prepare(`
            SELECT e.id, e.name as label, e.type, e.influence_score,
                   (SELECT COUNT(*) FROM nexus_links l WHERE l.source_id = e.id) AS degree
            FROM entities e
            ORDER BY degree DESC, e.name ASC
            LIMIT ?
        `).all(half);

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
        const sector = String(req.params.sector).toUpperCase();

        // These must be a subset of the category CHECK constraint in
        // db/schema.sql. 'ENERGY_SECURITY', 'ECONOMIC_WARFARE' and 'DARK_WEB'
        // were listed here but do not exist in the schema, so those branches
        // matched zero rows and the endpoint returned empty results silently
        // (verified: 0 rows for each).
        const SECTOR_CATEGORIES = {
            DEFENSE: ['WAR', 'MILITARY_MOVEMENT', 'DIPLOMATIC_ESCALATION', 'NUCLEAR_THREAT', 'TERRORISM'],
            ENERGY: ['SANCTIONS', 'DIPLOMATIC_ESCALATION', 'POLITICAL_INSTABILITY'],
            CYBER: ['CYBER_ATTACK', 'TERRORISM'],
        };

        const categories = SECTOR_CATEGORIES[sector];
        if (!categories) {
            return res.status(400).json({
                error: 'Invalid sector',
                valid: Object.keys(SECTOR_CATEGORIES),
            });
        }

        const placeholders = categories.map(() => '?').join(',');
        const events = db.prepare(`
            SELECT * FROM events 
            WHERE category IN (${placeholders})
            ORDER BY created_at DESC
            LIMIT 20
        `).all(...categories);

        res.json({ sector, categories, count: events.length, events });
    } catch (err) {
        console.error('Sector intel error:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/intelligence/predictions — Forecast data
router.get('/predictions', (req, res) => {
    try {
        const db = getDb();
        const limit = clampInt(req.query.limit, { min: 1, max: 50, fallback: 10 });
        
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

        // Dark web — the dashboard shows a signal count, so it needs the real one
        // rather than a number invented on the client.
        const darkWeb = db.prepare(`
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN threat_level = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
                   SUM(CASE WHEN discovered_at > datetime('now', '-24 hours') THEN 1 ELSE 0 END) as last_24h
            FROM dark_web_intel
        `).get();

        // Briefings generated so far today, for the "briefings" KPI.
        const briefings = db.prepare(`
            SELECT COUNT(*) as count FROM global_briefings
            WHERE created_at > datetime('now', 'start of day')
        `).get().count;

        // Count of events that actually carry a written brief. The dashboard used
        // to display a hardcoded "9" for this regardless of what was in the DB.
        const intelReports = db.prepare(`
            SELECT COUNT(*) as count FROM events WHERE ai_brief IS NOT NULL AND ai_brief != ''
        `).get().count;

        // Vulnerability intelligence (NVD + CISA KEV)
        const vulns = vulnStats();

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

        // Recent high-risk events feed the dashboard's crisis tracker. Previously
        // the client showed eight invented headlines on this panel at all times.
        const topThreats = db.prepare(`
            SELECT id, title, category, risk_level, country, created_at
            FROM events
            WHERE risk_level IN ('CRITICAL', 'HIGH')
            ORDER BY
                CASE risk_level WHEN 'CRITICAL' THEN 0 ELSE 1 END ASC,
                created_at DESC
            LIMIT 8
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
                briefings_today: briefings,
                ai_summaries: intelReports,
                dark_web_signals: darkWeb?.total || 0,
                dark_web_critical: darkWeb?.critical || 0,
                dark_web_last_24h: darkWeb?.last_24h || 0,
                active_threats: criticalEvents + highEvents,
            },
            vulnerabilities: vulns,
            category_distribution: categoryDist,
            top_countries: topCountries,
            risk_trend: riskTrend,
            top_threats: topThreats,
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
            // SQLite does not allow a SELECT alias in HAVING, so aggregate with
            // COUNT(*) and repeat it. The previous `HAVING sync_count > 1`
            // raised "no such column: sync_count" and 500'd on every call.
            relatedPairs = db.prepare(`
                SELECT e1.name as entity1, e2.name as entity2, COUNT(*) as sync_count
                FROM nexus_links l1
                JOIN nexus_links l2 ON l1.source_id = l2.source_id AND l1.target_id != l2.target_id
                JOIN entities e1 ON l1.target_id = e1.id
                JOIN entities e2 ON l2.target_id = e2.id
                WHERE l1.source_id IN (${placeholders})
                GROUP BY e1.name, e2.name
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC
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

        // nexus_links are written entity -> target. Verified against the live
        // database: 2323/2323 links have source_id in `entities` and 0 in
        // `events`. `PARTICIPATED_IN` (1693) points at an event;
        // `ASSOCIATED_WITH` (630) points at another entity. The previous query
        // had this inverted, so this endpoint always returned [].
        const timeline = db.prepare(`
            SELECT DISTINCT ev.* 
            FROM nexus_links l
            JOIN events ev ON ev.id = l.target_id 
            WHERE l.source_id = ?
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
