const axios = require('axios');
const cheerio = require('cheerio');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

// Public Intelligence / Conflict Telegram Channels
const TARGET_CHANNELS = [
    'DDGeopolitics', 'IntelRepublic', 'osint_defender',
    'warmonitors', 'tpyxnews', 'clashreport',
    'milinfolive', 'rybar', 'DonbassDevushka'
];

/**
 * Enhanced OSINT Scraper 
 * Logic for "Signal Strength" based on tactical indicators
 */
async function scrapeTelegramChannels() {
    console.log('\n🕵️ Starting Tactical OSINT: Telegram...');
    const db = getDb();
    const insertStmt = db.prepare(`
        INSERT OR IGNORE INTO raw_articles (id, title, description, url, source_name, published_at, processed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    `);

    const tacticalKeywords = ['SITREP', 'BREAKING', 'FLASH', 'CONFIRMED', 'EXPLOSION', 'STRIKE', 'MOBILIZATION'];
    let totalScraped = 0;

    for (const channel of TARGET_CHANNELS) {
        try {
            const url = `https://t.me/s/${channel}`;
            const response = await axios.get(url, {
                headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36' }
            });

            const $ = cheerio.load(response.data);
            const messages = $('.tgme_widget_message_wrap').toArray().slice(-15); 

            for (const msg of messages) {
                const text = $(msg).find('.tgme_widget_message_text').text().trim();
                const timeStr = $(msg).find('time').attr('datetime');
                const postUrl = $(msg).find('.tgme_widget_message_date').attr('href');

                if (text && text.length > 20) {
                    // Calculate "Signal Strength" (simple keyword density for now)
                    const signalLevel = tacticalKeywords.filter(k => text.toUpperCase().includes(k)).length;
                    const tacticalPrefix = signalLevel > 1 ? '[TACTICAL] ' : '';

                    const title = tacticalPrefix + text.split('\n')[0].substring(0, 80) + '...';

                    const result = insertStmt.run(
                        uuidv4(),
                        title,
                        text,
                        postUrl || url,
                        `OSINT: @${channel}`,
                        timeStr || new Date().toISOString()
                    );
                    if (result.changes > 0) totalScraped++;
                }
            }
        } catch (err) {
            console.warn(`  ⚠️ Telegram @${channel} failure: ${err.message}`);
        }
    }

    console.log(`✅ OSINT complete: ${totalScraped} updates captured.`);
    return totalScraped;
}

module.exports = { scrapeTelegramChannels };
