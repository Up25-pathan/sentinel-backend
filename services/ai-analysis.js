/**
 * AI Analysis Pipeline
 * Uses OpenAI to classify, summarize, and extract entities from raw articles
 */
const { GoogleGenAI } = require('@google/genai');
const Groq = require('groq-sdk');
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');
const { fetchEventImages } = require('./image-scraper');
require('dotenv').config();

let groq = null;

function getGroq() {
    if (!groq && process.env.GROQ_API_KEY) {
        groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
    }
    return groq;
}

// Fallback analysis when OpenAI is not configured
function fallbackAnalysis(article) {
    const text = `${article.title} ${article.description}`.toLowerCase();

    // Simple keyword-based classification
    let category = 'OTHER';
    let risk_level = 'LOW';

    if (/war|combat|battle|fighting|offensive/.test(text)) { category = 'WAR'; risk_level = 'CRITICAL'; }
    else if (/military|troops|deploy|navy|airforce|army/.test(text)) { category = 'MILITARY_MOVEMENT'; risk_level = 'HIGH'; }
    else if (/sanction|embargo|restrict|ban|freeze/.test(text)) { category = 'SANCTIONS'; risk_level = 'HIGH'; }
    else if (/coup|overthrow|seize|junta|takeover/.test(text)) { category = 'COUP'; risk_level = 'CRITICAL'; }
    else if (/nuclear|atomic|warhead|enrichment|icbm/.test(text)) { category = 'NUCLEAR_THREAT'; risk_level = 'CRITICAL'; }
    else if (/diplomat|ambassador|negotiat|summit|talks/.test(text)) { category = 'DIPLOMATIC_ESCALATION'; risk_level = 'MEDIUM'; }
    else if (/terror|bomb|explosion|attack|suicide/.test(text)) { category = 'TERRORISM'; risk_level = 'HIGH'; }
    else if (/cyber|hack|breach|malware|ransomware/.test(text)) { category = 'CYBER_ATTACK'; risk_level = 'HIGH'; }
    else if (/protest|unrest|riot|uprising|destabili/.test(text)) { category = 'POLITICAL_INSTABILITY'; risk_level = 'MEDIUM'; }
    else if (/humanitarian|famine|refugee|displacement|aid/.test(text)) { category = 'HUMANITARIAN'; risk_level = 'MEDIUM'; }

    return {
        category,
        risk_level,
        summary: article.description || article.title,
        ai_brief: `Intelligence assessment: ${article.title}. Category: ${category}. Risk: ${risk_level}. Source: ${article.source_name}.`,
        entities: { countries: [], cities: [], leaders: [], organizations: [] },
        location_name: null,
        lat: null,
        lng: null
    };
}

/**
 * Analyze a single article using OpenAI
 */
async function analyzeWithAI(article) {
    const ai = getGroq();

    if (!ai) {
        return fallbackAnalysis(article);
    }

    try {
        const prompt = `
You are a senior military intelligence officer stationed at a global command center. Your job is to analyze incoming raw situational data (often fragmented or biased) and produce actionable, highly detailed tactical intelligence briefs.

Respond with ONLY valid JSON. Absolutely NO markdown formatting, NO code block ticks.

Title: ${article.title}
Description: ${article.description}
Source: ${article.source_name}

Respond strictly matching this JSON schema:
{
    "category": "WAR|MILITARY_MOVEMENT|SANCTIONS|COUP|DIPLOMATIC_ESCALATION|NUCLEAR_THREAT|POLITICAL_INSTABILITY|TERRORISM|CYBER_ATTACK|HUMANITARIAN|OTHER",
    "risk_level": "CRITICAL|HIGH|MEDIUM|LOW",
    "summary": "Create a distinct, sharp, 1-sentence headline/TL;DR summarizing the core event.",
    "ai_brief": "Write a massive, deep, multi-paragraph tactical intelligence brief. It must read like a classified military dossier. Analyze the strategic implications, historical context, potential motives, and immediate fallout. Minimum 3 paragraphs.",
    "escalation_score": 0-100 (integer representing probability of near-term kinetic escalation),
    "second_order_effects": ["Geopolitical Effect 1", "Economic Effect 2", "Strategic Effect 3"],
    "bias_analysis": "Sentence evaluating potential reporting bias or state narrative of the source.",
    "entities": {
        "countries": ["list of countries"],
        "cities": ["list of cities"],
        "leaders": ["list of leaders/officials"],
        "organizations": ["list of organizations"]
    },
    "location_name": "Primary location name",
    "lat": latitude_number_or_null,
    "lng": longitude_number_or_null
}`;

        const response = await ai.chat.completions.create({
            model: 'llama3-8b-8192',
            messages: [{ role: 'user', content: prompt }],
            temperature: 0.3,
            max_tokens: 800,
            response_format: { type: 'json_object' }
        });

        const rawText = response.choices[0].message.content;
        return JSON.parse(rawText.trim());
    } catch (err) {
        console.warn('  ⚠️ Groq analysis failed, using fallback:', err.message);
        return fallbackAnalysis(article);
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

    console.log(`\n🧠 Analyzing ${articles.length} articles...`);

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
            const analysis = await analyzeWithAI(article);

            if (analysis.category === 'OTHER') {
                markProcessed.run(article.id);
                continue;
            }

            const eventId = uuidv4();
            const now = new Date().toISOString().replace('T', ' ').replace('Z', '');
            const isBreaking = ['CRITICAL'].includes(analysis.risk_level) ? 1 : 0;

            // Extract country from entities
            const country = analysis.entities?.countries?.[0] || null;

            // Fetch extra context images via Headless Scraper
            const searchQuery = `${analysis.location_name || country || ''} ${analysis.category.replace('_', ' ')} geopolitical conflict`.trim();
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

            console.log(`  ✅ ${analysis.category} [${analysis.risk_level}]: ${article.title.substring(0, 60)}...`);

            // Groq has 14,400 Requests/Day and 30 RPM on the free tier.
            // 2 second delay keeps us exactly at 30 RPM without exhausting the massive daily limit.
            if (processed < articles.length && process.env.GROQ_API_KEY) {
                await new Promise(resolve => setTimeout(resolve, 2050));
            }
        } catch (err) {
            console.error(`  ❌ Failed to analyze: ${article.title} `, err.message);
            markProcessed.run(article.id);
        }
    }

    console.log(`✅ Analysis complete: ${processed}/${articles.length} articles processed.\n`);
    return processed;
}

module.exports = { processArticles, analyzeWithAI };
