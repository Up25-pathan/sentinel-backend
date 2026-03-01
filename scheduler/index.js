/**
 * Job Scheduler
 * Runs intelligence pipeline tasks on cron schedules
 */
const cron = require('node-cron');
const { ingestNews } = require('../services/ingestion');
const { processArticles } = require('../services/ai-analysis');
const { clusterEvents } = require('../services/clustering');
const { generateAlerts } = require('../services/alerts');

function startScheduler() {
    console.log('⏰ Starting intelligence scheduler...\n');

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

    // AI analysis — every 5 minutes
    cron.schedule('*/5 * * * *', async () => {
        console.log('─'.repeat(50));
        console.log(`[${new Date().toISOString()}] Running AI analysis...`);
        try {
            await processArticles(10);
            generateAlerts();
        } catch (err) {
            console.error('❌ Analysis error:', err.message);
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

    console.log('  📰 News ingestion:  every 15 minutes');
    console.log('  🧠 AI analysis:     every 5 minutes');
    console.log('  🔗 Event clustering: every 30 minutes');
    console.log('  🚨 Alert generation: after each analysis\n');
}

module.exports = { startScheduler };
