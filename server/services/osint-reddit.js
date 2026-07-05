/**
 * Reddit OSINT Scraper
 * Scrapes public Reddit JSON API for geopolitical intelligence from key subreddits.
 * No API key needed — uses Reddit's public .json endpoints.
 */
const axios = require('axios');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');
const { isGeopolitical } = require('./ingestion');

// Target subreddits for geopolitical intelligence
const TARGET_SUBREDDITS = [
    'geopolitics',
    'worldnews',
    'IntelligenceNews',
    'OSINT',
    'UkrainianConflict'
];

async function scrapeReddit() {
    console.log('\n📡 Starting OSINT Reddit Scraper...');
    const db = getDb();
    const insertStmt = db.prepare(`
        INSERT OR IGNORE INTO raw_articles (id, title, description, url, source_name, published_at, processed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    `);

    let totalScraped = 0;

    for (const subreddit of TARGET_SUBREDDITS) {
        try {
            const url = `https://www.reddit.com/r/${subreddit}/hot.json?limit=15`;
            const response = await axios.get(url, {
                headers: {
                    'User-Agent': 'SentinelIntelBot/1.0 (private intelligence platform)'
                },
                timeout: 8000
            });

            const posts = response.data?.data?.children || [];

            for (const post of posts) {
                const data = post.data;

                // Skip pinned/stickied posts and non-text posts
                if (data.stickied || data.is_video) continue;

                const title = data.title || '';
                const selftext = data.selftext || '';
                const description = selftext.substring(0, 500) || title;

                // Only process geopolitically relevant posts
                if (!isGeopolitical(title, description)) continue;

                // Skip very short titles (likely memes or low-effort)
                if (title.length < 25) continue;

                const publishedAt = data.created_utc
                    ? new Date(data.created_utc * 1000).toISOString()
                    : new Date().toISOString();

                const postUrl = data.url_overridden_by_dest || `https://reddit.com${data.permalink}`;

                const result = insertStmt.run(
                    uuidv4(),
                    title.length > 100 ? title.substring(0, 100) + '...' : title,
                    description,
                    postUrl,
                    `OSINT: Reddit (r/${subreddit})`,
                    publishedAt
                );

                if (result.changes > 0) totalScraped++;
            }
            console.log(`  📡 r/${subreddit}: checked ${posts.length} posts`);
        } catch (err) {
            console.warn(`  ⚠️ Failed to scrape r/${subreddit}: ${err.message}`);
        }
    }

    console.log(`✅ Reddit OSINT scrape complete: ${totalScraped} new posts found.\n`);
    return totalScraped;
}

module.exports = { scrapeReddit };
