/**
 * Trend Analysis Service
 * Provides time-series data for risk trends, category distributions,
 * and event frequency for visualization.
 */
const { getDb } = require('../db');

/**
 * Get risk trend data over time (daily aggregation)
 */
function getRiskTrends(days = 30) {
    const db = getDb();

    const trends = db.prepare(`
        SELECT 
            date(created_at) as date,
            COUNT(*) as total_events,
            SUM(CASE WHEN risk_level = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
            SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END) as medium,
            SUM(CASE WHEN risk_level = 'LOW' THEN 1 ELSE 0 END) as low,
            AVG(CASE risk_level
                WHEN 'CRITICAL' THEN 100 WHEN 'HIGH' THEN 75
                WHEN 'MEDIUM' THEN 50 ELSE 25 END) as avg_risk_score,
            SUM(CASE WHEN is_breaking = 1 THEN 1 ELSE 0 END) as breaking_count
        FROM events
        WHERE created_at > datetime('now', '-${parseInt(days)} days')
        GROUP BY date(created_at)
        ORDER BY date ASC
    `).all();

    return trends;
}

/**
 * Get category distribution over time
 */
function getCategoryTrends(days = 14) {
    const db = getDb();

    const trends = db.prepare(`
        SELECT 
            date(created_at) as date,
            category,
            COUNT(*) as count
        FROM events
        WHERE created_at > datetime('now', '-${parseInt(days)} days')
        GROUP BY date(created_at), category
        ORDER BY date ASC, count DESC
    `).all();

    return trends;
}

/**
 * Get regional hotspot trends
 */
function getRegionalTrends(days = 14) {
    const db = getDb();

    const trends = db.prepare(`
        SELECT 
            location_name,
            COUNT(*) as event_count,
            AVG(CASE risk_level
                WHEN 'CRITICAL' THEN 100 WHEN 'HIGH' THEN 75
                WHEN 'MEDIUM' THEN 50 ELSE 25 END) as avg_risk,
            MAX(created_at) as latest_event,
            GROUP_CONCAT(DISTINCT category) as categories
        FROM events
        WHERE created_at > datetime('now', '-${parseInt(days)} days')
            AND location_name IS NOT NULL
        GROUP BY location_name
        ORDER BY event_count DESC
        LIMIT 20
    `).all();

    return trends;
}

/**
 * Get source credibility stats
 */
function getSourceCredibility() {
    const db = getDb();

    const sources = db.prepare(`
        SELECT 
            s.name,
            COUNT(*) as article_count,
            AVG(s.credibility) as avg_credibility,
            COUNT(DISTINCT s.event_id) as events_covered,
            MAX(s.published_at) as last_seen
        FROM sources s
        GROUP BY s.name
        ORDER BY article_count DESC
        LIMIT 30
    `).all();

    return sources;
}

/**
 * Get overall intelligence summary stats
 */
function getIntelSummary() {
    const db = getDb();

    const today = db.prepare(`
        SELECT COUNT(*) as count FROM events
        WHERE created_at > datetime('now', '-24 hours')
    `).get();

    const week = db.prepare(`
        SELECT COUNT(*) as count FROM events
        WHERE created_at > datetime('now', '-7 days')
    `).get();

    const critical = db.prepare(`
        SELECT COUNT(*) as count FROM events
        WHERE risk_level = 'CRITICAL' AND created_at > datetime('now', '-7 days')
    `).get();

    const topCategory = db.prepare(`
        SELECT category, COUNT(*) as count FROM events
        WHERE created_at > datetime('now', '-7 days')
        GROUP BY category ORDER BY count DESC LIMIT 1
    `).get();

    const topRegion = db.prepare(`
        SELECT location_name, COUNT(*) as count FROM events
        WHERE created_at > datetime('now', '-7 days') AND location_name IS NOT NULL
        GROUP BY location_name ORDER BY count DESC LIMIT 1
    `).get();

    return {
        events_today: today?.count || 0,
        events_this_week: week?.count || 0,
        critical_this_week: critical?.count || 0,
        top_category: topCategory?.category || 'N/A',
        top_category_count: topCategory?.count || 0,
        top_region: topRegion?.location_name || 'N/A',
        top_region_count: topRegion?.count || 0,
    };
}

module.exports = {
    getRiskTrends,
    getCategoryTrends,
    getRegionalTrends,
    getSourceCredibility,
    getIntelSummary,
};
