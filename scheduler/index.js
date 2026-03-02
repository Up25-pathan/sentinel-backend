/**
 * Job Scheduler
 * Runs intelligence pipeline tasks on cron schedules
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

function startScheduler() {
    // ─── 6. Daily Briefing ─────────────────────────────────
    // Run at 6 AM UTC daily + every 12 hours
    cron.schedule('0 6,18 * * *', async () => {
        console.log('\n📋 Running Daily Briefing...');
        try {
            await generateDailyBriefing();
        } catch (err) {
            console.error('❌ Daily Briefing error:', err.message);
        }
    });

    console.log('⏰ Starting intelligence scheduler...\n');

    // Run initial ingestion immediately
    console.log(`[${new Date().toISOString()}] Running initial news ingestion...`);
    ingestNews().then(async () => {
        console.log(`[${new Date().toISOString()}] Generating initial intelligence events...`);
        try {
            await processArticles(10);
        } catch (err) {
            console.error('❌ Initial Analysis error:', err.message);
        }

        // Run initial macro analysis exactly 1 minute after boot (so events have populated)
        setTimeout(() => {
            console.log(`[${new Date().toISOString()}] Generating Initial Global AI Briefing...`);
            runMacroAnalysis().catch(err => console.error('❌ Initial Macro Analysis error:', err.message));
        }, 60000);
    }).catch(err => console.error('❌ Initial ingestion error:', err.message));

    // News ingestion — every 15 minutes
    cron.schedule('*/15 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running news ingestion...`);
        try {
            await ingestNews();
        } catch (err) {
            console.error('❌ Ingestion error:', err.message);
        }
    });

    // OSINT Ingestion (Telegram + X) — every 5 minutes (faster than RSS)
    cron.schedule('*/5 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running OSINT ingestion (Telegram & X)...`);
        try {
            await scrapeTelegramChannels();
            await scrapeXAccounts();
            await scrapeReddit();
        } catch (err) {
            console.error('❌ OSINT Ingestion error:', err.message);
        }
    });

    // AI analysis — every 5 minutes
    cron.schedule('*/5 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running AI analysis...`);
        try {
            await processArticles(10);
            generateAlerts();
            checkWatchlists();
        } catch (err) {
            console.error('❌ Analysis error:', err.message);
        }
    });

    // Global AI Briefing — every 60 minutes
    cron.schedule('0 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Generating Global AI Briefing...`);
        try {
            await runMacroAnalysis();
        } catch (err) {
            console.error('❌ Macro Analysis error:', err.message);
        }
    });

    // Event clustering — every 30 minutes
    cron.schedule('*/30 * * * *', () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running event clustering...`);
        try {
            clusterEvents();
        } catch (err) {
            console.error('❌ Clustering error:', err.message);
        }
    });

    console.log('  📰 RSS News ingestion: every 15 minutes');
    console.log('  📱 OSINT (TG, X, Reddit): every 5 minutes');
    console.log('  🧠 AI analysis:      every 5 minutes');
    console.log('  🌍 Global AI Briefing: every 60 minutes');
    console.log('  🔗 Event clustering: every 30 minutes');
    console.log('  📋 Daily Briefing:   6 AM + 6 PM UTC');
    console.log('  🚨 Alert generation: after each analysis\n');
}

module.exports = { startScheduler };
