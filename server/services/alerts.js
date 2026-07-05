/**
 * Alert Generation Service
 * Creates alerts for breaking and critical geopolitical events
 */
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

/**
 * Generate alerts for new critical/breaking events
 */
function generateAlerts() {
    const db = getDb();

    // Find events that should have alerts but don't
    const events = db.prepare(`
        SELECT e.* FROM events e
        WHERE (e.risk_level IN ('CRITICAL', 'HIGH') OR e.is_breaking = 1)
        AND e.id NOT IN (SELECT event_id FROM alerts)
        ORDER BY e.created_at DESC
    `).all();

    if (events.length === 0) {
        return 0;
    }

    const insertAlert = db.prepare(`
        INSERT INTO alerts (id, event_id, type, message, is_read, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
    `);

    let alertCount = 0;

    const transaction = db.transaction(() => {
        for (const event of events) {
            let type = 'UPDATE';
            let emoji = 'ℹ️';

            if (event.is_breaking) {
                type = 'BREAKING';
                emoji = '🔴';
            } else if (event.risk_level === 'CRITICAL') {
                type = 'CRITICAL';
                emoji = '🔴';
            } else if (event.risk_level === 'HIGH') {
                type = 'ESCALATION';
                emoji = '⚠️';
            }

            const message = `${emoji} ${type}: ${event.title}`;
            const now = new Date().toISOString().replace('T', ' ').replace('Z', '');

            insertAlert.run(uuidv4(), event.id, type, message, now);
            alertCount++;
        }
    });

    transaction();

    if (alertCount > 0) {
        console.log(`🚨 Generated ${alertCount} new alerts.`);
    }
    return alertCount;
}

/**
 * Check recent events against user watchlists
 */
function checkWatchlists() {
    const db = getDb();

    // Get all active watchlists
    const watchlists = db.prepare('SELECT * FROM watchlists WHERE is_active = 1').all();
    if (watchlists.length === 0) return 0;

    let triggerCount = 0;
    const now = new Date();
    // Look back 24 hours for mentions
    const since = new Date(now.getTime() - (24 * 60 * 60 * 1000)).toISOString().replace('T', ' ').replace('Z', '');

    const countStmt = db.prepare(`
        SELECT COUNT(*) as count FROM events 
        WHERE (LOWER(title) LIKE '%' || ? || '%' OR LOWER(summary) LIKE '%' || ? || '%')
        AND created_at >= ?
    `);

    const updateWatchlist = db.prepare('UPDATE watchlists SET last_triggered_at = ? WHERE id = ?');
    const insertAlert = db.prepare(`
        INSERT INTO alerts (id, event_id, type, message, is_read, created_at)
        VALUES (?, ?, 'CRITICAL', ?, 0, ?)
    `);

    for (const wl of watchlists) {
        const result = countStmt.get(wl.keyword, wl.keyword, since);

        // If mentions exceed threshold and hasn't been triggered in the last hour
        const lastTriggered = wl.last_triggered_at ? new Date(wl.last_triggered_at) : new Date(0);
        const hoursSinceTrigger = (now - lastTriggered) / (1000 * 60 * 60);

        if (result.count >= wl.threshold && hoursSinceTrigger > 1) {
            // Find the most recent event matching this to attach to
            const recentEvent = db.prepare(`
                SELECT id FROM events 
                WHERE (LOWER(title) LIKE '%' || ? || '%' OR LOWER(summary) LIKE '%' || ? || '%')
                ORDER BY created_at DESC LIMIT 1
            `).get(wl.keyword, wl.keyword);

            if (recentEvent) {
                const message = `🎯 WATCHLIST ALERT: Keyword "${wl.keyword}" mentioned ${result.count} times in last 24h.`;
                const nowStr = now.toISOString().replace('T', ' ').replace('Z', '');

                insertAlert.run(uuidv4(), recentEvent.id, message, nowStr);
                updateWatchlist.run(nowStr, wl.id);

                console.log(`🎯 Triggered watchlist alert for: ${wl.keyword}`);
                triggerCount++;
            }
        }
    }

    return triggerCount;
}

module.exports = { generateAlerts, checkWatchlists };
