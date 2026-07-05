const { getDb } = require('./db');

const db = getDb();
const events = db.prepare(`SELECT * FROM events LIMIT 1`).all();

const enriched = events.map(event => {
    const sourceCount = db.prepare('SELECT COUNT(*) as count FROM sources WHERE event_id = ?').get(event.id);
    return {
        ...event,
        entities: event.entities_json ? JSON.parse(event.entities_json) : null,
        source_count: sourceCount.count
    };
});

console.log(JSON.stringify(enriched[0], null, 2));
