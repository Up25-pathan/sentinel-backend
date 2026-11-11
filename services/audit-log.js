/**
 * Shared Audit Log Service
 * Persists system/client actions into the server-side audit_log table
 * so every SENTINEL client (PC, Mobile) sees the same history.
 */
const { getDb } = require('../db');

function logAction(action, details = '') {
    try {
        const db = getDb();
        db.prepare(
            'INSERT INTO audit_log (timestamp, action, details) VALUES (datetime(\'now\'), ?, ?)'
        ).run(String(action).slice(0, 200), String(details).slice(0, 2000));
    } catch (err) {
        console.error('Audit log write error:', err.message);
    }
}

function getLatestLogs(limit = 100) {
    try {
        const db = getDb();
        return db.prepare(
            'SELECT id, timestamp, action, details FROM audit_log ORDER BY id DESC LIMIT ?'
        ).all(Math.min(Math.max(parseInt(limit) || 100, 1), 500));
    } catch (err) {
        console.error('Audit log read error:', err.message);
        return [];
    }
}

module.exports = { logAction, getLatestLogs };