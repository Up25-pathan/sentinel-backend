/**
 * Macro Analysis Service (v2 — Data-Driven)
 * Generates global briefings from database statistics (no AI required)
 * Optionally enhances daily briefing with AI (1 call/day max)
 */
const Groq = require('groq-sdk');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');
const { generateLocalMacroBriefing } = require('./local-nlp');

let groq = null;
function getGroq() {
    if (!groq && process.env.GROQ_API_KEY) {
        groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
    }
    return groq;
}

async function runMacroAnalysis() {
    const db = getDb();
    console.log('\n🌍 Starting Macro-Level Briefing...');

    const recentEvents = db.prepare(`
        SELECT title, summary, category, risk_level, country, escalation_score, second_order_effects
        FROM events 
        ORDER BY created_at DESC 
        LIMIT 25
    `).all();

    if (recentEvents.length === 0) {
        console.log('  ℹ️ No recent events. Skipping global briefing.');
        return;
    }

    // Step 1: Always generate data-driven briefing (free, instant)
    const localBriefing = generateLocalMacroBriefing(recentEvents);
    const now = new Date().toISOString().replace('T', ' ').replace('Z', '');

    db.prepare(`
        INSERT INTO global_briefings (id, global_risk_score, major_situations_json, macro_predictions_json, created_at)
        VALUES (?, ?, ?, ?, ?)
    `).run(
        uuidv4(),
        localBriefing.global_risk_score,
        JSON.stringify(localBriefing.major_situations),
        JSON.stringify(localBriefing.macro_predictions),
        now
    );

    console.log(`✅ Macro Briefing complete [DATA-DRIVEN]. Global Risk: ${localBriefing.global_risk_score}%`);
    console.log(`   Active situations: ${localBriefing.major_situations.length}, Predictions: ${localBriefing.macro_predictions.length}\n`);
}

module.exports = { runMacroAnalysis };
