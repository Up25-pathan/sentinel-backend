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

    if (!keyword) {
        return res.status(400).json({ error: 'Keyword is required' });
    }

    try {
        const db = getDb();
        const insertStmt = db.prepare(`
            INSERT INTO watchlists (id, keyword, threshold, is_active)
            VALUES (?, ?, ?, 1)
        `);

        insertStmt.run(uuidv4(), keyword.toLowerCase().trim(), threshold || 3);

        const newWatchlist = db.prepare('SELECT * FROM watchlists WHERE keyword = ?').get(keyword.toLowerCase().trim());
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
