const OpenAI = require('openai');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

let openai = null;
function getOpenAI() {
    if (!openai && process.env.OPENAI_API_KEY) {
        openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    }
    return openai;
}

async function runMacroAnalysis() {
    const db = getDb();
    console.log('\n🌍 Starting Macro-Level AI Briefing...');

    const recentEvents = db.prepare(`
        SELECT title, summary, category, risk_level, escalation_score, second_order_effects
        FROM events 
        ORDER BY created_at DESC 
        LIMIT 15
    `).all();

    if (recentEvents.length === 0) {
        console.log('  ℹ️ No recent events. Skipping global briefing.');
        return;
    }

    const client = getOpenAI();
    if (!client) {
        console.warn('  ⚠️ No OpenAI key configured. Creating fallback macro analysis.');
        const mockBriefing = {
            id: uuidv4(),
            global_risk_score: 65,
            major_situations_json: JSON.stringify([
                { flashpoint: "Global Uncertainty", description: "Simulated global tension due to missing API key. Data cannot be fully analyzed." }
            ]),
            macro_predictions_json: JSON.stringify([
                "Ongoing instability expected.",
                "Market volatility likely."
            ]),
            created_at: new Date().toISOString().replace('T', ' ').replace('Z', '')
        };
        db.prepare(`
            INSERT INTO global_briefings (id, global_risk_score, major_situations_json, macro_predictions_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        `).run(mockBriefing.id, mockBriefing.global_risk_score, mockBriefing.major_situations_json, mockBriefing.macro_predictions_json, mockBriefing.created_at);
        return;
    }

    try {
        const eventsPrompt = recentEvents.map(e => `[${e.risk_level}] ${e.category} - ${e.title}: ${e.summary}`).join('\n');

        const response = await client.chat.completions.create({
            model: 'gpt-3.5-turbo',
            messages: [
                {
                    role: 'system',
                    content: `You are the Director of Global Intelligence. You synthesize individual news events into a cohesive, macro-level global situation report. Analyze the provided top 15 recent global events and return a strict JSON response.`
                },
                {
                    role: 'user',
                    content: `Top 15 Recent Intelligence Events:\n${eventsPrompt}\n\nRespond with strict JSON format:
{
    "global_risk_score": 0-100 (integer representing overall global instability and escalation risk),
    "major_situations": [
        {
            "flashpoint": "Short title of the conflict/situation (e.g., Middle East Escalation)",
            "description": "2-3 sentences synthesizing the current state of this specific flashpoint based on the provided events."
        }
    ],
    "macro_predictions": [
        "Prediction 1 (e.g., Global energy markets will face severe disruption if X continues)",
        "Prediction 2",
        "Prediction 3"
    ]
}`
                }
            ],
            temperature: 0.4,
            response_format: { type: 'json_object' }
        });

        const analysis = JSON.parse(response.choices[0].message.content);
        const now = new Date().toISOString().replace('T', ' ').replace('Z', '');

        db.prepare(`
            INSERT INTO global_briefings (id, global_risk_score, major_situations_json, macro_predictions_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        `).run(
            uuidv4(),
            analysis.global_risk_score || 50,
            JSON.stringify(analysis.major_situations || []),
            JSON.stringify(analysis.macro_predictions || []),
            now
        );

        console.log(`✅ Macro Analysis complete. Global Risk: ${analysis.global_risk_score}%\n`);

    } catch (err) {
        console.error('  ❌ Macro Analysis Failed:', err.message);
        const errBriefing = {
            id: uuidv4(),
            global_risk_score: 50,
            major_situations_json: JSON.stringify([
                { flashpoint: "System Degraded: API Quota Exceeded", description: `OpenAI rejected the request: ${err.message}. Please check your OpenAI billing plan and add credits.` }
            ]),
            macro_predictions_json: JSON.stringify([
                "Predictive AI layer is temporarily offline."
            ]),
            created_at: new Date().toISOString().replace('T', ' ').replace('Z', '')
        };
        db.prepare(`
            INSERT INTO global_briefings (id, global_risk_score, major_situations_json, macro_predictions_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        `).run(errBriefing.id, errBriefing.global_risk_score, errBriefing.major_situations_json, errBriefing.macro_predictions_json, errBriefing.created_at);
    }
}

module.exports = { runMacroAnalysis };
