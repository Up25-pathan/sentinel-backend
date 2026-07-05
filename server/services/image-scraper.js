const axios = require('axios');
const cheerio = require('cheerio');

/**
 * Event Image Scraper
 * Multi-strategy approach to find relevant context images for intelligence events.
 * 
 * Strategy order:
 * 1. Bing Image Search (scraping HTML results)
 * 2. Google Custom Search (if API key available)
 * 3. Wikimedia Commons API (free, reliable, no auth)
 * 4. Category-based fallback images (always works)
 */

const BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
};

// ─── Strategy 1: Bing Image Search ──────────────────────────────
async function bingImageSearch(query, limit = 3) {
    const url = `https://www.bing.com/images/search?q=${encodeURIComponent(query)}&form=HDRSC2&first=1`;
    const response = await axios.get(url, {
        headers: BROWSER_HEADERS,
        timeout: 8000,
    });

    const $ = cheerio.load(response.data);
    const images = [];

    // Bing stores image data in 'm' attribute of .mimg elements or in iusc class
    $('a.iusc').each((i, el) => {
        try {
            const m = $(el).attr('m');
            if (m) {
                const data = JSON.parse(m);
                if (data.murl && data.murl.startsWith('http')) {
                    images.push(data.murl);
                }
            }
        } catch (e) { /* skip malformed entries */ }
    });

    // Also try img.mimg as fallback
    if (images.length === 0) {
        $('img.mimg').each((i, el) => {
            const src = $(el).attr('src');
            if (src && src.startsWith('http') && !src.includes('.svg')) {
                images.push(src);
            }
        });
    }

    return images.slice(0, limit);
}

// ─── Strategy 2: Wikimedia Commons API ──────────────────────────
async function wikimediaSearch(query, limit = 3) {
    const url = `https://commons.wikimedia.org/w/api.php`;
    const response = await axios.get(url, {
        params: {
            action: 'query',
            generator: 'search',
            gsrsearch: query,
            gsrlimit: limit,
            prop: 'imageinfo',
            iiprop: 'url|mime',
            iiurlwidth: 800,
            format: 'json',
            origin: '*',
        },
        headers: { 'User-Agent': 'SentinelIntelBot/1.0' },
        timeout: 6000,
    });

    const pages = response.data?.query?.pages;
    if (!pages) return [];

    const images = [];
    for (const page of Object.values(pages)) {
        const info = page.imageinfo?.[0];
        if (info && info.mime?.startsWith('image/')) {
            const imgUrl = info.thumburl || info.url;
            if (imgUrl && !imgUrl.includes('.svg')) {
                images.push(imgUrl);
            }
        }
    }

    return images.slice(0, limit);
}

// ─── Strategy 3: Category Fallback Images ───────────────────────
// Uses Wikimedia Commons curated category images as reliable fallbacks
const CATEGORY_IMAGE_MAP = {
    'WAR': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/USMC_M1A1_Abrams.jpg/800px-USMC_M1A1_Abrams.jpg',
    'MILITARY_MOVEMENT': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/USS_Abraham_Lincoln_%28CVN-72%29_underway_in_the_Pacific_Ocean_on_22_September_2018_%28180922-N-GR106-2032%29.jpg/800px-USS_Abraham_Lincoln_%28CVN-72%29_underway_in_the_Pacific_Ocean_on_22_September_2018_%28180922-N-GR106-2032%29.jpg',
    'SANCTIONS': 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/United_Nations_General_Assembly_Hall_%283%29.jpg/800px-United_Nations_General_Assembly_Hall_%283%29.jpg',
    'DIPLOMATIC_ESCALATION': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/The_United_Nations_Security_Council_in_session.jpg/800px-The_United_Nations_Security_Council_in_session.jpg',
    'NUCLEAR_THREAT': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Nagasakibomb.jpg/420px-Nagasakibomb.jpg',
    'CYBER_ATTACK': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/Cyber_Threat_Source_Descriptions.png/800px-Cyber_Threat_Source_Descriptions.png',
    'TERRORISM': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Smoke_pridge_during_the_2019-20_Hong_Kong_protests.jpg/800px-Smoke_pridge_during_the_2019-20_Hong_Kong_protests.jpg',
    'COUP': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/2021_Myanmar_coup_d%27%C3%A9tat_protest_%28291%29.jpg/800px-2021_Myanmar_coup_d%27%C3%A9tat_protest_%28291%29.jpg',
    'HUMANITARIAN': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Donate-a-photo-1.jpg/800px-Donate-a-photo-1.jpg',
    'POLITICAL_INSTABILITY': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Protests_in_Iraq_2019.jpg/800px-Protests_in_Iraq_2019.jpg',
    'OTHER': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/World_map_%282004%29.svg/800px-World_map_%282004%29.svg.png',
};

function getCategoryFallback(query) {
    // Try to detect category from the query string
    for (const [cat, url] of Object.entries(CATEGORY_IMAGE_MAP)) {
        if (query.toUpperCase().includes(cat)) {
            return [url];
        }
    }
    return [CATEGORY_IMAGE_MAP['OTHER']];
}

// ─── Main Entry Point ───────────────────────────────────────────
async function fetchEventImages(query, limit = 3) {
    console.log(`  📸 Fetching images for: "${query}"...`);

    // Strategy 1: Bing
    try {
        const bingImages = await bingImageSearch(query, limit);
        if (bingImages.length > 0) {
            console.log(`  ✅ Found ${bingImages.length} images via Bing`);
            return bingImages;
        }
    } catch (err) {
        console.warn(`  ⚠️ Bing image search failed: ${err.message}`);
    }

    // Strategy 2: Wikimedia Commons
    try {
        // Simplify query for Wikimedia (use just the location + category)
        const simpleQuery = query.split(' ').slice(0, 3).join(' ');
        const wikiImages = await wikimediaSearch(simpleQuery, limit);
        if (wikiImages.length > 0) {
            console.log(`  ✅ Found ${wikiImages.length} images via Wikimedia`);
            return wikiImages;
        }
    } catch (err) {
        console.warn(`  ⚠️ Wikimedia search failed: ${err.message}`);
    }

    // Strategy 3: Category fallback (always succeeds)
    const fallback = getCategoryFallback(query);
    console.log(`  📷 Using category fallback image`);
    return fallback;
}

module.exports = { fetchEventImages };
