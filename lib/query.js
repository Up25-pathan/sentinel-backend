/**
 * Query parameter validation helpers.
 *
 * Previously every handler did `parseInt(req.query.limit) || 20` and passed the
 * result straight into a bound parameter. That fails in both directions:
 *   ?limit=abc  -> parseInt gives NaN, the `||` default does not catch NaN's
 *                  truthiness, so NaN reached SQLite -> 500 datatype mismatch
 *   ?limit=-1    -> accepted verbatim, and `LIMIT -1` means "no limit", which
 *                  dumped the entire table to the caller
 */

/**
 * Parse an integer query param, clamped to [min, max], with a fallback.
 * Never returns NaN.
 */
function clampInt(value, { min = 1, max = 200, fallback = 20 } = {}) {
    const n = parseInt(value, 10);
    if (!Number.isFinite(n)) return fallback;
    if (n < min) return min;
    if (n > max) return max;
    return n;
}

/** Page number, 1-based, floored at 1. */
function clampPage(value, { max = 10000, fallback = 1 } = {}) {
    const n = parseInt(value, 10);
    if (!Number.isFinite(n)) return fallback;
    if (n < 1) return 1;
    if (n > max) return max;
    return n;
}

/** A time window in days, clamped to [1, 3650]. */
function clampDays(value, { min = 1, max = 3650, fallback = 30 } = {}) {
    return clampInt(value, { min, max, fallback });
}

/**
 * Compute LIMIT/OFFSET from page + limit.
 * Returns integers only.
 */
function paginate(query, { defaultLimit = 20, maxLimit = 200 } = {}) {
    const limit = clampInt(query.limit, { min: 1, max: maxLimit, fallback: defaultLimit });
    const page = clampPage(query.page);
    return { limit, page, offset: (page - 1) * limit };
}

/**
 * A SQLite datetime modifier for a `days` window, e.g. '-30 days'.
 * Returns a bound parameter, never interpolated SQL text.
 */
function daysModifier(days) {
    return `-${clampDays(days)} days`;
}

/**
 * Pick a value from an allowlist. Anything not present falls back.
 * Used for ORDER BY direction and sort column whitelists.
 */
function pick(value, allowed, fallback) {
    return allowed.includes(value) ? value : fallback;
}

module.exports = { clampInt, clampPage, clampDays, paginate, daysModifier, pick };
