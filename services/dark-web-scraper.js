/**
 * Dark Web Intelligence Scrapers
 * Collects threat intelligence from open-source deep/dark web feeds.
 * All sources are accessed via clearnet APIs — no Tor required.
 */
const axios = require('axios');
const { getDb } = require('../db');
require('dotenv').config();

// ─── 1. abuse.ch — Malware/Botnet Tracking ──────────────────────
// Free, no API key needed. Tracks botnets, malware C2 servers.
async function scrapeAbuseCH() {
    console.log('  🕷️ Fetching abuse.ch threat feeds...');
    const db = getDb();
    let count = 0;

    try {
        // Recent malware URLs
        const urlhausRes = await axios.get('https://urlhaus-api.abuse.ch/v1/urls/recent/', {
            headers: { 'User-Agent': 'SentinelIntelBot/1.0' },
            timeout: 10000,
        });

        const urls = urlhausRes.data?.urls || [];
        for (const entry of urls.slice(0, 20)) {
            const existing = db.prepare('SELECT id FROM dark_web_intel WHERE source_id = ?').get(`abusech-${entry.id}`);
            if (existing) continue;

            db.prepare(`
                INSERT INTO dark_web_intel (source_id, source, category, title, content, threat_level, url, tags, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            `).run(
                `abusech-${entry.id}`,
                'abuse.ch',
                'MALWARE',
                `Malware URL: ${entry.threat || 'Unknown Threat'}`,
                `URL: ${entry.url}\nHost: ${entry.host}\nStatus: ${entry.url_status}\nThreat: ${entry.threat}\nTags: ${(entry.tags || []).join(', ')}`,
                entry.threat === 'malware_download' ? 'HIGH' : 'MEDIUM',
                entry.url,
                JSON.stringify(entry.tags || []),
            );
            count++;
        }

        // Recent botnet C2 servers
        const feodoRes = await axios.get('https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.json', {
            headers: { 'User-Agent': 'SentinelIntelBot/1.0' },
            timeout: 10000,
        });

        const c2s = feodoRes.data || [];
        for (const entry of c2s.slice(0, 15)) {
            const srcId = `feodo-${entry.ip_address}-${entry.port}`;
            const existing = db.prepare('SELECT id FROM dark_web_intel WHERE source_id = ?').get(srcId);
            if (existing) continue;

            db.prepare(`
                INSERT INTO dark_web_intel (source_id, source, category, title, content, threat_level, tags, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            `).run(
                srcId,
                'abuse.ch/feodo',
                'BOTNET_C2',
                `Botnet C2: ${entry.malware} at ${entry.ip_address}:${entry.port}`,
                `IP: ${entry.ip_address}\nPort: ${entry.port}\nMalware: ${entry.malware}\nStatus: ${entry.status}\nCountry: ${entry.country}\nAS: ${entry.as_name}`,
                'CRITICAL',
                JSON.stringify([entry.malware, entry.country]),
            );
            count++;
        }
    } catch (err) {
        console.warn(`  ⚠️ abuse.ch scrape error: ${err.message}`);
    }

    return count;
}

// ─── 2. Ransomware.live — Active Ransomware Groups ──────────────
async function scrapeRansomware() {
    console.log('  🔒 Fetching ransomware group activity...');
    const db = getDb();
    let count = 0;

    try {
        const res = await axios.get('https://api.ransomware.live/recentvictims', {
            headers: { 'User-Agent': 'SentinelIntelBot/1.0' },
            timeout: 10000,
        });

        const victims = res.data || [];
        for (const v of victims.slice(0, 20)) {
            const srcId = `ransom-${v.group_name}-${v.post_title?.substring(0, 40)}`;
            const existing = db.prepare('SELECT id FROM dark_web_intel WHERE source_id = ?').get(srcId);
            if (existing) continue;

            db.prepare(`
                INSERT INTO dark_web_intel (source_id, source, category, title, content, threat_level, url, tags, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            `).run(
                srcId,
                'ransomware.live',
                'RANSOMWARE',
                `[${v.group_name}] ${v.post_title || 'New victim posted'}`,
                `Group: ${v.group_name}\nVictim: ${v.post_title}\nCountry: ${v.country || 'Unknown'}\nSector: ${v.activity || 'Unknown'}\nDate: ${v.discovered}`,
                'CRITICAL',
                v.post_url || '',
                JSON.stringify([v.group_name, v.country]),
            );
            count++;
        }
    } catch (err) {
        console.warn(`  ⚠️ Ransomware.live scrape error: ${err.message}`);
    }

    return count;
}

// ─── 3. AlienVault OTX — Threat Intel Pulses ────────────────────
async function scrapeOTX() {
    console.log('  👽 Fetching AlienVault OTX pulses...');
    const db = getDb();
    let count = 0;

    const apiKey = process.env.OTX_API_KEY;
    if (!apiKey) {
        console.log('  ⏩ OTX_API_KEY not set, skipping AlienVault');
        return 0;
    }

    try {
        const res = await axios.get('https://otx.alienvault.com/api/v1/pulses/subscribed?limit=15&modified_since=', {
            headers: {
                'X-OTX-API-KEY': apiKey,
                'User-Agent': 'SentinelIntelBot/1.0',
            },
            timeout: 10000,
        });

        const pulses = res.data?.results || [];
        for (const pulse of pulses) {
            const srcId = `otx-${pulse.id}`;
            const existing = db.prepare('SELECT id FROM dark_web_intel WHERE source_id = ?').get(srcId);
            if (existing) continue;

            const tags = pulse.tags || [];
            const indicators = pulse.indicator_count || 0;
            const tlp = pulse.tlp || 'white';

            db.prepare(`
                INSERT INTO dark_web_intel (source_id, source, category, title, content, threat_level, url, tags, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            `).run(
                srcId,
                'AlienVault OTX',
                'THREAT_INTEL',
                pulse.name,
                `${pulse.description || 'No description'}\n\nIndicators: ${indicators}\nTLP: ${tlp}\nAdversary: ${pulse.adversary || 'Unknown'}\nTargeted Countries: ${(pulse.targeted_countries || []).join(', ') || 'N/A'}`,
                indicators > 100 ? 'CRITICAL' : indicators > 20 ? 'HIGH' : 'MEDIUM',
                `https://otx.alienvault.com/pulse/${pulse.id}`,
                JSON.stringify(tags.slice(0, 10)),
            );
            count++;
        }
    } catch (err) {
        console.warn(`  ⚠️ OTX scrape error: ${err.message}`);
    }

    return count;
}

// ─── 4. Shodan (Internet-Exposed Infrastructure) ────────────────
async function scrapeShodan() {
    console.log('  🔍 Fetching Shodan exposed infrastructure...');
    const db = getDb();
    let count = 0;

    const apiKey = process.env.SHODAN_API_KEY;
    if (!apiKey) {
        console.log('  ⏩ SHODAN_API_KEY not set, skipping Shodan');
        return 0;
    }

    try {
        // Search for critical exposed infrastructure (SCADA, ICS, etc.)
        const queries = [
            'tag:ics country:RU,CN,IR,KP',
            'product:Siemens port:102',
            'vuln:CVE-2024',
        ];

        for (const query of queries) {
            try {
                const res = await axios.get('https://api.shodan.io/shodan/host/search', {
                    params: { key: apiKey, query, minify: true },
                    timeout: 10000,
                });

                const matches = res.data?.matches || [];
                for (const match of matches.slice(0, 5)) {
                    const srcId = `shodan-${match.ip_str}-${match.port}`;
                    const existing = db.prepare('SELECT id FROM dark_web_intel WHERE source_id = ?').get(srcId);
                    if (existing) continue;

                    db.prepare(`
                        INSERT INTO dark_web_intel (source_id, source, category, title, content, threat_level, tags, discovered_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    `).run(
                        srcId,
                        'Shodan',
                        'EXPOSED_INFRA',
                        `Exposed: ${match.product || 'Service'} at ${match.ip_str}:${match.port}`,
                        `IP: ${match.ip_str}\nPort: ${match.port}\nOrg: ${match.org}\nCountry: ${match.location?.country_name}\nProduct: ${match.product}\nVersion: ${match.version}\nVulns: ${Object.keys(match.vulns || {}).join(', ')}`,
                        match.vulns ? 'CRITICAL' : 'HIGH',
                        JSON.stringify([match.org, match.location?.country_code]),
                    );
                    count++;
                }
            } catch (e) {
                // Rate limited or query error, skip
            }
        }
    } catch (err) {
        console.warn(`  ⚠️ Shodan scrape error: ${err.message}`);
    }

    return count;
}

// ─── Main Runner ────────────────────────────────────────────────
async function scrapeDarkWeb() {
    console.log('\n🕸️ Dark Web Intelligence Collection Starting...');
    const startTime = Date.now();

    const abusechCount = await scrapeAbuseCH();
    const ransomCount = await scrapeRansomware();
    const otxCount = await scrapeOTX();
    const shodanCount = await scrapeShodan();

    const total = abusechCount + ransomCount + otxCount + shodanCount;
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`✅ Dark web intel: ${total} new items in ${elapsed}s (abuse.ch: ${abusechCount}, ransomware: ${ransomCount}, OTX: ${otxCount}, Shodan: ${shodanCount})\n`);

    return total;
}

module.exports = { scrapeDarkWeb };
