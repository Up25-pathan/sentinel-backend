/**
 * Export/Backup Service
 * Exports the intelligence database as JSON for backup.
 */
const { getDb } = require('../db');

/**
 * Export all events as JSON
 */
function exportEvents(days = 30) {
    const db = getDb();

    const events = db.prepare(`
        SELECT e.*, GROUP_CONCAT(s.name, '|') as source_names
        FROM events e
        LEFT JOIN sources s ON s.event_id = e.id
        WHERE e.created_at > datetime('now', '-${parseInt(days)} days')
        GROUP BY e.id
        ORDER BY e.created_at DESC
    `).all();

    return {
        exportedAt: new Date().toISOString(),
        totalEvents: events.length,
        periodDays: days,
        events: events.map(e => ({
            id: e.id,
            title: e.title,
            summary: e.summary,
            category: e.category,
            risk_level: e.risk_level,
            location_name: e.location_name,
            latitude: e.latitude,
            longitude: e.longitude,
            is_breaking: e.is_breaking,
            ai_brief: e.ai_brief,
            escalation_score: e.escalation_score,
            second_order_effects: e.second_order_effects,
            bias_analysis: e.bias_analysis,
            sources: e.source_names ? e.source_names.split('|') : [],
            created_at: e.created_at,
        }))
    };
}

/**
 * Export global briefings
 */
function exportBriefings(days = 30) {
    const db = getDb();

    const briefings = db.prepare(`
        SELECT * FROM global_briefings
        WHERE created_at > datetime('now', '-${parseInt(days)} days')
        ORDER BY created_at DESC
    `).all();

    return {
        exportedAt: new Date().toISOString(),
        totalBriefings: briefings.length,
        briefings: briefings.map(b => ({
            id: b.id,
            data: b.briefing_data ? JSON.parse(b.briefing_data) : null,
            riskScore: b.global_risk_score,
            created_at: b.created_at,
        }))
    };
}

/**
 * Full database export
 */
function exportAll(days = 30) {
    return {
        sentinel_backup: true,
        version: '1.0.0',
        exportedAt: new Date().toISOString(),
        events: exportEvents(days),
        briefings: exportBriefings(days),
    };
}

module.exports = { exportEvents, exportBriefings, exportAll };
