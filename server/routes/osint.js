const express = require('express');
const { getDb } = require('../db');
const { paginate } = require('../lib/query');
const router = express.Router();

// GET /api/osint — List raw OSINT events (Telegram, X, etc)
router.get('/', (req, res) => {
    try {
        const db = getDb();
        const platform = req.query.platform; // Optional: 'Telegram' or 'X'

        const { limit, page, offset } = paginate(req.query, { defaultLimit: 20, maxLimit: 200 });

        let queryStr = `SELECT * FROM raw_articles WHERE source_name LIKE 'OSINT:%'`;
        let params = [];

        if (platform) {
            queryStr += ` AND source_name LIKE ?`;
            params.push(`%${platform}%`);
        }

        queryStr += ` ORDER BY published_at DESC LIMIT ? OFFSET ?`;
        params.push(limit, offset);

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
                page,
                limit,
                total: countRow.total,
                pages: Math.max(1, Math.ceil(countRow.total / limit)),
            },
        });
    } catch (err) {
        console.error('Error fetching OSINT:', err);
        res.status(500).json({ error: 'Failed to fetch OSINT data' });
    }
});

module.exports = router;
