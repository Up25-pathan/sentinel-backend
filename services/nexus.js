/**
 * Nexus Intelligence Service (v2 — Local + Optional AI)
 * Uses local NLP for entity extraction (always works, zero API calls)
 * Optionally enhances with AI for deep relationship analysis
 */
const { v4: uuidv4 } = require('uuid');
const Groq = require('groq-sdk');
const { getDb } = require('../db');
const { extractNexusEntities } = require('./local-nlp');
require('dotenv').config();

let groq = null;

function getGroq() {
    if (!groq && process.env.GROQ_API_KEY) {
        groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
    }
    return groq;
}

/**
 * Process event Nexus using LOCAL NLP (instant, free)
 * Always runs — populates entities and nexus_links from text patterns
 */
function processEventNexusLocal(event) {
    const db = getDb();

    try {
        const nexusData = extractNexusEntities(event);

        if (nexusData.entities.length === 0) {
            return; // Nothing to extract
        }

        db.transaction(() => {
            for (const ent of nexusData.entities) {
                const entityId = ent.name.toLowerCase().replace(/[^a-z0-9]/g, '_');
                db.prepare(`
                    INSERT INTO entities (id, name, type, description, influence_score, updated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(id) DO UPDATE SET 
                        description = COALESCE(excluded.description, entities.description),
                        influence_score = MAX(entities.influence_score, excluded.influence_score),
                        updated_at = datetime('now')
                `).run(entityId, ent.name, ent.type, ent.description, ent.influence || 1.0);
            }

            for (const link of nexusData.links) {
                const sourceId = link.source === event.id
                    ? event.id
                    : link.source.toLowerCase().replace(/[^a-z0-9]/g, '_');
                const targetId = link.target === event.id
                    ? event.id
                    : link.target.toLowerCase().replace(/[^a-z0-9]/g, '_');

                db.prepare(`
                    INSERT INTO nexus_links (id, source_id, target_id, link_type, strength, evidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT DO NOTHING
                `).run(uuidv4(), sourceId, targetId, link.type, link.strength, link.evidence);
            }
        })();

        console.log(`  🔗 Nexus[LOCAL]: Mapped ${nexusData.entities.length} entities, ${nexusData.links.length} links for [${event.id.substring(0, 8)}]`);
    } catch (err) {
        console.error('  ⚠️ Nexus[LOCAL] Error:', err.message);
    }
}

/**
 * AI-enhanced Nexus analysis (optional, budget-dependent)
 * Only called for high-priority events when AI budget allows
 */
async function processEventNexusAI(event) {
    const db = getDb();
    const client = getGroq();

    if (!client) return;

    try {
        const prompt = `
        You are NExUS, a relational intelligence engine.
        Target: "${event.title}"
        Summary: ${event.summary}
        Category: ${event.category}
        Location: ${event.location_name}, ${event.country}

        Extract key entities and relationships. 
        Entity types: PERSON, ORG, GROUP, GPE, FACILITY, WEAPON_SYSTEM, INFRASTRUCTURE.
        Relationship types: CONTROLS, ALLIED_WITH, THREATENS, FINANCES, LOCATED_IN, PARTICIPATED_IN, IMPACTS.

        JSON only:
        {
          "entities": [{"name": "Name", "type": "TYPE", "description": "Brief", "influence": 1-10}],
          "links": [{"source": "A", "target": "B", "type": "REL", "strength": 1-5, "evidence": "Brief"}]
        }
        Use "${event.id}" when linking to this event.
        `;

        const completion = await client.chat.completions.create({
            model: 'llama-3.1-8b-instant',
            messages: [{ role: 'user', content: prompt }],
            response_format: { type: 'json_object' },
            temperature: 0.1
        });

        const nexusData = JSON.parse(completion.choices[0].message.content);

        db.transaction(() => {
            for (const ent of nexusData.entities || []) {
                const entityId = ent.name.toLowerCase().replace(/[^a-z0-9]/g, '_');
                db.prepare(`
                    INSERT INTO entities (id, name, type, description, influence_score, updated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(id) DO UPDATE SET 
                        description = COALESCE(excluded.description, entities.description),
                        influence_score = MAX(entities.influence_score, excluded.influence_score),
                        updated_at = datetime('now')
                `).run(entityId, ent.name, ent.type, ent.description, ent.influence || 1.0);
            }

            for (const link of nexusData.links || []) {
                const sourceId = link.source === event.id ? event.id : link.source.toLowerCase().replace(/[^a-z0-9]/g, '_');
                const targetId = link.target === event.id ? event.id : link.target.toLowerCase().replace(/[^a-z0-9]/g, '_');

                db.prepare(`
                    INSERT INTO nexus_links (id, source_id, target_id, link_type, strength, evidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT DO NOTHING
                `).run(uuidv4(), sourceId, targetId, link.type, link.strength, link.evidence);
            }
        })();

        console.log(`  🧠 Nexus[AI]: Mapped ${nexusData.entities?.length || 0} entities, ${nexusData.links?.length || 0} links.`);
    } catch (err) {
        console.error('  ⚠️ Nexus[AI] Error:', err.message);
    }
}

module.exports = { processEventNexusLocal, processEventNexusAI };
