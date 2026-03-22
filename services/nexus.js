/**
 * Nexus Intelligence Service
 * The core engine for Project Nexus.
 * Responsible for Automated Entity Extraction (AEE) and Relationship Mapping.
 */
const { v4: uuidv4 } = require('uuid');
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
 * Analyze an event and extract entity relationships
 * @param {Object} event The event record
 */
async function processEventNexus(event) {
    const db = getDb();
    const client = getGroq();

    if (!client) {
        console.warn('⚠️ Nexus: AI client not configured. Skipping advanced extraction.');
        return;
    }

    console.log(`🧠 Nexus: Analyzing connections for [${event.id}] "${event.title}"...`);

    try {
        const prompt = `
        You are NExUS (Network Extraction & Universal Synthesis), the core relational engine for a Palantir-level intelligence platform.
        Target: "${event.title}"
        Summary: ${event.summary}
        Category: ${event.category}
        Location: ${event.location_name}, ${event.country}

        TASK: Extract all key entities and their relationships. 
        Entities can be: PERSON, ORG (Company/Agency), GROUP (Rebel/Terrorist), GPE (Country/City), FACILITY, WEAPON_SYSTEM, or INFRASTRUCTURE.

        RELATIONSHIP TYPES:
        - CONTROLS / COMMANDS
        - ALLIED_WITH / SUPPORTED_BY
        - THREATENS / ATTACKED
        - SUBSIDIZES / FINANCES
        - LOCATED_IN
        - PARTICIPATED_IN (for Event links)
        - IMPACTS (for economic/social links)

        OUTPUT FORMAT (JSON ONLY):
        {
          "entities": [
            {"name": "Entity Name", "type": "TYPE", "description": "Brief intelligence summary", "influence": 1-10}
          ],
          "links": [
            {"source": "Entity A", "target": "Entity B", "type": "REL_TYPE", "strength": 1-5, "evidence": "Brief justification"}
          ]
        }

        Note: Use exactly "${event.id}" when linking an entity to this specific event.
        `;

        const completion = await client.chat.completions.create({
            model: 'llama-3.1-70b-versatile',
            messages: [{ role: 'user', content: prompt }],
            response_format: { type: 'json_object' },
            temperature: 0.1
        });

        const nexusData = JSON.parse(completion.choices[0].message.content);

        // Save entities and links
        db.transaction(() => {
            for (const ent of nexusData.entities || []) {
                const entityId = ent.name.toLowerCase().replace(/[^a-z0-9]/g, '_');
                db.prepare(`
                    INSERT INTO entities (id, name, type, description, influence_score, updated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(id) DO UPDATE SET 
                        description = COALESCE(entities.description, excluded.description),
                        influence_score = MAX(entities.influence_score, excluded.influence_score),
                        updated_at = datetime('now')
                `).run(entityId, ent.name, ent.type, ent.description, ent.influence || 1.0);

                // Update ent object with the generated ID for linking
                ent.internal_id = entityId;
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

        console.log(`✅ Nexus: Mapped ${nexusData.entities?.length || 0} entities and ${nexusData.links?.length || 0} links.`);

    } catch (err) {
        console.error('❌ Nexus Error:', err.message);
    }
}

module.exports = { processEventNexus };
