const axios = require('axios');
const cheerio = require('cheerio');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

// Public Intelligence / Conflict Telegram Channels
const TARGET_CHANNELS = [
    'DDGeopolitics',
    'IntelRepublic',
    'osint_defender',
    'warmonitors',
    'tpyxnews'
];

async function scrapeTelegramChannels() {
    console.log('\n🕵️ Starting OSINT Telegram Scraper...');
    const db = getDb();
    const insertStmt = db.prepare(`
        INSERT OR IGNORE INTO raw_articles (id, title, description, url, source_name, published_at, processed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    `);

    let totalScraped = 0;

    for (const channel of TARGET_CHANNELS) {
        try {
            // Using t.me public preview pages for fast, API-free scraping of recent posts
            const url = `https://t.me/s/${channel}`;
            const response = await axios.get(url, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            });

            const $ = cheerio.load(response.data);
            const messages = $('.tgme_widget_message_wrap').toArray().slice(-10); // get last 10 messages

            for (const msg of messages) {
                const text = $(msg).find('.tgme_widget_message_text').text().trim();
                const timeStr = $(msg).find('time').attr('datetime');
                const postUrl = $(msg).find('.tgme_widget_message_date').attr('href');

                if (text && text.length > 30) {
                    const title = text.split('\n')[0].substring(0, 80) + '...';

                    const result = insertStmt.run(
                        uuidv4(),
                        title,
                        text,
                        postUrl || url,
                        `OSINT: Telegram (@${channel})`,
                        timeStr || new Date().toISOString()
                    );

                    if (result.changes > 0) totalScraped++;
                }
            }
            console.log(`  📱 @${channel}: checked latest posts`);
        } catch (err) {
            console.warn(`  ⚠️ Failed to scrape Telegram channel @${channel}: ${err.message}`);
        }
    }

    console.log(`✅ OSINT scrape complete: ${totalScraped} new tactical updates found.\n`);
    return totalScraped;
}

module.exports = { scrapeTelegramChannels };
