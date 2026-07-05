/**
 * Daily Briefing Service
 * Generates a personalized morning intelligence briefing
 * summarizing the most important events from the past 24 hours.
 */
const Groq = require('groq-sdk');
const { getDb } = require('../db');
require('dotenv').config();

let groq = null;

function getGroq() {
    if (!groq && process.env.GROQ_API_KEY) {
        groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
    }
    return groq;
}

/**
 * Generate the daily intelligence briefing
 */
async function generateDailyBriefing() {
    const db = getDb();
    console.log('\n📋 Generating Daily Intelligence Briefing...');

    // Get events from the last 24 hours
    const recentEvents = db.prepare(`
        SELECT title, summary, category, risk_level, location_name,
               is_breaking, escalation_score, created_at
        FROM events
        WHERE created_at > datetime('now', '-24 hours')
        ORDER BY 
            CASE risk_level 
                WHEN 'CRITICAL' THEN 1 
                WHEN 'HIGH' THEN 2 
                WHEN 'MEDIUM' THEN 3 
                ELSE 4 
            END,
            is_breaking DESC,
            created_at DESC
        LIMIT 20
    `).all();

    if (recentEvents.length === 0) {
        console.log('  No events in last 24 hours, skipping briefing.');
        return null;
    }

    // Category breakdown
    const categoryBreakdown = db.prepare(`
        SELECT category, COUNT(*) as count, 
               AVG(CASE risk_level 
                   WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 
                   WHEN 'MEDIUM' THEN 2 ELSE 1 END) as avg_risk
        FROM events
        WHERE created_at > datetime('now', '-24 hours')
        GROUP BY category
        ORDER BY count DESC
    `).all();

    // Build context
    const eventList = recentEvents.map(e =>
        `[${e.category}] [${e.risk_level}]${e.is_breaking ? ' [BREAKING]' : ''} ${e.title}` +
        (e.location_name ? ` (${e.location_name})` : '') +
        (e.escalation_score ? ` — Escalation: ${e.escalation_score}%` : '')
    ).join('\n');

    const catSummary = categoryBreakdown.map(c =>
        `${c.category}: ${c.count} events (avg risk: ${c.avg_risk.toFixed(1)}/4)`
    ).join(', ');

    const client = getGroq();

    if (!client) {
        // Fallback briefing
        return buildFallbackBriefing(recentEvents, categoryBreakdown);
    }

    try {
        const completion = await client.chat.completions.create({
            model: 'llama-3.1-8b-instant',
            messages: [
                {
                    role: 'system',
                    content: `You are SENTINEL, a geopolitical intelligence briefing system. Generate a concise morning briefing.`
                },
                {
                    role: 'user',
                    content: `Generate a DAILY INTELLIGENCE BRIEFING for the past 24 hours.

Events (${recentEvents.length} total):
${eventList}

Category Distribution: ${catSummary}

Format your briefing as:
1. EXECUTIVE SUMMARY (2-3 sentences overview)
2. CRITICAL DEVELOPMENTS (top 3-5 events that demand attention)
3. REGIONAL HOTSPOTS (which regions are most active)
4. RISK OUTLOOK (what to watch in the next 24 hours)

Be concise and analytical. Use intelligence-style language.`
                }
            ],
            temperature: 0.4,
            max_tokens: 800,
        });

        const briefingText = completion.choices[0]?.message?.content || '';

        // Store the briefing
        const briefingData = {
            text: briefingText,
            eventCount: recentEvents.length,
            categories: categoryBreakdown,
            generatedAt: new Date().toISOString(),
            model: 'llama-3.1-8b'
        };

        // Save to database (reuse global_briefings table)
        db.prepare(`
            INSERT INTO global_briefings (id, briefing_data, created_at)
            VALUES (?, ?, datetime('now'))
        `).run(
            `daily-${new Date().toISOString().split('T')[0]}`,
            JSON.stringify(briefingData)
        );

        console.log('✅ Daily briefing generated.');
        return briefingData;

    } catch (err) {
        console.error('Daily briefing error:', err.message);
        return buildFallbackBriefing(recentEvents, categoryBreakdown);
    }
}

function buildFallbackBriefing(events, categories) {
    const criticalEvents = events.filter(e => e.risk_level === 'CRITICAL' || e.risk_level === 'HIGH');
    const breakingEvents = events.filter(e => e.is_breaking);

    let text = `📋 DAILY INTELLIGENCE BRIEFING\n`;
    text += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
    text += `EXECUTIVE SUMMARY\n`;
    text += `${events.length} events tracked in the last 24 hours. `;
    text += `${criticalEvents.length} classified as Critical/High risk. `;
    text += `${breakingEvents.length} breaking developments.\n\n`;

    text += `CRITICAL DEVELOPMENTS\n`;
    criticalEvents.slice(0, 5).forEach(e => {
        text += `• [${e.risk_level}] ${e.title}\n`;
        if (e.location_name) text += `  📍 ${e.location_name}\n`;
    });

    text += `\nCATEGORY BREAKDOWN\n`;
    categories.forEach(c => {
        text += `• ${c.category}: ${c.count} events\n`;
    });

    return {
        text,
        eventCount: events.length,
        categories,
        generatedAt: new Date().toISOString(),
        model: 'fallback'
    };
}

/**
 * Get the latest daily briefing from the database
 */
function getLatestDailyBriefing() {
    const db = getDb();
    const briefing = db.prepare(`
        SELECT * FROM global_briefings
        WHERE id LIKE 'daily-%'
        ORDER BY created_at DESC
        LIMIT 1
    `).get();

    if (briefing && briefing.briefing_data) {
        return JSON.parse(briefing.briefing_data);
    }
    return null;
}

module.exports = { generateDailyBriefing, getLatestDailyBriefing };
