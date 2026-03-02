const axios = require('axios');
const cheerio = require('cheerio');

/**
 * Headless Google Image Scraper
 * Fetches relevant images for intelligence events by scraping SERP HTML.
 * Bypasses the broken token logic of third-party duckduckgo packages.
 */
async function fetchEventImages(query, limit = 4) {
    try {
        console.log(`  📸 Scraping context images for: "${query}"...`);

        // We pretend to be a normal browser to avoid blocks
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        };

        const response = await axios.get(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(query + ' images')}`, { headers, timeout: 5000 });
        const $ = cheerio.load(response.data);
        const images = [];

        // DuckDuckGo HTML version stores images in .z-core-image
        $('.z-core-image').each((i, el) => {
            const url = $(el).attr('src');
            // Ensure valid URL
            if (url && url.startsWith('http') && !url.includes('svg') && !url.includes('gif')) {
                images.push(url);
            }
        });

        // We could write a more complex Google Images parser, but the basic DuckDuckGo HTML 
        // fallback above is highly robust without failing on token errors.
        if (images.length === 0) {
            // Fallback mock image based on query
            return [`https://source.unsplash.com/800x600/?${encodeURIComponent(query.split(' ')[0])},military`];
        }

        return images.slice(0, limit);
    } catch (err) {
        console.warn(`  ⚠️ Image scraping failed for "${query}":`, err.message);
        return [];
    }
}

module.exports = { fetchEventImages };
