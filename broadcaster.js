const { getDb } = require('./db');
const eventBus = require('./eventbus');

/**
 * Poll for newly inserted events/alerts and emit them on the event bus.
 *
 * High-water marks use the implicit SQLite `rowid` rather than `created_at`.
 * `created_at` is TEXT in the format `datetime('now')` produces
 * ("2026-09-30 09:15:00.000"), which is NOT lexicographically comparable with
 * the ISO-8601 form ("2026-09-30T09:15:00.000Z") because ' ' (0x20) < 'T'
 * (0x54). Comparing the two as strings silently matched nothing, so no event
 * was ever broadcast. `rowid` is a monotonic INTEGER and has no such ambiguity.
 */

const POLL_INTERVAL_MS = 3000;

let lastEventRowid = 0;
let lastAlertRowid = 0;
let started = false;
let pollTimer = null;
let consecutiveErrors = 0;
let errorLogged = false;

function maxRowid(table) {
    const db = getDb();
    const row = db.prepare(`SELECT COALESCE(MAX(rowid), 0) AS m FROM ${table}`).get();
    return row.m;
}

function resetHighWaterMarks() {
    try {
        lastEventRowid = maxRowid('events');
        lastAlertRowid = maxRowid('alerts');
    } catch (err) {
        // Table may not exist yet on a cold database.
        lastEventRowid = 0;
        lastAlertRowid = 0;
    }
}

function poll() {
    if (!started) return;

    let db;
    try {
        db = getDb();
    } catch (err) {
        reportError(err, 'database unavailable');
        return;
    }

    try {
        const newEvents = db
            .prepare('SELECT * FROM events WHERE rowid > ? ORDER BY rowid ASC')
            .all(lastEventRowid);

        for (const event of newEvents) {
            lastEventRowid = event.rowid;
            eventBus.emit('new_event', event);
        }

        const newAlerts = db
            .prepare(
                `SELECT a.*, e.title as event_title FROM alerts a
                 LEFT JOIN events e ON a.event_id = e.id
                 WHERE a.rowid > ? ORDER BY a.rowid ASC`
            )
            .all(lastAlertRowid);

        for (const alert of newAlerts) {
            lastAlertRowid = alert.rowid;
            eventBus.emit('new_alert', alert);
        }

        if (consecutiveErrors > 0) {
            console.log(`📢 Broadcaster recovered after ${consecutiveErrors} failed poll(s).`);
        }
        consecutiveErrors = 0;
        errorLogged = false;
    } catch (err) {
        reportError(err, 'poll failed');
    }
}

/**
 * Log the first failure in full (with stack), then stay quiet until recovery.
 * A permanently broken query used to be invisible forever behind an empty
 * catch block.
 */
function reportError(err, context) {
    consecutiveErrors++;
    if (!errorLogged) {
        console.error(`❌ Broadcaster ${context}: ${err.message}`);
        if (err.stack) console.error(err.stack);
        errorLogged = true;
    }
}

function startBroadcaster() {
    if (started) {
        console.warn('⚠️  Broadcaster already running.');
        return;
    }

    resetHighWaterMarks();
    started = true;

    pollTimer = setInterval(poll, POLL_INTERVAL_MS);

    console.log(
        `📢 Broadcaster started — polling events (rowid > ${lastEventRowid}) ` +
        `and alerts (rowid > ${lastAlertRowid}) every ${POLL_INTERVAL_MS / 1000}s`
    );
}

function stopBroadcaster() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
    started = false;
}

/**
 * Diagnostic snapshot — surfaced on /api/health so a silently dead
 * broadcaster cannot hide again.
 */
function broadcasterStatus() {
    return {
        running: started,
        intervalMs: POLL_INTERVAL_MS,
        lastEventRowid,
        lastAlertRowid,
        consecutiveErrors,
    };
}

module.exports = { startBroadcaster, stopBroadcaster, broadcasterStatus };
