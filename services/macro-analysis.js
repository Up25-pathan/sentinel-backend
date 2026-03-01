const { GoogleGenAI } = require('@google/genai');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

let gemini = null;
function getGemini() {
    if (!gemini && process.env.GEMINI_API_KEY) {
        gemini = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    }
    return gemini;
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

    const ai = getGemini();
    if (!ai) {
        console.warn('  ⚠️ No Gemini API key configured. Creating fallback macro analysis.');
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
        const prompt = `You are the Director of Global Intelligence. You synthesize individual news events into a cohesive, macro-level global situation report. Analyze the provided top 15 recent global events and return a strict JSON response. Do NOT use markdown code blocks like \`\`\`json. You MUST return major_situations and macro_predictions as JSON Arrays.

Top 15 Recent Intelligence Events:
${eventsPrompt}

Respond with strictly this JSON format, do not add or omit fields:
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
}`;

        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: prompt,
            config: {
                temperature: 0.4,
                responseMimeType: 'application/json'
            }
        });

        // Clean out any accidental markdown blocks that sometimes sneak past the instructions
        let rawText = response.text;
        if (rawText.startsWith('```json')) {
            rawText = rawText.substring(7);
        }
        if (rawText.endsWith('```')) {
            rawText = rawText.substring(0, rawText.length - 3);
        }

        const analysis = JSON.parse(rawText.trim());
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
                { flashpoint: "System Degraded: API Quota Exceeded", description: `Gemini rejected the request: ${err.message}. Please check your Google Cloud Console for quota limits.` }
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
