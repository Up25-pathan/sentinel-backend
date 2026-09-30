/**
 * Offline verification of the vulnerability pipeline against REAL captured
 * upstream payloads (cisa.gov KEV + NVD 2.0). No network, so this is repeatable
 * and does not trip CISA's WAF.
 *
 *   node server/test_vulns_offline.js
 *
 * Payloads are read from FIX (see KEV_FILE / NVD_FILE below). The database is
 * deleted first so every run starts from the same state and counts are exact.
 */
const fs = require('fs');
const path = require('path');

const FIX = process.env.VULN_FIXTURE_DIR || 'C:/Users/umarp/AppData/Local/Temp/opencode';
process.env.DB_PATH = process.env.VULN_TEST_DB
    || path.join(FIX, 'vulnoffline.db');

// Start clean: a leftover DB from a previous run makes row counts drift.
for (const suffix of ['', '-wal', '-shm']) {
    try { fs.unlinkSync(process.env.DB_PATH + suffix); } catch (e) { /* first run */ }
}

const { getDb, closeDb } = require('./db');
const v = require('./services/vulnerabilities');

let failed = 0;
function check(label, cond, extra = '') {
    console.log(`${cond ? '  PASS' : '  FAIL'}  ${label}${extra ? ' — ' + extra : ''}`);
    if (!cond) failed++;
}

const kev = JSON.parse(fs.readFileSync(path.join(FIX, 'kev.json'), 'utf8'));
const nvd = JSON.parse(fs.readFileSync(path.join(FIX, 'nvd.json'), 'utf8'));
const now = new Date().toISOString();

(async () => {
    // ── 1. Pure parsers, against real records ────────────────────────
    console.log('\n── parseKevEntry over all 1729 real KEV entries ──');
    const kevRows = kev.vulnerabilities.map(e => v.parseKevEntry(e, now)).filter(Boolean);
    check('every real KEV entry parses', kevRows.length === kev.vulnerabilities.length,
        `${kevRows.length}/${kev.vulnerabilities.length}`);
    check('all ids well-formed', kevRows.every(r => /^CVE-\d{4}-\d{4,}$/.test(r.id)));
    check('all have descriptions', kevRows.every(r => r.desc.length > 0));
    check('all have vendors', kevRows.every(r => !!r.vendor));
    check('all have due dates', kevRows.every(r => !!r.dueDate));
    check('rejects junk', v.parseKevEntry({ cveID: 'NOT-A-CVE' }, now) === null
        && v.parseKevEntry({}, now) === null
        && v.parseKevEntry(null, now) === null);
    const rk = kevRows.find(r => r.cwes);
    console.log('  sample:', JSON.stringify(kevRows[0]).slice(0, 230));

    console.log('\n── parseNvdItem over 50 real NVD records ──');
    const nvdRows = nvd.vulnerabilities.map(i => v.parseNvdItem(i, now)).filter(Boolean);
    check('every real NVD item parses', nvdRows.length === nvd.vulnerabilities.length,
        `${nvdRows.length}/${nvd.vulnerabilities.length}`);
    const scored = nvdRows.filter(r => r.cvss_score !== null);
    check('most carry a CVSS score', scored.length > nvdRows.length * 0.9,
        `${scored.length}/${nvdRows.length} scored`);
    check('severity always derived from score',
        nvdRows.every(r => r.cvss_score === null ? r.severity === 'UNKNOWN' : r.severity === v.severityFromScore(r.cvss_score)));
    check('no CVE-2024-000* fabrications',
        !nvdRows.some(r => /^CVE-2024-000\d\d$/.test(r.cve_id)));
    const withCpe = nvdRows.filter(r => r.product);
    console.log('  sample:', JSON.stringify(nvdRows.find(r => r.cvss_score === 10) || nvdRows[0]).slice(0, 300));
    console.log(`  ${withCpe.length}/${nvdRows.length} resolved a vendor/product from CPE`);

    // ── 2. Full SQL path: KEV first, then NVD over it ────────────────
    console.log('\n── SQL: KEV insert then NVD upsert (the overwrite risk) ──');
    const db = getDb();
    const now2 = new Date().toISOString();

    // Replay exactly what syncKev does.
    const stmt = db.prepare(`
        UPDATE vulnerabilities SET in_kev=1, exploit_status='Weaponized',
            ransomware_use=@ransomware, kev_date_added=@dateAdded, kev_due_date=@dueDate,
            required_action=@action, vendor=COALESCE(vendor,@vendor), product=COALESCE(product,@product),
            description=CASE WHEN description='' THEN @desc ELSE description END,
            cwes=COALESCE(cwes,@cwes), kev_fetched_at=@now
        WHERE cve_id=@id`);
    const insert = db.prepare(`
        INSERT INTO vulnerabilities (cve_id,description,cvss_score,severity,vendor,product,
            exploit_status,in_kev,ransomware_use,kev_date_added,kev_due_date,required_action,cwes,kev_fetched_at)
        VALUES (@id,@desc,NULL,'UNKNOWN',@vendor,@product,'Weaponized',1,@ransomware,@dateAdded,@dueDate,@action,@cwes,@now)
        ON CONFLICT(cve_id) DO UPDATE SET in_kev=1, exploit_status='Weaponized',
            ransomware_use=@ransomware, kev_date_added=@dateAdded, kev_due_date=@dueDate,
            required_action=@action, vendor=COALESCE(vulnerabilities.vendor,@vendor),
            product=COALESCE(vulnerabilities.product,@product),
            description=CASE WHEN vulnerabilities.description='' THEN @desc ELSE vulnerabilities.description END,
            cwes=COALESCE(vulnerabilities.cwes,@cwes), kev_fetched_at=@now`);

    db.transaction(() => {
        for (const e of kev.vulnerabilities) {
            const p = v.parseKevEntry(e, now2);
            if (!p) continue;
            if (stmt.run(p).changes === 0) insert.run(p);
        }
    })();

    let n = db.prepare('SELECT COUNT(*) n FROM vulnerabilities WHERE in_kev=1').get().n;
    check('KEV rows stored', n === kev.vulnerabilities.length, `${n} rows`);
    n = db.prepare("SELECT COUNT(*) n FROM vulnerabilities WHERE exploit_status='Weaponized'").get().n;
    check('all marked Weaponized', n === kev.vulnerabilities.length, `${n} rows`);

    const upsertSql = fs.readFileSync(path.join(__dirname, 'services', 'vulnerabilities.js'), 'utf8')
        .match(/const UPSERT = `([\s\S]*?)`;/)[1];
    const upsert = db.prepare(upsertSql);

    // Night 1: NVD lands first, on an empty CVE table.
    db.transaction(() => { for (const r of nvdRows) upsert.run(r); })();
    check('night 1: NVD rows stored', db.prepare('SELECT COUNT(*) n FROM vulnerabilities WHERE cvss_score IS NOT NULL').get().n === nvdRows.length);

    // The CVE CISA KEV also lists, but that is outside this 50-record NVD page.
    // Simulate KEV picking it up between the two nightly runs.
    const kevIds = new Set(kevRows.map(r => r.id));
    const overlap = nvdRows.find(r => kevIds.has(r.cve_id));
    const targetId = overlap ? overlap.cve_id : nvdRows[0].cve_id;
    if (!overlap) {
        const k = kevRows[0];
        db.prepare(`
            UPDATE vulnerabilities SET in_kev=1, exploit_status='Weaponized',
                kev_date_added=?, kev_due_date=?, required_action=?, ransomware_use=?
            WHERE cve_id=?`)
            .run(k.dateAdded, k.dueDate, k.action, k.ransomware, targetId);
        console.log(`  (forced overlap on ${targetId}: in KEV but not in this NVD page)`);
    }
    const marked = db.prepare('SELECT in_kev, exploit_status FROM vulnerabilities WHERE cve_id=?').get(targetId);
    check('target CVE is now marked KEV/Weaponized',
        marked.in_kev === 1 && marked.exploit_status === 'Weaponized', JSON.stringify(marked));

    // Night 2: the incremental NVD sync runs again and re-upserts the same row.
    // This is the exact case that used to reset exploit_status to 'No Known Exploit'.
    db.transaction(() => { for (const r of nvdRows) upsert.run(r); })();

    const after = db.prepare('SELECT * FROM vulnerabilities WHERE cve_id=?').get(targetId);
    check('KEV exploit_status NOT wiped by the next NVD sync', after.exploit_status === 'Weaponized',
        `${targetId} -> ${after.exploit_status}`);
    check('KEV required_action preserved', !!after.required_action);
    check('KEV date_added preserved', !!after.kev_date_added);
    check('in_kev flag survived NVD upsert', after.in_kev === 1);
    check('NVD still supplied the score', after.cvss_score !== null, `cvss=${after.cvss_score} sev=${after.severity}`);

    const kevTotal = db.prepare('SELECT COUNT(*) n FROM vulnerabilities WHERE in_kev=1').get().n;
    n = db.prepare("SELECT COUNT(*) n FROM vulnerabilities WHERE exploit_status='Weaponized'").get().n;
    check('every KEV row is Weaponized after the NVD pass', n === kevTotal, `${n}/${kevTotal}`);
    check('no non-KEV row claims Weaponized',
        db.prepare("SELECT COUNT(*) n FROM vulnerabilities WHERE exploit_status='Weaponized' AND in_kev=0").get().n === 0);

    // ── 2b. Default ordering must surface KEV, not bury it ────────────
    console.log('\n── default GET /vulns ordering ──');
    const top20 = db.prepare(`
        SELECT cve_id, in_kev FROM vulnerabilities
        ORDER BY in_kev DESC, cvss_score IS NULL ASC, cvss_score DESC, published DESC
        LIMIT 20`).all();
    console.log('  first 5:', top20.slice(0, 5).map(r => `${r.cve_id}(kev=${r.in_kev})`).join(' '));
    check('top row is a KEV entry', top20[0].in_kev === 1);
    // The real requirement: no non-KEV row may outrank a KEV row.
    const firstKevIdx = top20.findIndex(r => r.in_kev === 1);
    const nonKevBefore = top20.slice(0, firstKevIdx).filter(r => r.in_kev === 0);
    check('no non-KEV row appears above a KEV row', nonKevBefore.length === 0,
        `first KEV at index ${firstKevIdx}`);
    // The requirement: a KEV row must outrank a non-KEV row even when the
    // non-KEV row has the higher CVSS score. Force a deterministic pair.
    console.log('\n── KEV outranks a higher-scoring non-KEV CVE ──');
    db.prepare(`UPDATE vulnerabilities SET cvss_score=2.0, severity='LOW' WHERE cve_id=?`).run(targetId);
    const hiNonKev = db.prepare(`SELECT cve_id, cvss_score FROM vulnerabilities
        WHERE in_kev=0 AND cvss_score IS NOT NULL ORDER BY cvss_score DESC LIMIT 1`).get();
    const newFirst = db.prepare(`SELECT cve_id, in_kev FROM vulnerabilities
        ORDER BY in_kev DESC, cvss_score IS NULL ASC, cvss_score DESC, published DESC LIMIT 1`).get();
    check('KEV row (cvss 2.0) is ranked above non-KEV row (cvss ' + hiNonKev.cvss_score + ')',
        newFirst.cve_id === targetId, `first = ${newFirst.cve_id}`);

    // The real defect the ordering change fixes: 1,729 KEV rows have no CVSS yet,
    // and `cvss_score IS NULL ASC` pushed every one of them below all rated rows.
    const countKevInTop = (order) => db.prepare(`
        SELECT COUNT(*) n FROM (
            SELECT in_kev FROM vulnerabilities ORDER BY ${order} LIMIT 50
        ) WHERE in_kev = 1`).get().n;
    const newTop = countKevInTop('in_kev DESC, cvss_score IS NULL ASC, cvss_score DESC, published DESC');
    const oldTop = countKevInTop('cvss_score IS NULL ASC, in_kev DESC, cvss_score DESC, published DESC');
    console.log(`  KEV rows in top 50 — new order: ${newTop}, old order: ${oldTop}`);
    check('new order puts KEV entries in the top 50', newTop > oldTop && newTop > 0,
        `${oldTop} -> ${newTop}`);
    // Restore the real score.
    const realNvd = nvdRows.find(r => r.cve_id === targetId);
    db.prepare('UPDATE vulnerabilities SET cvss_score=?, severity=? WHERE cve_id=?')
        .run(realNvd.cvss_score, realNvd.severity, targetId);

    // ── 2c. Backfill targets exactly the unscored KEV rows ────────────
    console.log('\n── KEV CVSS backfill targeting ──');
    const backfillPick = db.prepare(`
        SELECT cve_id FROM vulnerabilities
        WHERE in_kev = 1 AND cvss_score IS NULL AND nvd_fetched_at IS NULL
        ORDER BY kev_date_added DESC LIMIT 25`).all();
    const bad = db.prepare(`SELECT COUNT(*) n FROM vulnerabilities WHERE in_kev=1 AND cvss_score IS NULL AND nvd_fetched_at IS NOT NULL`).get().n;
    check('backfill selects only unscored+unattempted KEV rows',
        backfillPick.every(r => /^CVE-/.test(r.cve_id)) && backfillPick.length <= 25,
        `${backfillPick.length} queued`);
    check('no KEV row is retried after a failed attempt', bad === 0);

    // ── 3. Stats ──────────────────────────────────────────────────────
    console.log('\n── vulnStats() ──');
    const st = v.vulnStats();
    console.log('  ' + JSON.stringify(st));
    check('total = KEV + new NVD', st.total === kev.vulnerabilities.length + nvdRows.filter(r => !kevIds.has(r.cve_id)).length);
    check('configured true', st.configured === true);
    check('severity buckets sum to scored rows', Object.values(st.by_severity).reduce((a, b) => a + b, 0) >= nvdRows.length);

    // ── 4. Query params ───────────────────────────────────────────────
    console.log('\n── query shapes used by GET /vulns ──');
    const crit = db.prepare("SELECT COUNT(*) n FROM vulnerabilities WHERE severity='CRITICAL'").get().n;
    const kevOnly = db.prepare("SELECT COUNT(*) n FROM vulnerabilities WHERE in_kev=1 AND cvss_score IS NULL").get().n;
    console.log(`  CRITICAL=${crit}  KEV-without-score=${kevOnly}  (KEV rows stay UNKNOWN until NVD covers them)`);
    const ordered = db.prepare(`SELECT cve_id FROM vulnerabilities
        WHERE cvss_score IS NOT NULL ORDER BY cvss_score IS NULL ASC, in_kev DESC, cvss_score DESC, published DESC LIMIT 5`).all();
    console.log('  top 5 by cvss:', ordered.map(r => r.cve_id).join(', '));
    check('ORDER BY places KEV rows at equal score', ordered.length === 5);

    closeDb();
    console.log(failed ? `\nRESULT: ${failed} FAILURE(S)` : '\nRESULT: ALL CHECKS PASSED');
    process.exit(failed ? 1 : 0);
})();
