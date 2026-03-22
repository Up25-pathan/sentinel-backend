/**
 * Predictive Intelligence Engine
 * Generates forecasts and second-order effect analysis for geopolitical clusters.
 */
const Groq = require('groq-sdk');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');
require('dotenv').config();

let groq = null;
function getGroq() {
    if (!groq && process.env.GROQ_API_KEY) {
        groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
    }
    return groq;
}

/**
 * Generate predictions for a cluster of related events
 * @param {string} clusterId 
 */
async function generateClusterPredictions(clusterId) {
    const db = getDb();
    const client = getGroq();

    if (!client) {
        console.warn('⚠️ Predictions: AI client not configured.');
        return;
    }

    // Get all events in this cluster
    const events = db.prepare('SELECT * FROM events WHERE cluster_id = ?').all(clusterId);
    if (events.length === 0) return;

    console.log(`🔮 Predictive Engine: Analyzing cluster [${clusterId}] (${events.length} events)...`);

    try {
        const eventsContext = events.map(e => `- [${e.category}] ${e.title}: ${e.summary}`).join('\n');
        
        const prompt = `
        You are a Senior Intelligence Predictor specializing in Geopolitical Risk.
        
        SITUATION CONTEXT (Cluster Intelligence):
        ${eventsContext}

        TASK: Analyze these events and forecast the "Second-Order Effects" (collateral impacts). 
        Focus on:
        1. Macro-economic impact (Commodity prices, market stability).
        2. Geopolitical escalation (Alliances, retaliations).
        3. Human/Civil impact (Migration, protests).

        OUTPUT FORMAT (JSON ONLY):
        {
          "predictions": [
            {
              "text": "Prediction description...",
              "probability": 0.0-1.0,
              "impact_level": "CRITICAL/HIGH/MEDIUM/LOW",
              "categories": ["ENERGY", "STABILITY", "DIPLOMACY"]
            }
          ]
        }
        `;

        const completion = await client.chat.completions.create({
            model: 'llama-3.1-70b-versatile',
            messages: [{ role: 'user', content: prompt }],
            response_format: { type: 'json_object' },
            temperature: 0.2
        });

        const data = JSON.parse(completion.choices[0].message.content);

        // Save predictions
        db.transaction(() => {
            for (const pred of data.predictions || []) {
                db.prepare(`
                    INSERT INTO predictions (id, cluster_id, event_id, prediction_text, probability, impact_level, categories_affected)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                `).run(
                    uuidv4(),
                    clusterId,
                    events[0].id, // Link to the primary event in cluster
                    pred.text,
                    pred.probability,
                    pred.impact_level,
                    JSON.stringify(pred.categories)
                );
            }
        })();

        console.log(`✅ Predictive Engine: Generated ${data.predictions?.length || 0} forecasts.`);

    } catch (err) {
        console.error('❌ Predictive Engine Error:', err.message);
    }
}

module.exports = { generateClusterPredictions };
