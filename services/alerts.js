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

module.exports = { generateAlerts };
