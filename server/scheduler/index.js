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
    cron.schedule('*/15 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running news ingestion...`);
        try {
            await ingestNews();
        } catch (err) {
            console.error('❌ Ingestion error:', err.message);
        }
    });

    // ─── OSINT Ingestion — every 5 minutes ────────────────────
    cron.schedule('*/5 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running OSINT ingestion...`);
        try {
            await scrapeTelegramChannels();
            await scrapeXAccounts();
            await scrapeReddit();
            await scrapeDarkWeb();
        } catch (err) {
            console.error('❌ OSINT Ingestion error:', err.message);
        }
    });

    // ─── Article Analysis (Local NLP) — every 5 minutes ───────
    cron.schedule('*/5 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running Local NLP analysis...`);
        try {
            await processArticles(15);
            generateAlerts();
            checkWatchlists();
        } catch (err) {
            console.error('❌ Analysis error:', err.message);
        }
    });

    // ─── Data-Driven Macro Briefing — every 60 minutes ────────
    cron.schedule('0 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Generating Data-Driven Briefing...`);
        try {
            await runMacroAnalysis();
        } catch (err) {
            console.error('❌ Macro Analysis error:', err.message);
        }
    });

    // ─── Event clustering — every 30 minutes ──────────────────
    cron.schedule('*/30 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running event clustering...`);
        try {
            const clusterIds = clusterEvents();
            
            const { generateClusterPredictions } = require('../services/prediction-engine');
            for (const clusterId of clusterIds) {
                await generateClusterPredictions(clusterId);
            }
        } catch (err) {
            console.error('❌ Clustering/Prediction error:', err.message);
        }
    });

    console.log('  📰 RSS News ingestion:     every 15 minutes');
    console.log('  📱 OSINT (TG, X, Reddit):  every 5 minutes');
    console.log('  ⚡ Local NLP analysis:     every 5 minutes (FREE)');
    console.log('  🌍 Data-Driven Briefing:   every 60 minutes (FREE)');
    console.log('  🔗 Event clustering:       every 30 minutes');
    console.log('  📋 Daily Briefing:         6 AM + 6 PM UTC');
    console.log('  🧠 AI Enhancement:         budget-limited (auto)\n');
}

module.exports = { startScheduler };
