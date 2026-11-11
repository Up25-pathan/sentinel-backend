/**
 * Event Clustering Service
 * Groups related events by location, category, and time proximity
 */
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

// ─── Tunables ────────────────────────────────────────────────────
const CLUSTER_RADIUS_KM = 500;
const CLUSTER_WINDOW_HOURS = 72;

// The previous implementation selected every located event ever stored and then
// compared every pair, which is O(n²). Measured against the live database: 838
// events produced 350,703 haversine evaluations and 71 ms of *synchronous*
// event-loop block, growing quadratically (~40 s at 20k events). Because
// better-sqlite3 is fully synchronous and this ran from a 30-minute cron, every
// HTTP request, SSE heartbeat and WebSocket broadcast stalled for the duration,
// and the events table grows by design.
const MAX_EVENTS_PER_RUN = 2000;
const MAX_CLUSTERS_PER_RUN = 200;
const YIELD_EVERY = 50;

const EARTH_RADIUS_KM = 6371;
// Derived from the same radius haversineDistance() uses. It must not be an
// independently chosen constant: 111.32 km/deg is the mean, whereas the true
// value is 111.1949. A window derived from the larger figure is marginally
// narrower than the 500 km radius and silently drops genuine neighbours that sit
// almost exactly due north/south of each other.
const KM_PER_DEG_LAT = EARTH_RADIUS_KM * Math.PI / 180;
// Latitude is the one axis where degrees and kilometres are uniform everywhere on
// the globe, which is what makes the sliding window below exact.
const RADIUS_DEG_LAT = CLUSTER_RADIUS_KM / KM_PER_DEG_LAT;

/**
 * Calculate distance between two lat/lng points (in km)
 */
function haversineDistance(lat1, lng1, lat2, lng2) {
    const R = EARTH_RADIUS_KM;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Yield to the event loop so a long clustering run cannot stall HTTP/SSE/WS. */
function yieldToEventLoop() {
    return new Promise((resolve) => setImmediate(resolve));
}

/**
 * Cluster events based on proximity and category.
 *
 * Now async and no longer O(n²).
 *
 * The obvious optimisation — a uniform lat/lng grid — is subtly incorrect here
 * and was measured dropping ~12% of genuine neighbours: a cell of fixed *degree*
 * width shrinks in kilometres toward the poles (at 82°N a 4.5° longitude cell is
 * only ~65 km), so a fixed ±1 cell neighbourhood no longer spans 500 km. Scaling
 * cells per latitude band does not fix it either, because the seed and its
 * candidate then land in grids of different widths and their cell indices are not
 * comparable across the band boundary.
 *
 * Instead the search exploits the one dimension where degrees and kilometres are
 * uniform: latitude. Sorting by latitude turns "within 500 km" into "within
 * RADIUS_DEG_LAT degrees", which is a *contiguous* run in sorted order. Scanning
 * outwards from each seed until that bound is crossed visits every possible
 * candidate and provably cannot miss one, regardless of longitude distortion.
 * Events are additionally partitioned by category, since clustering is defined as
 * "same category and nearby" and that is the cheapest possible partition.
 */
async function clusterEvents() {
    const db = getDb();

    // Bounded input. Clustering is a heuristic refinement over recent activity,
    // not a historical backfill, and only the newest events were ever meaningful.
    const events = db.prepare(`
        SELECT id, title, category, lat, lng, created_at, cluster_id
        FROM events
        WHERE lat IS NOT NULL AND lng IS NOT NULL
        ORDER BY created_at DESC
        LIMIT ?
    `).all(MAX_EVENTS_PER_RUN);

    if (events.length === 0) {
        console.log('  ℹ️ No events to cluster.');
        return [];
    }

    // Precompute timestamps once — `new Date(string)` per pair was a significant
    // share of the cost at this volume.
    for (const event of events) {
        const t = new Date(event.created_at).getTime();
        event._time = Number.isNaN(t) ? 0 : t;
    }

    // ─── Latitude index for candidate lookup ──────────────────────
    // The outer loop below deliberately still walks `events` in its original
    // (created_at DESC) order. Cluster formation is order-dependent — `processed`
    // is claimed as clusters are formed — so partitioning or reordering the outer
    // loop would change which events end up grouped together. The sorted index is
    // used only to *find* candidates, which keeps the result identical to the
    // original all-pairs scan while making it fast.
    const byCategory = new Map();
    for (const event of events) {
        const key = event.category || '';
        let bucket = byCategory.get(key);
        if (!bucket) {
            bucket = [];
            byCategory.set(key, bucket);
        }
        event._bucket = bucket;
        bucket.push(event);
    }
    for (const bucket of byCategory.values()) {
        bucket.sort((a, b) => a.lat - b.lat);
        bucket.forEach((event, index) => { event._slot = index; });
    }

    const updateCluster = db.prepare('UPDATE events SET cluster_id = ? WHERE id = ?');
    const clustersCreated = [];
    const processed = new Set();

    const windowMs = CLUSTER_WINDOW_HOURS * 60 * 60 * 1000;
    let sinceYield = 0;
    let reachedCap = false;

    for (let i = 0; i < events.length; i++) {
        const seed = events[i];
        if (processed.has(seed.id)) continue;

        const bucket = seed._bucket;
        const slot = seed._slot;
        const cluster = [seed];
        const clusterId = seed.cluster_id || uuidv4();
        const minLat = seed.lat - RADIUS_DEG_LAT;
        const maxLat = seed.lat + RADIUS_DEG_LAT;

        const consider = (candidate) => {
            if (candidate.id === seed.id) return;
            if (processed.has(candidate.id)) return;
            // Time proximity (within 72 hours) — cheap rejection before distance.
            if (Math.abs(candidate._time - seed._time) >= windowMs) return;

            const distance = haversineDistance(
                seed.lat, seed.lng,
                candidate.lat, candidate.lng
            );
            if (distance < CLUSTER_RADIUS_KM) cluster.push(candidate);
        };

        // Sorted ascending by latitude: every candidate inside the latitude bound
        // sits in this contiguous run, so stopping at the bound cannot skip one.
        for (let j = slot + 1; j < bucket.length; j++) {
            if (bucket[j].lat >= maxLat) break;
            consider(bucket[j]);
        }
        for (let j = slot - 1; j >= 0; j--) {
            if (bucket[j].lat <= minLat) break;
            consider(bucket[j]);
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
            clustersCreated.push(clusterId);
        } else {
            processed.add(seed.id);
        }

        // Bound the downstream work: the scheduler fans out an AI prediction per
        // cluster, and that loop was previously unbounded.
        if (clustersCreated.length >= MAX_CLUSTERS_PER_RUN) {
            reachedCap = true;
            break;
        }

        if (++sinceYield >= YIELD_EVERY) {
            sinceYield = 0;
            await yieldToEventLoop();
        }
    }

    console.log(
        `✅ Clustering complete: ${clustersCreated.length} clusters from ${events.length} events` +
        `${reachedCap ? ' (cluster cap reached)' : events.length >= MAX_EVENTS_PER_RUN ? ' (window capped)' : ''}.\n`
    );
    return clustersCreated;
}

module.exports = { clusterEvents, haversineDistance };