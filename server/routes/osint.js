const express = require('express');
const { getDb } = require('../db');
const router = express.Router();

// GET /api/osint — List raw OSINT events (Telegram, X, etc)
router.get('/', (req, res) => {
    try {
        const db = getDb();
        const {
            page = 1,
            limit = 20,
            platform // Optional: 'Telegram' or 'X'
        } = req.query;

        const offset = (parseInt(page) - 1) * parseInt(limit);

        let queryStr = `SELECT * FROM raw_articles WHERE source_name LIKE 'OSINT:%'`;
        let params = [];

        if (platform) {
            queryStr += ` AND source_name LIKE ?`;
            params.push(`%${platform}%`);
        }

        queryStr += ` ORDER BY published_at DESC LIMIT ? OFFSET ?`;
        params.push(parseInt(limit), offset);

        const articles = db.prepare(queryStr).all(...params);

        // Get total count
        let countQuery = `SELECT COUNT(*) as total FROM raw_articles WHERE source_name LIKE 'OSINT:%'`;
        let countParams = [];
        if (platform) {
            countQuery += ` AND source_name LIKE ?`;
            countParams.push(`%${platform}%`);
        }
        const countRow = db.prepare(countQuery).get(...countParams);

        res.json({
            data: articles,
            pagination: {
                page: parseInt(page),
                limit: parseInt(limit),
                total: countRow.total,
                pages: Math.ceil(countRow.total / parseInt(limit))
            }
        });
    } catch (err) {
        console.error('Error fetching OSINT:', err);
        res.status(500).json({ error: 'Failed to fetch OSINT data' });
    }
});

module.exports = router;
