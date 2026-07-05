/**
 * AI Chat Service
 * Natural language Q&A over the intelligence database.
 * Uses Groq (Llama 3.1) with event context for grounded answers.
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
 * Process a natural language question against the intelligence database
 */
async function chat(question) {
    const db = getDb();

    // 1. Search for relevant events using keywords from the question
    const keywords = extractKeywords(question);
    let events = [];

    if (keywords.length > 0) {
        const whereClauses = keywords.map(k => `(title LIKE ? OR summary LIKE ? OR location_name LIKE ?)`);
        const params = keywords.flatMap(k => [`%${k}%`, `%${k}%`, `%${k}%`]);

        events = db.prepare(`
            SELECT id, title, summary, category, risk_level, location_name, 
                   latitude, longitude, is_breaking, created_at, ai_brief,
                   escalation_score, second_order_effects, bias_analysis
            FROM events 
            WHERE ${whereClauses.join(' OR ')}
            ORDER BY created_at DESC
            LIMIT 15
        `).all(...params);
    }

    // If no keyword matches, get the most recent events
    if (events.length === 0) {
        events = db.prepare(`
            SELECT id, title, summary, category, risk_level, location_name,
                   is_breaking, created_at, ai_brief, escalation_score
            FROM events 
            ORDER BY created_at DESC
            LIMIT 10
        `).all();
    }

    // 2. Fetch global stats for context
    const stats = db.prepare(`
        SELECT 
            COUNT(*) as total_events,
            SUM(CASE WHEN risk_level = 'CRITICAL' THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) as high_count,
            SUM(CASE WHEN is_breaking = 1 THEN 1 ELSE 0 END) as breaking_count
        FROM events
        WHERE created_at > datetime('now', '-7 days')
    `).get();

    // 3. Build context for the AI
    const eventContext = events.map(e =>
        `[${e.category}] [${e.risk_level}] ${e.title}` +
        (e.location_name ? ` | Location: ${e.location_name}` : '') +
        (e.summary ? ` | ${e.summary}` : '') +
        (e.escalation_score ? ` | Escalation: ${e.escalation_score}%` : '') +
        ` | Date: ${e.created_at}`
    ).join('\n');

    const systemPrompt = `You are SENTINEL, an AI geopolitical intelligence analyst. You have access to a real-time database of global events.

Current Intelligence Database (last 7 days):
- Total Events: ${stats.total_events}
- Critical Events: ${stats.critical_count}
- High Risk Events: ${stats.high_count}
- Active Breaking Events: ${stats.breaking_count}

Relevant Events Context:
${eventContext}

Instructions:
- Answer questions based on the intelligence data provided above.
- Be concise, analytical, and use intelligence terminology.
- When discussing events, cite specific details from the data.
- If asked about something not in the database, say so clearly.
- Format responses with clear sections and bullet points when appropriate.
- Always note the risk levels and escalation potential.
- Do NOT make up events or data not in the context above.`;

    // 4. Call Groq AI
    const client = getGroq();
    if (!client) {
        return generateFallbackResponse(question, events, stats);
    }

    try {
        const completion = await client.chat.completions.create({
            model: 'llama-3.1-8b-instant',
            messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: question }
            ],
            temperature: 0.3,
            max_tokens: 800,
        });

        const answer = completion.choices[0]?.message?.content || 'No response generated.';

        return {
            answer,
            eventsReferenced: events.length,
            model: 'llama-3.1-8b',
            timestamp: new Date().toISOString()
        };
    } catch (err) {
        console.error('AI Chat error:', err.message);
        return generateFallbackResponse(question, events, stats);
    }
}

/**
 * Extract meaningful keywords from a question
 */
function extractKeywords(question) {
    const stopWords = new Set([
        'what', 'is', 'the', 'a', 'an', 'are', 'was', 'were', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'about',
        'tell', 'me', 'happening', 'going', 'there', 'any', 'how', 'many',
        'much', 'latest', 'recent', 'current', 'now', 'today', 'update',
        'news', 'events', 'situation', 'status', 'whats', "what's"
    ]);

    return question
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '')
        .split(/\s+/)
        .filter(w => w.length > 2 && !stopWords.has(w));
}

/**
 * Fallback response when AI is not available
 */
function generateFallbackResponse(question, events, stats) {
    const lines = [`📊 Intelligence Summary (based on ${events.length} relevant events):\n`];

    if (events.length === 0) {
        lines.push('No matching events found in the database for your query.');
    } else {
        lines.push(`Found ${events.length} relevant events:\n`);
        events.slice(0, 5).forEach(e => {
            lines.push(`• [${e.risk_level}] ${e.title}`);
            if (e.location_name) lines.push(`  📍 ${e.location_name}`);
        });
    }

    lines.push(`\n📈 Weekly Stats: ${stats.total_events} total | ${stats.critical_count} critical | ${stats.high_count} high risk`);

    return {
        answer: lines.join('\n'),
        eventsReferenced: events.length,
        model: 'fallback',
        timestamp: new Date().toISOString()
    };
}

module.exports = { chat };
