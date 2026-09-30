/**
 * Export/Backup Service
 * Exports the intelligence database as JSON for backup.
 */
const { getDb } = require('../db');
const { clampDays, daysModifier } = require('../lib/query');

/**
 * Export all events as JSON
 */
function exportEvents(days = 30) {
    const db = getDb();
    const window = clampDays(days);

    // The columns are `lat` / `lng` (see db/schema.sql). This previously
    // selected `e.latitude` / `e.longitude`, which do not exist, so every
    // exported event silently carried latitude: undefined, longitude: undefined
    // and backups had no coordinates at all.
    const events = db.prepare(`
        SELECT e.*, GROUP_CONCAT(s.name, '|') as source_names
        FROM events e
        LEFT JOIN sources s ON s.event_id = e.id
        WHERE e.created_at > datetime('now', ?)
        GROUP BY e.id
        ORDER BY e.created_at DESC
    `).all(daysModifier(window));

    return {
        exportedAt: new Date().toISOString(),
        totalEvents: events.length,
        periodDays: window,
        events: events.map(e => ({
            id: e.id,
            title: e.title,
            summary: e.summary,
            category: e.category,
            risk_level: e.risk_level,
            location_name: e.location_name,
            country: e.country,
            lat: e.lat,
            lng: e.lng,
            is_breaking: e.is_breaking,
            ai_brief: e.ai_brief,
            escalation_score: e.escalation_score,
            second_order_effects: e.second_order_effects,
            bias_analysis: e.bias_analysis,
            cluster_id: e.cluster_id,
            entities: e.entities_json ? safeParse(e.entities_json) : null,
            images: e.images_json ? safeParse(e.images_json) : null,
            sources: e.source_names ? e.source_names.split('|') : [],
            created_at: e.created_at,
        }))
    };
}

function safeParse(json) {
    try {
        return JSON.parse(json);
    } catch {
        return null;
    }
}

/**
 * Export global briefings
 */
function exportBriefings(days = 30) {
    const db = getDb();
    const window = clampDays(days);

    const briefings = db.prepare(`
        SELECT * FROM global_briefings
        WHERE created_at > datetime('now', ?)
        ORDER BY created_at DESC
    `).all(daysModifier(window));

    return {
        exportedAt: new Date().toISOString(),
        totalBriefings: briefings.length,
        periodDays: window,
        briefings: briefings.map(b => ({
            id: b.id,
            data: safeParse(b.briefing_data),
            majorSituations: safeParse(b.major_situations_json),
            macroPredictions: safeParse(b.macro_predictions_json),
            riskScore: b.global_risk_score,
            created_at: b.created_at,
        }))
    };
}

/**
 * Export the relational graph as well. Without these, a restore loses the
 * entire Nexus layer, which is the most expensive data to rebuild.
 */
function exportGraph() {
    const db = getDb();

    const entities = db.prepare('SELECT * FROM entities').all();
    const links = db.prepare('SELECT * FROM nexus_links').all();
    const predictions = db.prepare('SELECT * FROM predictions').all();
    const darkWeb = db.prepare('SELECT * FROM dark_web_intel').all();
    const watchlists = db.prepare('SELECT * FROM watchlists').all();
    const assets = db.prepare('SELECT * FROM assets').all();

    return {
        entities,
        nexusLinks: links,
        predictions,
        darkWebIntel: darkWeb,
        watchlists,
        assets,
    };
}

/**
 * Full database export
 */
function exportAll(days = 30) {
    return {
        sentinel_backup: true,
        version: '1.1.0',
        exportedAt: new Date().toISOString(),
        events: exportEvents(days),
        briefings: exportBriefings(days),
        graph: exportGraph(),
    };
}

module.exports = { exportEvents, exportBriefings, exportGraph, exportAll };
