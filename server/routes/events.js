const express = require('express');
const { getDb } = require('../db');
const router = express.Router();

// GET /api/events — List events (paginated, filterable)
router.get('/', (req, res) => {
    try {
        const db = getDb();
        const {
            page = 1,
            limit = 20,
            category,
            risk_level,
            is_breaking,
            sort = 'created_at',
            order = 'DESC'
        } = req.query;

        const offset = (parseInt(page) - 1) * parseInt(limit);
        let where = [`NOT EXISTS (SELECT 1 FROM sources s WHERE s.event_id = events.id AND s.name LIKE 'OSINT:%')`];
        let params = [];

        if (category) {
            where.push('category = ?');
            params.push(category);
        }
        if (risk_level) {
            where.push('risk_level = ?');
            params.push(risk_level);
        }
        if (is_breaking !== undefined) {
            where.push('is_breaking = ?');
            params.push(parseInt(is_breaking));
        }

        const whereClause = where.length > 0 ? `WHERE ${where.join(' AND ')}` : '';
        const allowedSorts = ['created_at', 'risk_level', 'category'];
        const sortCol = allowedSorts.includes(sort) ? sort : 'created_at';
        const sortOrder = order.toUpperCase() === 'ASC' ? 'ASC' : 'DESC';

        // Get total count
        const countRow = db.prepare(`SELECT COUNT(*) as total FROM events ${whereClause}`).get(...params);

        // Get events
        const events = db.prepare(`
            SELECT * FROM events ${whereClause} 
            ORDER BY is_breaking DESC, ${sortCol} ${sortOrder}
            LIMIT ? OFFSET ?
        `).all(...params, parseInt(limit), offset);

        // Get source counts for each event
        const enriched = events.map(event => {
            const sourceCount = db.prepare('SELECT COUNT(*) as count FROM sources WHERE event_id = ?').get(event.id);

            let parsedEntities = null;
            if (event.entities_json) {
                try { parsedEntities = JSON.parse(event.entities_json); }
                catch (e) { console.warn(`Failed to parse entities for event ${event.id}`); }
            }

            let parsedImages = [];
            if (event.images_json) {
                try { parsedImages = JSON.parse(event.images_json); }
                catch (e) { console.warn(`Failed to parse images for event ${event.id}`); }
            }

            return {
                ...event,
                images_json: parsedImages,
                entities: parsedEntities,
                source_count: sourceCount.count
            };
        });

        res.json({
            events: enriched,
            pagination: {
                page: parseInt(page),
                limit: parseInt(limit),
                total: countRow.total,
                pages: Math.ceil(countRow.total / parseInt(limit))
            }
        });
    } catch (err) {
        console.error('Error fetching events:', err);
        res.status(500).json({ error: 'Failed to fetch events', details: err.message, stack: err.stack });
    }
});

// GET /api/events/breaking — Current breaking events
router.get('/breaking', (req, res) => {
    try {
        const db = getDb();
        const events = db.prepare(`
            SELECT * FROM events 
            WHERE is_breaking = 1 
            ORDER BY created_at DESC
            LIMIT 10
        `).all();

        res.json({ events });
    } catch (err) {
        console.error('Error fetching breaking events:', err);
        res.status(500).json({ error: 'Failed to fetch breaking events' });
    }
});

// GET /api/events/search — Search events
router.get('/search', (req, res) => {
    try {
        const db = getDb();
        const { q, category, risk_level, limit = 20 } = req.query;

        if (!q) {
            return res.status(400).json({ error: 'Search query (q) is required' });
        }

        let where = [`(title LIKE ? OR summary LIKE ? OR ai_brief LIKE ? OR location_name LIKE ? OR country LIKE ?)`];
        let params = Array(5).fill(`%${q}%`);

        if (category) {
            where.push('category = ?');
            params.push(category);
        }
        if (risk_level) {
            where.push('risk_level = ?');
            params.push(risk_level);
        }

        const events = db.prepare(`
            SELECT * FROM events 
            WHERE ${where.join(' AND ')}
            ORDER BY created_at DESC
            LIMIT ?
        `).all(...params, parseInt(limit));

        res.json({ events, query: q, count: events.length });
    } catch (err) {
        console.error('Error searching events:', err);
        res.status(500).json({ error: 'Search failed' });
    }
});

// GET /api/events/:id — Single event with full details
router.get('/:id', (req, res) => {
    try {
        const db = getDb();
        const event = db.prepare('SELECT * FROM events WHERE id = ?').get(req.params.id);

        if (!event) {
            return res.status(404).json({ error: 'Event not found' });
        }

        const sources = db.prepare('SELECT * FROM sources WHERE event_id = ? ORDER BY credibility DESC').all(event.id);
        const alerts = db.prepare('SELECT * FROM alerts WHERE event_id = ? ORDER BY created_at DESC').all(event.id);

        // Get related events (same category or nearby location)
        const related = db.prepare(`
            SELECT id, title, category, risk_level, location_name, created_at 
            FROM events 
            WHERE id != ? AND (category = ? OR country = ?)
            ORDER BY created_at DESC
            LIMIT 5
        `).all(event.id, event.category, event.country);

        let parsedEntities = null;
        if (event.entities_json) {
            try { parsedEntities = JSON.parse(event.entities_json); }
            catch (e) { console.warn(`Failed to parse entities for event ${event.id}`); }
        }

        let parsedImages = [];
        if (event.images_json) {
            try { parsedImages = JSON.parse(event.images_json); }
            catch (e) { console.warn(`Failed to parse images for event ${event.id}`); }
        }

        res.json({
            ...event,
            images_json: parsedImages,
            entities: parsedEntities,
            sources,
            alerts,
            related
        });
    } catch (err) {
        console.error('Error fetching event:', err);
        res.status(500).json({ error: 'Failed to fetch event' });
    }
});

module.exports = router;
