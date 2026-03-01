/**
 * News Ingestion Service
 * Collects geopolitical news from RSS feeds and NewsAPI
 */
const RSSParser = require('rss-parser');
const axios = require('axios');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');
require('dotenv').config();

const rssParser = new RSSParser();

// Major geopolitical news RSS feeds
const RSS_FEEDS = [
    { name: 'Reuters World', url: 'https://feeds.reuters.com/Reuters/worldNews' },
    { name: 'AP Top News', url: 'https://rsshub.app/apnews/topics/apf-topnews' },
    { name: 'BBC World', url: 'http://feeds.bbci.co.uk/news/world/rss.xml' },
    { name: 'Al Jazeera', url: 'https://www.aljazeera.com/xml/rss/all.xml' },
    { name: 'France 24', url: 'https://www.france24.com/en/rss' },
];

// Geopolitical keywords for filtering
const GEO_KEYWORDS = [
    'military', 'conflict', 'war', 'sanctions', 'coup', 'nuclear',
    'missile', 'troops', 'invasion', 'escalation', 'diplomacy',
    'territory', 'border', 'defense', 'strike', 'attack', 'rebel',
    'insurgent', 'ceasefire', 'peace talks', 'arms', 'navy',
    'airforce', 'deployment', 'alliance', 'nato', 'un security',
    'embargo', 'threat', 'crisis', 'regime', 'protest', 'uprising',
    'intelligence', 'espionage', 'cyber attack', 'drone', 'artillery',
    'humanitarian', 'refugee', 'genocide', 'chemical weapons',
    'biological weapons', 'assassination', 'hostage', 'terrorism'
];

/**
 * Check if an article is geopolitically relevant based on keywords
 */
function isGeopolitical(title = '', description = '') {
    const text = `${title} ${description}`.toLowerCase();
    return GEO_KEYWORDS.some(keyword => text.includes(keyword));
}

/**
 * Ingest news from RSS feeds
 */
async function ingestFromRSS() {
    const db = getDb();
    const insertStmt = db.prepare(`
        INSERT OR IGNORE INTO raw_articles (id, title, description, url, source_name, image_url, published_at, processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    `);

    let totalIngested = 0;

    for (const feed of RSS_FEEDS) {
        try {
            const parsed = await rssParser.parseURL(feed.url);
            const articles = parsed.items || [];

            for (const article of articles) {
                if (isGeopolitical(article.title, article.contentSnippet || article.content)) {
                    const result = insertStmt.run(
                        uuidv4(),
                        article.title || 'Unknown Title',
                        article.contentSnippet || article.content || '',
                        article.link || '',
                        feed.name,
                        article.enclosure?.url || null,
                        article.pubDate || new Date().toISOString(),
                    );
                    if (result.changes > 0) totalIngested++;
                }
            }
            console.log(`  📡 ${feed.name}: checked ${articles.length} articles`);
        } catch (err) {
            console.warn(`  ⚠️ RSS feed failed (${feed.name}):`, err.message);
        }
    }

    return totalIngested;
}

/**
 * Ingest news from NewsAPI
 */
async function ingestFromNewsAPI() {
    const apiKey = process.env.NEWS_API_KEY;
    if (!apiKey) {
        console.log('  ℹ️ NewsAPI key not configured, skipping.');
        return 0;
    }

    const db = getDb();
    const insertStmt = db.prepare(`
        INSERT OR IGNORE INTO raw_articles (id, title, description, url, source_name, image_url, published_at, processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    `);

    let totalIngested = 0;
    const queries = ['geopolitics', 'military conflict', 'international sanctions', 'political coup'];

    for (const q of queries) {
        try {
            const response = await axios.get('https://newsapi.org/v2/everything', {
                params: {
                    q,
                    language: 'en',
                    sortBy: 'publishedAt',
                    pageSize: 20,
                    apiKey
                }
            });

            const articles = response.data.articles || [];
            for (const article of articles) {
                const result = insertStmt.run(
                    uuidv4(),
                    article.title || 'Unknown',
                    article.description || '',
                    article.url || '',
                    article.source?.name || 'NewsAPI',
                    article.urlToImage || null,
                    article.publishedAt || new Date().toISOString(),
                );
                if (result.changes > 0) totalIngested++;
            }
        } catch (err) {
            console.warn(`  ⚠️ NewsAPI query failed (${q}):`, err.message);
        }
    }

    return totalIngested;
}

/**
 * Main ingestion function — runs all sources
 */
async function ingestNews() {
    console.log('\n📰 Starting news ingestion...');
    const startTime = Date.now();

    const rssCount = await ingestFromRSS();
    const newsApiCount = await ingestFromNewsAPI();

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    const total = rssCount + newsApiCount;

    console.log(`✅ Ingestion complete: ${total} new articles in ${elapsed}s (RSS: ${rssCount}, NewsAPI: ${newsApiCount})\n`);
    return { total, rss: rssCount, newsApi: newsApiCount, elapsed };
}

module.exports = { ingestNews, isGeopolitical };
