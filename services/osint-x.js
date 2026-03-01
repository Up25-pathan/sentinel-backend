const axios = require('axios');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

// Known high-value X/Twitter Intelligence Accounts
const TARGET_ACCOUNTS = [
    'Faytuks',
    'spectatorindex',
    'BNONews',
    'ragipsoylu',
    'clashreport'
];

async function scrapeXAccounts() {
    console.log('\n🐦 Starting OSINT X/Twitter Scraper...');
    const db = getDb();
    const insertStmt = db.prepare(`
        INSERT OR IGNORE INTO raw_articles (id, title, description, url, source_name, published_at, processed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    `);

    let totalScraped = 0;

    // Use Nitter (open-source alternative frontend) to bypass X API limitations and logins
    // We use a public Nitter instance list to avoid rate limits
    const NITTER_INSTANCES = [
        'https://nitter.cz',
        'https://nitter.poast.org',
        'https://nitter.catsarch.com',
        'https://nitter.salastil.com'
    ];

    for (const account of TARGET_ACCOUNTS) {
        let success = false;

        // Try up to 3 different instances for each account if we hit a 403
        for (let i = 0; i < NITTER_INSTANCES.length && !success; i++) {
            const baseUrl = NITTER_INSTANCES[i];
            try {
                // Fetch the RSS feed provided by Nitter for the user
                const url = `${baseUrl}/${account}/rss`;
                const response = await axios.get(url, {
                    timeout: 8000,
                    headers: {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/rss+xml, application/xml;q=0.9, text/xml;q=0.8'
                    }
                });

                // Parse RSS out of Nitter XML
                // We use simple regex for speed instead of heavy XML parsers for this specific layout
                const items = response.data.match(/<item>([\s\S]*?)<\/item>/g) || [];

                for (const item of items.slice(0, 10)) { // Get top 10 tweets
                    const titleMatch = item.match(/<title>([\s\S]*?)<\/title>/);
                    const descMatch = item.match(/<description>([\s\S]*?)<\/description>/);
                    const linkMatch = item.match(/<link>([\s\S]*?)<\/link>/);
                    const pubDateMatch = item.match(/<pubDate>([\s\S]*?)<\/pubDate>/);

                    if (titleMatch && linkMatch) {
                        // Clean CDATA tags
                        let title = titleMatch[1].replace(/<!\[CDATA\[|\]\]>/g, '').trim();
                        let desc = descMatch ? descMatch[1].replace(/<!\[CDATA\[|\]\]>/g, '').trim() : title;

                        // Strip HTML from Nitter description
                        desc = desc.replace(/<[^>]*>?/gm, '');

                        // Only process significant tweets (ignore short "yes/no" replies)
                        if (title.length > 20) {
                            const result = insertStmt.run(
                                uuidv4(),
                                (title.length > 80 ? title.substring(0, 80) + '...' : title),
                                desc,
                                linkMatch[1],
                                `OSINT: X (@${account})`,
                                pubDateMatch ? new Date(pubDateMatch[1]).toISOString() : new Date().toISOString()
                            );

                            if (result.changes > 0) totalScraped++;
                        }
                    }
                }
                success = true;
                console.log(`  🐦 @${account}: checked latest posts via Nitter (${baseUrl})`);
            } catch (err) {
                if (i === NITTER_INSTANCES.length - 1) {
                    console.warn(`  ⚠️ Failed to scrape X/Twitter @${account} across all mirrors: ${err.message}`);
                }
            }
        }
    }

    console.log(`✅ OSINT X/Twitter scrape complete: ${totalScraped} new breaking updates found.\n`);
    return totalScraped;
}

module.exports = { scrapeXAccounts };
