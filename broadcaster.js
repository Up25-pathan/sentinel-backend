const { getDb } = require('./db');
const eventBus = require('./eventbus');

let lastEventCheck = new Date().toISOString();
let lastAlertCheck = new Date().toISOString();

function poll() {
    try {
        const db = getDb();

        const newEvents = db.prepare(
            `SELECT * FROM events WHERE created_at > ? ORDER BY created_at ASC`
        ).all(lastEventCheck);

        if (newEvents.length > 0) {
            lastEventCheck = newEvents[newEvents.length - 1].created_at;
            for (const event of newEvents) {
                eventBus.emit('new_event', event);
            }
        }

        const newAlerts = db.prepare(
            `SELECT a.*, e.title as event_title FROM alerts a
             JOIN events e ON a.event_id = e.id
             WHERE a.created_at > ? ORDER BY a.created_at ASC`
        ).all(lastAlertCheck);

        if (newAlerts.length > 0) {
            lastAlertCheck = newAlerts[newAlerts.length - 1].created_at;
            for (const alert of newAlerts) {
                eventBus.emit('new_alert', alert);
            }
        }
    } catch (err) {
        // DB might not be ready yet
    }
}

function startBroadcaster() {
    lastEventCheck = new Date().toISOString();
    lastAlertCheck = new Date().toISOString();
    setInterval(poll, 3000);
    console.log('📢 Broadcaster started — polling for new events every 3s');
}

module.exports = { startBroadcaster };
