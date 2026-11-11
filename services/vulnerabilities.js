/**
 * Vulnerability Intelligence — NVD CVE + CISA KEV
 * ===============================================
 * Populates the `vulnerabilities` table from two real, key-free public feeds:
 *
 *   CISA KEV  https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
 *             ~1,700 CVEs confirmed exploited in the wild. One request, no key.
 *             This is the source of truth for `exploit_status`.
 *
 *   NVD 2.0  https://services.nvd.nist.gov/rest/json/cves/2.0
 *             Authoritative CVSS base scores, descriptions, CPE vendor/product
 *             and CWE ids. Rate limited to 5 requests / 30 s without an API key
 *             and 50 with one, so pages are walked with a delay and the sync is
 *             incremental: it only asks for CVEs published since the newest row
 *             it already holds.
 *
 * Why this exists: the client previously shipped a hardcoded list of 15 invented
 * CVEs (CVE-2024-00001 "Apache Log4j", and so on) and displayed them whenever
 * /api/intelligence/vulns failed. That endpoint did not exist, so the panel
 * showed fabricated vulnerabilities 100% of the time. There is no fallback data
 * here by design: if both feeds fail the table stays empty and the client is
 * told the feed is down.
 */
const { getDb } = require('../db');
const { isUnset } = require('../env');
const { recordSuccess, recordFailure } = require('./source-health');

const NVD_BASE = 'https://services.nvd.nist.gov/rest/json/cves/2.0';
const KEV_URL = 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json';

// NVD: 5 requests / 30 s unauthenticated, 50 authenticated. Stay under the
// unauthenticated ceiling so a keyless deployment never gets 403-throttled.
const NVD_PAGE_SIZE = 100;
const NVD_MAX_PAGES = 6;          // <= 600 CVEs per run
const NVD_REQUEST_DELAY_MS = 6500;
const REQUEST_TIMEOUT_MS = 45000;

// How far back to look on a cold start, or when the last sync failed. KEV is
// small and always fully refreshed; NVD is the expensive one.
const COLD_START_LOOKBACK_DAYS = 30;

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * fetch with a hard timeout and a gentle retry.
 *
 * cisa.gov sits behind a WAF that answers a burst of requests with an HTML 404
 * page instead of the feed — several rapid retries guarantee 404, because each
 * retry is what trips the limit. The backoff is therefore long (10s, 30s) and an
 * HTML error body is reported as rate limiting rather than a missing feed.
 */
const RETRY_BACKOFF_MS = [10000, 30000];

async function fetchJson(url, { timeoutMs = REQUEST_TIMEOUT_MS, retries = 2 } = {}) {
    let lastErr;
    for (let attempt = 0; attempt <= retries; attempt++) {
        if (attempt > 0) {
            await sleep(RETRY_BACKOFF_MS[Math.min(attempt - 1, RETRY_BACKOFF_MS.length - 1)]);
        }
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const res = await fetch(url, {
                signal: controller.signal,
                headers: { 'User-Agent': 'SENTINEL-Intel/1.0 (vulnerability sync)' },
            });
            if (!res.ok) {
                const body = await res.text().catch(() => '');
                const isHtml = /^\s*<(!doctype|html)/i.test(body);
                if (isHtml) {
                    throw new Error(
                        `upstream returned an HTML error page (HTTP ${res.status}) — ` +
                        'rate limited or blocked by the origin WAF; will retry slowly'
                    );
                }
                throw new Error(`HTTP ${res.status} ${res.statusText}${body ? ` — ${body.slice(0, 180)}` : ''}`);
            }
            return await res.json();
        } catch (err) {
            lastErr = err.name === 'AbortError'
                ? new Error(`request timed out after ${timeoutMs}ms`)
                : err;
        } finally {
            clearTimeout(timer);
        }
    }
    throw lastErr;
}

/**
 * Severity is derived from the CVSS base score rather than copied from the
 * feed, so a row keeps a consistent colour even if the publisher labels a
 * 5.9 as "HIGH".
 */
function severityFromScore(score) {
    if (score === null || score === undefined || Number.isNaN(score)) return 'UNKNOWN';
    if (score >= 9.0) return 'CRITICAL';
    if (score >= 7.0) return 'HIGH';
    if (score >= 4.0) return 'MEDIUM';
    if (score > 0) return 'LOW';
    return 'UNKNOWN';
}

/**
 * Pull the primary CVSS metric, preferring the newest schema version present.
 * NVD publishes cvssMetricV40 / V31 / V30 / V2 on the same record.
 */
function pickCvss(metrics) {
    if (!metrics) return null;
    const order = ['cvssMetricV40', 'cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2'];
    for (const key of order) {
        const list = metrics[key];
        if (Array.isArray(list) && list.length && list[0] && list[0].cvssData) {
            const d = list[0].cvssData;
            if (typeof d.baseScore === 'number') {
                return { score: d.baseScore, vector: d.vectorString || null, version: key };
            }
        }
    }
    return null;
}

/**
 * Resolve vendor / product / affected versions for a CVE.
 *
 * NVD 2.0 moved product data out of the legacy CPE `configurations` block and
 * into `affected[].affectedData[]` ({ vendor, product, versions[] }). Records
 * published through the new CNA pipeline have no `configurations` at all, so
 * reading only the legacy shape resolved a product for 0 of 50 current CVEs.
 * Both shapes are handled: the structured one first, CPE as a fallback for
 * records that predate the change.
 */
function parseAffected(cve) {
    const structured = parseAffectedStructured(cve);
    if (structured.product) return structured;
    return parseCpe(cve.configurations);
}

/** The NVD 2.0 `affected[].affectedData[]` shape. */
function parseAffectedStructured(cve) {
    const out = { vendor: null, product: null, versions: null };
    const blocks = Array.isArray(cve?.affected) ? cve.affected : [];
    if (!blocks.length) return out;

    for (const block of blocks) {
        const data = Array.isArray(block?.affectedData) ? block.affectedData : [];
        for (const entry of data) {
            if (!out.vendor && entry?.vendor) out.vendor = String(entry.vendor).slice(0, 200);
            if (!out.product && entry?.product) out.product = String(entry.product).slice(0, 200);
        }
    }

    // Version ranges, rendered the way a human would want to read them.
    const seen = new Set();
    for (const block of blocks) {
        for (const entry of (Array.isArray(block?.affectedData) ? block.affectedData : [])) {
            for (const v of (Array.isArray(entry?.versions) ? entry.versions : [])) {
                if (v?.status && v.status !== 'affected') continue;
                let text = null;
                if (v.lessThanOrEqual) text = `<= ${v.lessThanOrEqual}`;
                else if (v.lessThan) text = `< ${v.lessThan}`;
                else if (v.version && v.version !== '*' && v.version !== '-') text = v.version;
                if (text && !seen.has(text)) seen.add(text);
            }
        }
    }
    if (seen.size) out.versions = Array.from(seen).slice(0, 4).join(' / ');

    return out;
}

/**
 * Legacy CPE shape. `criteria` looks like cpe:2.3:a:vendor:product:version:...
 */
function parseCpe(configurations) {
    try {
        const nodes = configurations?.[0]?.nodes;
        if (!Array.isArray(nodes) || !nodes.length) return {};
        for (const node of nodes) {
            const matches = node.cpeMatch;
            if (!Array.isArray(matches) || !matches.length) continue;
            for (const m of matches) {
                const parts = String(m.criteria || '').split(':');
                // cpe, 2.3, a, vendor, product, version
                if (parts.length < 6) continue;
                const out = {
                    vendor: parts[3] && parts[3] !== '*' ? parts[3] : null,
                    product: parts[4] && parts[4] !== '*' ? parts[4] : null,
                    version: parts[5] && parts[5] !== '*' ? parts[5] : null,
                };
                if (out.product) return out;
            }
        }
    } catch {
        // Malformed configurations are not worth failing the whole record over.
    }
    return {};
}

/**
 * Map one CISA KEV entry to bound parameters for the upsert statements.
 * Pure: no network, no DB. Returns null for an entry without a usable CVE id.
 */
function parseKevEntry(v, now) {
    const id = String(v?.cveID || '').trim().toUpperCase();
    if (!id || !/^CVE-\d{4}-\d{4,}$/.test(id)) return null;
    return {
        id,
        desc: String(v.shortDescription || '').slice(0, 2000),
        vendor: String(v.vendorProject || '').slice(0, 200) || null,
        product: String(v.product || '').slice(0, 200) || null,
        ransomware: String(v.knownRansomwareCampaignUse || '') || null,
        dateAdded: v.dateAdded || null,
        dueDate: v.dueDate || null,
        action: String(v.requiredAction || '').slice(0, 4000) || null,
        cwes: Array.isArray(v.cwes) && v.cwes.length ? v.cwes.slice(0, 12).join(',') : null,
        now,
    };
}

/**
 * Map one NVD `vulnerabilities[]` element to bound parameters. Pure.
 * Returns null for anything without a well-formed CVE id.
 */
function parseNvdItem(item, now) {
    const cve = item?.cve;
    const cve_id = cve?.id ? String(cve.id).trim().toUpperCase() : null;
    if (!cve_id || !/^CVE-\d{4}-\d{4,}$/.test(cve_id)) return null;

    const cvss = pickCvss(cve.metrics);
    const affected = parseAffected(cve);
    const desc = Array.isArray(cve.descriptions)
        ? (cve.descriptions.find(d => d.lang === 'en') || cve.descriptions[0])?.value || ''
        : '';
    const cwes = Array.isArray(cve.weaknesses) && cve.weaknesses.length
        ? cve.weaknesses
            .flatMap(w => (w.description || []).map(d => d.value))
            .filter(v => typeof v === 'string' && v.startsWith('CWE-'))
            .slice(0, 12).join(',')
        : null;
    const refs = Array.isArray(cve.references) && cve.references.length
        ? JSON.stringify(cve.references.slice(0, 20).map(r => r.url).filter(Boolean))
        : null;

    return {
        cve_id,
        description: String(desc).slice(0, 4000),
        cvss_score: cvss ? cvss.score : null,
        severity: cvss ? severityFromScore(cvss.score) : 'UNKNOWN',
        cvss_vector: cvss ? cvss.vector : null,
        vendor: affected.vendor || null,
        product: affected.product || null,
        affected_versions: affected.versions || null,
        cwes: cwes || null,
        references_json: refs,
        // Never downgrade a KEV row: NVD knows nothing about exploitation, so
        // the stored value is overwritten only below, in the ON CONFLICT clause
        // of the SQL, which is a no-op when the CVE is already marked Weaponized.
        exploit_status: 'No Known Exploit',
        vuln_status: cve.vulnStatus || null,
        published: cve.published || null,
        modified: cve.lastModified || null,
        nvd_fetched_at: now,
    };
}

const UPSERT = `
INSERT INTO vulnerabilities (
    cve_id, description, cvss_score, severity, cvss_vector,
    vendor, product, affected_versions, cwes, references_json,
    exploit_status, vuln_status, published, modified, nvd_fetched_at
) VALUES (
    @cve_id, @description, @cvss_score, @severity, @cvss_vector,
    @vendor, @product, @affected_versions, @cwes, @references_json,
    @exploit_status, @vuln_status, @published, @modified, @nvd_fetched_at
)
ON CONFLICT(cve_id) DO UPDATE SET
    description       = COALESCE(excluded.description, vulnerabilities.description),
    cvss_score        = COALESCE(excluded.cvss_score, vulnerabilities.cvss_score),
    severity          = COALESCE(excluded.severity, vulnerabilities.severity),
    cvss_vector       = COALESCE(excluded.cvss_vector, vulnerabilities.cvss_vector),
    vendor            = COALESCE(excluded.vendor, vulnerabilities.vendor),
    product           = COALESCE(excluded.product, vulnerabilities.product),
    affected_versions = COALESCE(excluded.affected_versions, vulnerabilities.affected_versions),
    cwes              = COALESCE(excluded.cwes, vulnerabilities.cwes),
    references_json   = COALESCE(excluded.references_json, vulnerabilities.references_json),
    -- NVD carries no exploitation data. Without this guard the nightly NVD sync
    -- reset every CISA KEV row from 'Weaponized' back to 'No Known Exploit'.
    exploit_status    = CASE
                           WHEN vulnerabilities.in_kev = 1 THEN 'Weaponized'
                           ELSE excluded.exploit_status
                       END,
    vuln_status       = COALESCE(excluded.vuln_status, vulnerabilities.vuln_status),
    published         = COALESCE(excluded.published, vulnerabilities.published),
    modified          = COALESCE(excluded.modified, vulnerabilities.modified),
    nvd_fetched_at    = excluded.nvd_fetched_at
`;

/**
 * Sync the CISA Known Exploited Vulnerabilities catalog.
 * Full replace each run — the feed is small, and entries are only ever added
 * or annotated, so an upsert on the CVE id is the whole job.
 */
async function syncKev() {
    const label = 'vuln:cisa-kev';
    try {
        const feed = await fetchJson(KEV_URL);
        const list = Array.isArray(feed?.vulnerabilities) ? feed.vulnerabilities : [];
        if (!list.length) {
            throw new Error('KEV feed returned no vulnerabilities');
        }

        const db = getDb();
        const now = new Date().toISOString();
        const stmt = db.prepare(`
            UPDATE vulnerabilities SET
                in_kev = 1,
                exploit_status = 'Weaponized',
                ransomware_use = @ransomware,
                kev_date_added = @dateAdded,
                kev_due_date = @dueDate,
                required_action = @action,
                vendor = COALESCE(vendor, @vendor),
                product = COALESCE(product, @product),
                description = CASE WHEN description = '' THEN @desc ELSE description END,
                cwes = COALESCE(cwes, @cwes),
                kev_fetched_at = @now
            WHERE cve_id = @id
        `);

        // A KEV entry can predate our NVD coverage, so insert the KEV record
        // itself when the CVE is not in the table yet. cvss_score stays NULL
        // until NVD fills it in; the client renders "—".
        const insert = db.prepare(`
            INSERT INTO vulnerabilities (
                cve_id, description, cvss_score, severity, vendor, product,
                exploit_status, in_kev, ransomware_use, kev_date_added,
                kev_due_date, required_action, cwes, kev_fetched_at
            ) VALUES (
                @id, @desc, NULL, 'UNKNOWN', @vendor, @product,
                'Weaponized', 1, @ransomware, @dateAdded,
                @dueDate, @action, @cwes, @now
            )
            ON CONFLICT(cve_id) DO UPDATE SET
                in_kev = 1,
                exploit_status = 'Weaponized',
                ransomware_use = @ransomware,
                kev_date_added = @dateAdded,
                kev_due_date = @dueDate,
                required_action = @action,
                vendor = COALESCE(vulnerabilities.vendor, @vendor),
                product = COALESCE(vulnerabilities.product, @product),
                description = CASE WHEN vulnerabilities.description = '' THEN @desc ELSE vulnerabilities.description END,
                cwes = COALESCE(vulnerabilities.cwes, @cwes),
                kev_fetched_at = @now
        `);

        const run = db.transaction(() => {
            let updated = 0;
            for (const v of list) {
                const params = parseKevEntry(v, now);
                if (!params) continue;
                const r = stmt.run(params);
                if (r.changes > 0) {
                    updated++;
                } else {
                    insert.run(params);
                }
            }
            return updated;
        });

        const updated = run();
        const total = db.prepare('SELECT COUNT(*) AS n FROM vulnerabilities WHERE in_kev = 1').get().n;
        console.log(`   🛡️  CISA KEV: ${list.length} entries processed, ${updated} matched existing CVEs, ${total} KEV rows held`);
        recordSuccess(label, list.length);
        return list.length;
    } catch (err) {
        recordFailure(label, err);
        return 0;
    }
}

/**
 * Incremental NVD 2.0 sync. Asks only for CVEs published after the newest row
 * already stored, so a steady-state daily run is one cheap page.
 */
async function syncNvd() {
    const label = 'vuln:nvd';
    try {
        const db = getDb();
        const row = db.prepare('SELECT MAX(published) AS newest FROM vulnerabilities WHERE published IS NOT NULL').get();
        let start;

        if (row?.newest) {
            // Re-fetch a day of overlap so late-published/updated records land.
            start = new Date(new Date(row.newest).getTime() - 24 * 3600 * 1000);
        } else {
            start = new Date(Date.now() - COLD_START_LOOKBACK_DAYS * 24 * 3600 * 1000);
        }
        const end = new Date();

        const fmt = (d) => `${d.toISOString().slice(0, 19)}.000Z`;
        let startIndex = 0;
        let stored = 0;
        let pages = 0;
        let totalResults = 0;

        const upsert = db.prepare(UPSERT);

        while (pages < NVD_MAX_PAGES) {
            const url = new URL(NVD_BASE);
            url.searchParams.set('resultsPerPage', String(NVD_PAGE_SIZE));
            url.searchParams.set('startIndex', String(startIndex));
            url.searchParams.set('pubStartDate', fmt(start));
            url.searchParams.set('pubEndDate', fmt(end));

            const apiKey = process.env.NVD_API_KEY;
            if (!isUnset(apiKey)) {
                url.searchParams.set('apiKey', String(apiKey).trim());
            }

            const data = await fetchJson(url.toString());
            totalResults = data?.totalResults || 0;
            const items = Array.isArray(data?.vulnerabilities) ? data.vulnerabilities : [];
            if (!items.length) break;

            const now = new Date().toISOString();
            const run = db.transaction(() => {
                let n = 0;
                for (const item of items) {
                    const params = parseNvdItem(item, now);
                    if (!params) continue;
                    upsert.run(params);
                    n++;
                }
                return n;
            });

            stored += run();
            pages++;
            startIndex += items.length;

            if (startIndex >= totalResults) break;
            if (pages < NVD_MAX_PAGES) {
                // Stay inside the unauthenticated rate limit.
                await sleep(NVD_REQUEST_DELAY_MS);
            }
        }

        const held = db.prepare('SELECT COUNT(*) AS n FROM vulnerabilities').get().n;
        const newest = db.prepare('SELECT MAX(published) AS p FROM vulnerabilities').get().p;
        console.log(
            `   🛡️  NVD 2.0: ${totalResults} published since ${fmt(start).slice(0, 10)}, ` +
            `${stored} upserted over ${pages} page(s); ${held} rows held, newest ${newest || 'n/a'}`
        );
        if (totalResults === 0) {
            throw new Error(`no CVEs published since ${fmt(start).slice(0, 10)} — upstream may be stale`);
        }
        recordSuccess(label, stored);
        return stored;
    } catch (err) {
        recordFailure(label, err);
        return 0;
    }
}

// How many KEV CVEs to score per run. NVD 2.0 accepts only one cveId per
// request, and the anonymous limit is 5 requests / 30 s, so a full pass over
// ~1,700 KEV entries is not a single-run job. 25/day converges over a couple of
// months and costs ~3 minutes of scheduler time.
const KEV_SCORE_BUDGET = 25;

/**
 * Fill in CVSS scores for KEV entries the date-window sync will never reach.
 *
 * KEV is a catalog of old, already-published CVEs, so the incremental NVD sync
 * (which only asks for recently published CVEs) never returns them. Left alone
 * they all read severity=UNKNOWN, which made the panel report 0 CRITICAL
 * vulnerabilities while listing 1,729 confirmed-exploited ones.
 */
async function backfillKevScores() {
    const label = 'vuln:nvd-kev-backfill';
    try {
        const db = getDb();
        const pending = db.prepare(`
            SELECT cve_id FROM vulnerabilities
            WHERE in_kev = 1 AND cvss_score IS NULL AND nvd_fetched_at IS NULL
            ORDER BY kev_date_added DESC
            LIMIT ?
        `).all(KEV_SCORE_BUDGET);

        if (!pending.length) {
            recordSuccess(label, 0);
            return 0;
        }

        const apiKey = process.env.NVD_API_KEY;
        let scored = 0;
        for (const { cve_id } of pending) {
            const url = new URL(NVD_BASE);
            url.searchParams.set('cveId', cve_id);
            if (!isUnset(apiKey)) url.searchParams.set('apiKey', String(apiKey).trim());

            try {
                const data = await fetchJson(url.toString(), { retries: 1 });
                const item = Array.isArray(data?.vulnerabilities) ? data.vulnerabilities[0] : null;
                const params = parseNvdItem(item, new Date().toISOString());
                if (params && params.cvss_score !== null) {
                    getDb().prepare(UPSERT).run(params);
                    scored++;
                } else {
                    // Mark as attempted so a CVE NVD has no score for does not
                    // get retried forever.
                    getDb().prepare('UPDATE vulnerabilities SET nvd_fetched_at = ? WHERE cve_id = ?')
                        .run(new Date().toISOString(), cve_id);
                }
            } catch (err) {
                // A single missing/unscored CVE must not abort the batch.
                getDb().prepare('UPDATE vulnerabilities SET nvd_fetched_at = ? WHERE cve_id = ?')
                    .run(new Date().toISOString(), cve_id);
            }

            if (scored < pending.length - 1) await sleep(NVD_REQUEST_DELAY_MS);
        }

        const remaining = db.prepare(`
            SELECT COUNT(*) AS n FROM vulnerabilities
            WHERE in_kev = 1 AND cvss_score IS NULL
        `).get().n;
        if (scored > 0 || remaining === 0) {
            console.log(`   🛡️  NVD KEV backfill: ${scored}/${pending.length} scored this run, ${remaining} still unrated`);
        }
        recordSuccess(label, scored);
        return scored;
    } catch (err) {
        recordFailure(label, err);
        return 0;
    }
}

/**
 * Full vulnerability sync. Both feeds are independent: KEV succeeding with NVD
 * down is a useful partial state, so failures are recorded, not thrown.
 */
async function syncVulnerabilities() {
    console.log('─'.repeat(50));
    console.log(`[${new Date().toISOString()}] Syncing vulnerability intelligence (NVD + CISA KEV)...`);
    const kev = await syncKev();
    const nvd = await syncNvd();
    // Scored last and awaited, but only touches rows the other two left blank.
    const backfilled = await backfillKevScores();
    return { kev, nvd, backfilled };
}

/** Counts for the dashboard, plus whether we have ever synced anything. */
function vulnStats() {
    const db = getDb();
    const base = db.prepare('SELECT COUNT(*) AS n FROM vulnerabilities').get().n;
    const bySeverity = db.prepare('SELECT severity, COUNT(*) AS n FROM vulnerabilities GROUP BY severity').all();
    const kev = db.prepare('SELECT COUNT(*) AS n FROM vulnerabilities WHERE in_kev = 1').get().n;
    const critical = db.prepare("SELECT COUNT(*) AS n FROM vulnerabilities WHERE severity = 'CRITICAL'").get().n;
    const exploitable = db.prepare("SELECT COUNT(*) AS n FROM vulnerabilities WHERE exploit_status = 'Weaponized'").get().n;
    const newest = db.prepare('SELECT MAX(published) AS p FROM vulnerabilities').get().p;
    const lastNvd = db.prepare('SELECT MAX(nvd_fetched_at) AS t FROM vulnerabilities').get().t;
    const lastKev = db.prepare('SELECT MAX(kev_fetched_at) AS t FROM vulnerabilities').get().t;

    const severities = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, UNKNOWN: 0 };
    for (const r of bySeverity) {
        if (r.severity in severities) severities[r.severity] = r.n;
    }

    return {
        total: base,
        by_severity: severities,
        kev_count: kev,
        kev_ransomware: db.prepare(
            "SELECT COUNT(*) AS n FROM vulnerabilities WHERE in_kev = 1 AND ransomware_use = 'Known'"
        ).get().n,
        critical: critical,
        exploitable,
        newest_published: newest,
        last_nvd_sync: lastNvd,
        last_kev_sync: lastKev,
        configured: base > 0,
    };
}

module.exports = {
    syncVulnerabilities,
    syncKev,
    syncNvd,
    backfillKevScores,
    vulnStats,
    severityFromScore,
    pickCvss,
    parseCpe,
    parseAffected,
    parseAffectedStructured,
    parseKevEntry,
    parseNvdItem,
};
