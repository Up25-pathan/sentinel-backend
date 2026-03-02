const { image_search } = require('duckduckgo-images-api');

/**
 * Headless DuckDuckGo Image Scraper
 * Fetches relevant images for intelligence events based on keywords.
 */
async function fetchEventImages(query, limit = 4) {
    try {
        console.log(`  📸 Scraping context images for: "${query}"...`);
        const results = await image_search({ query, moderate: true, retries: 2, iterations: 1 });

        if (!results || results.length === 0) {
            return [];
        }

        // Extract the raw image URLs and filter out potential bad links
        const images = results
            .slice(0, limit)
            .map(img => img.image)
            .filter(url => url && !url.includes('svg') && !url.includes('gif'));

        return images;
    } catch (err) {
        console.warn(`  ⚠️ Image scraping failed for "${query}":`, err.message);
        return [];
    }
}

module.exports = { fetchEventImages };
