/**
 * Job Scheduler (v2 — Budget-Aware)
 * Local NLP runs freely, AI runs only within daily budget
 */
const cron = require('node-cron');
const { ingestNews } = require('../services/ingestion');
const { scrapeTelegramChannels } = require('../services/osint-telegram');
const { scrapeXAccounts } = require('../services/osint-x');
const { scrapeReddit } = require('../services/osint-reddit');
const { processArticles } = require('../services/ai-analysis');
const { runMacroAnalysis } = require('../services/macro-analysis');
const { clusterEvents } = require('../services/clustering');
const { generateAlerts, checkWatchlists } = require('../services/alerts');
const { generateDailyBriefing } = require('../services/daily-briefing');
const { scrapeDarkWeb } = require('../services/dark-web-scraper');
const { generateClusterPredictions, isConfigured: isAiConfigured } = require('../services/prediction-engine');
const { track } = require('../services/source-health');
const { syncVulnerabilities } = require('../services/vulnerabilities');

/**
 * Job overlap guard.
 *
 * OSINT ingestion and NLP analysis both ran on a five-minute cron with no
 * in-flight flag. An OSINT cycle (4 sequential upstreams, up to 10s each)
 * routinely outlasted that interval, so it overlapped the next NLP run — both
 * competing for the same raw_articles rows, which is how 676 alerts
 * accumulated against 838 events and how duplicate NLP work happened.
 */
const running = new Set();

/**
 * Wrap a job so a second invocation cannot start while the first is in flight.
 */
function guard(name, fn) {
    return async (...args) => {
        if (running.has(name)) {
            console.log(`⏭️  Skipping ${name} — previous run still in progress.`);
            return;
        }
        running.add(name);
        try {
            await fn(...args);
        } catch (err) {
            console.error(`❌ ${name} error:`, err.message);
        } finally {
            running.delete(name);
        }
    };
}

function startScheduler() {
    // ─── Daily Briefing (6 AM + 6 PM UTC) ────────────────────
    cron.schedule('0 6,18 * * *', async () => {
        console.log('\n📋 Running Daily Briefing...');
        try {
            await generateDailyBriefing();
        } catch (err) {
            console.error('❌ Daily Briefing error:', err.message);
        }
    });

    console.log('⏰ Starting intelligence scheduler (v2 — Local NLP Primary)...\n');

    // ─── Initial Boot Sequence ────────────────────────────────
    console.log(`[${new Date().toISOString()}] Running initial news ingestion...`);
    ingestNews().then(async () => {
        console.log(`[${new Date().toISOString()}] Processing articles with Local NLP...`);
        try {
            await processArticles(15); // Process more articles since NLP is free
        } catch (err) {
            console.error('❌ Initial Analysis error:', err.message);
        }

        // Generate initial macro briefing 30 seconds after boot
        setTimeout(() => {
            console.log(`[${new Date().toISOString()}] Generating Initial Data-Driven Briefing...`);
            runMacroAnalysis().catch(err => console.error('❌ Initial Macro Analysis error:', err.message));
        }, 30000);
    }).catch(err => console.error('❌ Initial ingestion error:', err.message));

    // ─── News ingestion — every 15 minutes ────────────────────
    cron.schedule('*/15 * * * *', guard('ingestion', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running news ingestion...`);
        await ingestNews();
    }));

    // ─── OSINT Ingestion — every 5 minutes ────────────────────
    cron.schedule('*/5 * * * *', guard('osint', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running OSINT ingestion...`);
        // Each source is tracked independently so /api/health can distinguish
        // "delivering nothing" from "never configured". These were previously
        // failing silently: 455 Reddit 403s, 359 X DNS failures, 91 abuse.ch
        // 401s and 89 ransomware.live 404s in a single log period.
        await track('osint:telegram', () => scrapeTelegramChannels());
        await track('osint:x', () => scrapeXAccounts());
        await track('osint:reddit', () => scrapeReddit());
        await track('osint:darkweb', () => scrapeDarkWeb());
    }));

    // ─── Article Analysis (Local NLP) — every 5 minutes ───────
    cron.schedule('*/5 * * * *', guard('nlp', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running Local NLP analysis...`);
        await processArticles(15);
        generateAlerts();
        checkWatchlists();
    }));

    // ─── Data-Driven Macro Briefing — every 60 minutes ────────
    cron.schedule('0 * * * *', guard('macro', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Generating Data-Driven Briefing...`);
        await runMacroAnalysis();
    }));

    // ─── Event clustering — every 30 minutes ──────────────────
    cron.schedule('*/30 * * * *', guard('clustering', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running event clustering...`);

        const clusterIds = clusterEvents();
        console.log(`   ${clusterIds.length} clusters formed`);

        if (!isAiConfigured()) {
            // Skip the per-cluster loop entirely. It could not produce anything
            // and it was the single largest source of log noise.
            return;
        }

        for (const clusterId of clusterIds) {
            await generateClusterPredictions(clusterId);
        }
    }));

    // ─── Vulnerability intelligence (NVD + CISA KEV) — daily ──
    // NVD is rate limited (5 req / 30 s without a key) and the sync walks pages
    // with a deliberate delay, so this must not run more often than daily.
    cron.schedule('23 3 * * *', guard('vulns', async () => {
        await syncVulnerabilities();
    }));

    // ─── Vulnerability sync on boot ────────────────────────────
    // Deferred 45s so it never competes with the initial ingestion burst. The
    // vulnerability panel used to render 15 invented CVEs because no real feed
    // was ever fetched; without this it is empty until 03:23 UTC.
    setTimeout(() => {
        syncVulnerabilities().catch(err =>
            console.error('❌ Initial vulnerability sync error:', err.message));
    }, 45000);

    console.log('  📰 RSS News ingestion:     every 15 minutes');
    console.log('  📱 OSINT (TG, X, Reddit):  every 5 minutes');
    console.log('  ⚡ Local NLP analysis:     every 5 minutes (FREE)');
    console.log('  🌍 Data-Driven Briefing:   every 60 minutes (FREE)');
    console.log('  🔗 Event clustering:       every 30 minutes');
    console.log('  🛡️  NVD + CISA KEV vulns:  daily 03:23 UTC (on boot)');
    console.log('  📋 Daily Briefing:         6 AM + 6 PM UTC');
    console.log('  🧠 AI Enhancement:         budget-limited (auto)\n');
}

module.exports = { startScheduler };
