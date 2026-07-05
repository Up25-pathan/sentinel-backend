/**
 * AI Analysis Pipeline (v2 — Local NLP First)
 * Uses local NLP engine as primary (zero API calls)
 * Optionally enhances CRITICAL events with Groq AI (budget-limited)
 */
const Groq = require('groq-sdk');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');
const { fetchEventImages } = require('./image-scraper');
const { analyzeLocal, extractNexusEntities } = require('./local-nlp');
const { processEventNexusLocal } = require('./nexus');
require('dotenv').config();

let groq = null;

// ─── AI Budget Limiter ──────────────────────────────────────────
// Only allow max AI_DAILY_BUDGET calls per day to prevent quota exhaustion
const AI_DAILY_BUDGET = parseInt(process.env.AI_DAILY_BUDGET) || 20;
let aiCallsToday = 0;
let lastResetDate = new Date().toDateString();

function checkAndResetBudget() {
    const today = new Date().toDateString();
    if (today !== lastResetDate) {
        aiCallsToday = 0;
        lastResetDate = today;
        console.log('🔄 AI budget reset for new day.');
    }
}

function canUseAI() {
    checkAndResetBudget();
    return aiCallsToday < AI_DAILY_BUDGET;
}

function recordAICall() {
    aiCallsToday++;
    console.log(`  💰 AI Budget: ${aiCallsToday}/${AI_DAILY_BUDGET} calls used today.`);
}

function getGroq() {
    if (!groq && process.env.GROQ_API_KEY) {
        groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
    }
    return groq;
}

/**
 * Enhance with AI only for high-value events (budget-limited)
 */
async function enhanceWithAI(article, localAnalysis) {
    const ai = getGroq();
    if (!ai || !canUseAI()) return localAnalysis;

    // Only spend AI budget on CRITICAL/HIGH risk events
    if (localAnalysis.risk_level !== 'CRITICAL' && localAnalysis.risk_level !== 'HIGH') {
        return localAnalysis;
    }

    try {
        const prompt = `
You are a senior military intelligence officer. Analyze this event and provide a deep intelligence brief.
Respond with ONLY valid JSON. NO markdown formatting.

Title: ${article.title}
Description: ${article.description}
Source: ${article.source_name}
Local Analysis Category: ${localAnalysis.category}
Local Analysis Risk: ${localAnalysis.risk_level}
Detected Entities: ${JSON.stringify(localAnalysis.entities)}

Respond strictly matching this JSON schema:
{
    "ai_brief": "Write a massive, deep, multi-paragraph tactical intelligence brief. Minimum 3 paragraphs.",
    "escalation_score": 0-100,
    "second_order_effects": ["Effect 1", "Effect 2", "Effect 3"],
    "bias_analysis": "Source reliability assessment.",
    "location_name": "Most specific location name",
    "lat": latitude_or_null,
    "lng": longitude_or_null
}`;

        const response = await ai.chat.completions.create({
            model: 'llama-3.1-8b-instant',
            messages: [{ role: 'user', content: prompt }],
            temperature: 0.3,
            max_tokens: 600,
            response_format: { type: 'json_object' }
        });

        recordAICall();
        const aiResult = JSON.parse(response.choices[0].message.content.trim());

        // Merge AI enhancements with local analysis (local provides structure, AI provides depth)
        return {
            ...localAnalysis,
            ai_brief: aiResult.ai_brief || localAnalysis.ai_brief,
            escalation_score: aiResult.escalation_score || localAnalysis.escalation_score,
            second_order_effects: aiResult.second_order_effects?.length > 0
                ? aiResult.second_order_effects
                : localAnalysis.second_order_effects,
            bias_analysis: aiResult.bias_analysis || localAnalysis.bias_analysis,
            // Only override geo if AI provides and local didn't
            lat: localAnalysis.lat || aiResult.lat,
            lng: localAnalysis.lng || aiResult.lng,
            location_name: localAnalysis.location_name || aiResult.location_name,
        };
    } catch (err) {
        console.warn('  ⚠️ AI enhancement failed, using local analysis:', err.message);
        return localAnalysis;
    }
}

/**
 * Process unprocessed raw articles
 */
async function processArticles(batchSize = 10) {
    const db = getDb();

    const articles = db.prepare(`
        SELECT * FROM raw_articles 
        WHERE processed = 0 
        ORDER BY published_at DESC 
        LIMIT ?
    `).all(batchSize);

    if (articles.length === 0) {
        console.log('  ℹ️ No unprocessed articles found.');
        return 0;
    }

    console.log(`\n🧠 Analyzing ${articles.length} articles (Local NLP + optional AI)...`);
    checkAndResetBudget();
    console.log(`  💰 AI Budget: ${aiCallsToday}/${AI_DAILY_BUDGET} used today.`);

    const insertEvent = db.prepare(`
        INSERT INTO events (id, title, summary, ai_brief, category, risk_level, 
            location_name, country, lat, lng, image_url, images_json, is_breaking, entities_json, 
            escalation_score, second_order_effects, bias_analysis, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const insertSource = db.prepare(`
        INSERT INTO sources (id, event_id, name, url, credibility, published_at)
        VALUES (?, ?, ?, ?, ?, ?)
    `);

    const markProcessed = db.prepare('UPDATE raw_articles SET processed = 1 WHERE id = ?');

    let processed = 0;

    for (const article of articles) {
        try {
            // Step 1: Local NLP analysis (instant, free)
            const localAnalysis = analyzeLocal(article);

            // Skip non-geopolitical events
            if (localAnalysis.category === 'OTHER') {
                markProcessed.run(article.id);
                continue;
            }

            // Step 2: Optional AI enhancement (budget-limited, only for critical events)
            const analysis = await enhanceWithAI(article, localAnalysis);

            const eventId = uuidv4();
            const now = new Date().toISOString().replace('T', ' ').replace('Z', '');
            const isBreaking = ['CRITICAL'].includes(analysis.risk_level) ? 1 : 0;

            // Country from analysis
            const country = analysis.country || analysis.entities?.countries?.[0] || null;

            // Fetch extra images
            const searchQuery = `${analysis.location_name || country || ''} ${analysis.category.replace('_', ' ')} geopolitical`.trim();
            const images = await fetchEventImages(searchQuery);

            insertEvent.run(
                eventId,
                article.title,
                analysis.summary,
                analysis.ai_brief,
                analysis.category,
                analysis.risk_level,
                analysis.location_name,
                country,
                analysis.lat,
                analysis.lng,
                images.length > 0 ? images[0] : article.image_url,
                JSON.stringify(images),
                isBreaking,
                JSON.stringify(analysis.entities || {}),
                analysis.escalation_score || 0,
                JSON.stringify(analysis.second_order_effects || []),
                analysis.bias_analysis || "Analysis pending.",
                now,
                now
            );

            // Step 3: Local Nexus entity extraction (instant, free)
            processEventNexusLocal({
                id: eventId,
                title: article.title,
                summary: analysis.summary,
                category: analysis.category,
                location_name: analysis.location_name,
                country: country
            });

            insertSource.run(
                uuidv4(),
                eventId,
                article.source_name || 'Unknown',
                article.url,
                'MEDIUM',
                article.published_at
            );

            markProcessed.run(article.id);
            processed++;

            const aiTag = analysis.ai_brief !== localAnalysis?.ai_brief ? '🧠AI+' : '⚡NLP';
            console.log(`  ✅ [${aiTag}] ${analysis.category} [${analysis.risk_level}]: ${article.title.substring(0, 55)}...`);

        } catch (err) {
            console.error(`  ❌ Failed to analyze: ${article.title} `, err.message);
            markProcessed.run(article.id);
        }
    }

    console.log(`✅ Analysis complete: ${processed}/${articles.length} articles processed.\n`);
    return processed;
}

module.exports = { processArticles, enhanceWithAI, analyzeLocal };
