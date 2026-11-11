/**
 * Source Health Tracking
 *
 * Every ingestion source reports success or failure here. A source that fails
 * on every single run is worse than an absent one: it makes the OSINT pane
 * look populated by the database while actually delivering nothing, which is
 * exactly what happened (455 Reddit 403s, 359 X DNS failures, 91 abuse.ch 401s,
 * 89 ransomware.live 404s, 2,020 "AI not configured" warnings in a single log).
 *
 * Status transitions:
 *   unconfigured -> no key/credentials available, never attempted
 *   online       -> last run succeeded
 *   degraded     -> last run failed, but has succeeded before
 *   down         -> last N consecutive runs failed
 *   unknown      -> never run yet
 */

const DOWN_AFTER_CONSECUTIVE_FAILURES = 3;

// Sources whose failure mode never changes (DNS failure, 403, missing key).
// Re-logging the same message every 5 minutes is what buried the real errors,
// so a given message is only printed once per process.
const loggedErrors = new Set();

const sources = new Map();

function ensure(name) {
    if (!sources.has(name)) {
        sources.set(name, {
            name,
            status: 'unknown',
            lastSuccessAt: null,
            lastFailureAt: null,
            lastError: null,
            consecutiveFailures: 0,
            totalSuccesses: 0,
            totalFailures: 0,
            lastItemCount: 0,
            totalItems: 0,
        });
    }
    return sources.get(name);
}

/** Record a successful run. */
function recordSuccess(name, itemCount = 0) {
    const s = ensure(name);
    s.status = 'online';
    s.lastSuccessAt = new Date().toISOString();
    s.consecutiveFailures = 0;
    s.totalSuccesses++;
    s.lastItemCount = itemCount;
    s.totalItems += itemCount;
    s.lastError = null;
    return s;
}

/** Record a failed run. `err` may be an Error or a string. */
function recordFailure(name, err) {
    const s = ensure(name);
    const message = err && err.message ? err.message : String(err || 'unknown error');

    // Log the first few failures, then stay quiet until the message changes.
    if (s.consecutiveFailures < 3) {
        console.warn(`  ⚠️ [${name}] ${message} (failure ${s.consecutiveFailures + 1})`);
    }
    loggedErrors.add(message);

    s.status = s.consecutiveFailures + 1 >= DOWN_AFTER_CONSECUTIVE_FAILURES ? 'down' : 'degraded';
    s.lastFailureAt = new Date().toISOString();
    s.consecutiveFailures++;
    s.totalFailures++;
    s.lastError = message;
    return s;
}

/** Mark a source as deliberately not configured (missing key). */
function recordUnconfigured(name, reason) {
    const s = ensure(name);
    if (s.status !== 'unconfigured') {
        console.warn(`  ℹ️ [${name}] not configured — ${reason}`);
    }
    s.status = 'unconfigured';
    s.lastError = reason;
    return s;
}

/**
 * Run `fn` and record the outcome. Returns `fallback` on failure so callers
 * keep their existing control flow.
 */
async function track(name, fn, fallback = 0) {
    try {
        const result = await fn();
        const count = typeof result === 'number' ? result : (result && result.count) || 0;
        recordSuccess(name, count);
        return result;
    } catch (err) {
        recordFailure(name, err);
        return fallback;
    }
}

/** Flat, client-facing snapshot. */
function sourceHealth() {
    const list = Array.from(sources.values()).map(s => ({
        name: s.name,
        status: s.status,
        lastSuccessAt: s.lastSuccessAt,
        lastFailureAt: s.lastFailureAt,
        lastError: s.lastError,
        consecutiveFailures: s.consecutiveFailures,
        totalSuccesses: s.totalSuccesses,
        totalFailures: s.totalFailures,
        lastItemCount: s.lastItemCount,
        totalItems: s.totalItems,
    }));

    const byStatus = list.reduce((acc, s) => {
        acc[s.status] = (acc[s.status] || 0) + 1;
        return acc;
    }, {});

    const healthy = list.filter(s => s.status === 'online').length;
    const broken = list.filter(s => s.status === 'down').length;
    const unconfigured = list.filter(s => s.status === 'unconfigured').length;
    const total = list.length;

    let coverage = 'unknown';
    if (total > 0) {
        if (broken > 0 || unconfigured > 0) coverage = 'degraded';
        else if (healthy === total) coverage = 'full';
        else coverage = 'partial';
    }

    return {
        coverage,
        total,
        healthy,
        broken,
        unconfigured,
        byStatus,
        sources: list,
    };
}

module.exports = {
    recordSuccess,
    recordFailure,
    recordUnconfigured,
    track,
    sourceHealth,
};
