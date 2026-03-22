/**
 * Event Clustering Service
 * Groups related events by location, category, and time proximity
 */
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

/**
 * Calculate distance between two lat/lng points (in km)
 */
function haversineDistance(lat1, lng1, lat2, lng2) {
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Cluster events based on proximity and category
 */
function clusterEvents() {
    const db = getDb();

    // Get unclustered events with coordinates
    const events = db.prepare(`
        SELECT id, title, category, lat, lng, created_at, cluster_id
        FROM events 
        WHERE lat IS NOT NULL AND lng IS NOT NULL
        ORDER BY created_at DESC
    `).all();

    if (events.length === 0) {
        console.log('  ℹ️ No events to cluster.');
        return 0;
    }

    const updateCluster = db.prepare('UPDATE events SET cluster_id = ? WHERE id = ?');
    let clustersCreated = 0;
    const clusterIds = [];

    // Simple proximity + category clustering
    const processed = new Set();

    for (let i = 0; i < events.length; i++) {
        if (processed.has(events[i].id)) continue;

        const cluster = [events[i]];
        const clusterId = events[i].cluster_id || uuidv4();

        for (let j = i + 1; j < events.length; j++) {
            if (processed.has(events[j].id)) continue;

            // Same category and within 500km
            if (events[i].category === events[j].category) {
                const distance = haversineDistance(
                    events[i].lat, events[i].lng,
                    events[j].lat, events[j].lng
                );

                // Check time proximity (within 72 hours)
                const timeDiff = Math.abs(
                    new Date(events[i].created_at) - new Date(events[j].created_at)
                );
                const hoursDiff = timeDiff / (1000 * 60 * 60);

                if (distance < 500 && hoursDiff < 72) {
                    cluster.push(events[j]);
                }
            }
        }

        // Only create clusters with 2+ events
        if (cluster.length > 1) {
            const transaction = db.transaction(() => {
                for (const event of cluster) {
                    updateCluster.run(clusterId, event.id);
                    processed.add(event.id);
                }
            });
            transaction();
            clustersCreated++;
            clusterIds.push(clusterId);
        } else {
            processed.add(events[i].id);
        }
    }

    console.log(`✅ Clustering complete: ${clustersCreated} clusters identified.\n`);
    return clusterIds;
}

module.exports = { clusterEvents };
