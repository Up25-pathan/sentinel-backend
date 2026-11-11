const express = require('express');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');
const router = express.Router();

// GET /api/watchlists — Get all watchlists
router.get('/', (req, res) => {
    try {
        const db = getDb();
        const watchlists = db.prepare('SELECT * FROM watchlists ORDER BY created_at DESC').all();
        res.json({ watchlists });
    } catch (err) {
        console.error('Error fetching watchlists:', err);
        res.status(500).json({ error: 'Failed to fetch watchlists' });
    }
});

// POST /api/watchlists — Create a new watchlist keyword
router.post('/', (req, res) => {
    const { keyword, threshold } = req.body;

    if (!keyword || typeof keyword !== 'string') {
        return res.status(400).json({ error: 'Keyword is required' });
    }

    // `threshold` used to be passed straight from the body into an INTEGER
    // column with no type check. SQLite applies type ordering across storage
    // classes, so a TEXT value made `count >= wl.threshold` permanently false —
    // the watchlist was created, reported as active, and could never fire.
    let thresholdValue = 3;
    if (threshold !== undefined && threshold !== null && threshold !== '') {
        const parsed = Number(threshold);
        if (!Number.isInteger(parsed) || parsed < 1 || parsed > 1000) {
            return res.status(400).json({ error: 'Threshold must be an integer between 1 and 1000' });
        }
        thresholdValue = parsed;
    }

    try {
        const db = getDb();
        const insertStmt = db.prepare(`
            INSERT INTO watchlists (id, keyword, threshold, is_active)
            VALUES (?, ?, ?, 1)
        `);

        const normalizedKeyword = keyword.toLowerCase().trim();
        if (!normalizedKeyword) {
            return res.status(400).json({ error: 'Keyword is required' });
        }

        insertStmt.run(uuidv4(), normalizedKeyword, thresholdValue);

        const newWatchlist = db.prepare('SELECT * FROM watchlists WHERE keyword = ?').get(normalizedKeyword);
        res.status(201).json(newWatchlist);
    } catch (err) {
        if (err.message.includes('UNIQUE constraint failed')) {
            return res.status(409).json({ error: 'Keyword already exists in watchlist' });
        }
        console.error('Error creating watchlist:', err);
        res.status(500).json({ error: 'Failed to create watchlist' });
    }
});

// DELETE /api/watchlists/:id — Delete a watchlist
router.delete('/:id', (req, res) => {
    try {
        const db = getDb();
        const result = db.prepare('DELETE FROM watchlists WHERE id = ?').run(req.params.id);

        if (result.changes === 0) {
            return res.status(404).json({ error: 'Watchlist not found' });
        }
        res.json({ success: true });
    } catch (err) {
        console.error('Error deleting watchlist:', err);
        res.status(500).json({ error: 'Failed to delete watchlist' });
    }
});

module.exports = router;
