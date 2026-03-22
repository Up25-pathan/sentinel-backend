/**
 * Seed Data — Realistic Geopolitical Events for UI Testing
 * Run with: npm run seed
 */
const { getDb } = require('./index');
const { v4: uuidv4 } = require('uuid');

const EVENTS = [
    {
        title: 'Major Military Escalation in Eastern Mediterranean',
        summary: 'Naval forces from multiple nations have converged in the Eastern Mediterranean following territorial disputes over exclusive economic zones. Tensions have risen sharply after a confrontation between patrol vessels near disputed waters.',
        ai_brief: '🔴 CRITICAL: Multi-national naval buildup in Eastern Mediterranean. Three carrier groups repositioned within 48 hours. Intelligence suggests this is the largest concentration of naval assets in the region since 2020. Risk of miscalculation is elevated.',
        category: 'MILITARY_MOVEMENT',
        risk_level: 'CRITICAL',
        location_name: 'Eastern Mediterranean Sea',
        country: 'International Waters',
        lat: 34.5,
        lng: 30.0,
        image_url: 'https://images.unsplash.com/photo-1580674285054-bed31e145f59?w=800',
        is_breaking: 1,
        entities_json: JSON.stringify({
            countries: ['Greece', 'Turkey', 'Egypt', 'France'],
            cities: ['Athens', 'Ankara', 'Cairo'],
            leaders: ['Greek PM', 'Turkish President'],
            organizations: ['NATO', 'EU Naval Force']
        }),
        sources: [
            { name: 'Reuters', url: 'https://reuters.com', credibility: 'HIGH' },
            { name: 'AP News', url: 'https://apnews.com', credibility: 'HIGH' },
            { name: 'Al Jazeera', url: 'https://aljazeera.com', credibility: 'MEDIUM' }
        ]
    },
    {
        title: 'New Comprehensive Sanctions Package Announced Against Russia',
        summary: 'Western allies have unveiled a new round of economic sanctions targeting key sectors of the Russian economy, including energy exports, financial institutions, and defense supply chains. The package includes secondary sanctions affecting third-party nations.',
        ai_brief: '⚠️ HIGH: New sanctions package targets 47 Russian entities across energy, finance, and defense sectors. Secondary sanctions provisions could impact trade routes through Central Asia. Market volatility expected in energy commodities.',
        category: 'SANCTIONS',
        risk_level: 'HIGH',
        location_name: 'Brussels, Belgium',
        country: 'Belgium',
        lat: 50.8503,
        lng: 4.3517,
        image_url: 'https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=800',
        is_breaking: 0,
        entities_json: JSON.stringify({
            countries: ['Russia', 'USA', 'UK', 'EU', 'Kazakhstan'],
            cities: ['Brussels', 'Washington DC', 'Moscow'],
            leaders: ['EU High Representative', 'US Secretary of State'],
            organizations: ['European Council', 'US Treasury', 'OFAC']
        }),
        sources: [
            { name: 'BBC World', url: 'https://bbc.com/news/world', credibility: 'HIGH' },
            { name: 'Financial Times', url: 'https://ft.com', credibility: 'HIGH' },
            { name: 'TASS', url: 'https://tass.com', credibility: 'LOW' }
        ]
    },
    {
        title: 'Military Coup Attempt Reported in West African Nation',
        summary: 'Reports of a military takeover are emerging from a West African country, with soldiers reportedly seizing government buildings and the state broadcaster. International flights have been suspended and communications are intermittent.',
        ai_brief: '🔴 CRITICAL: Military units have seized the presidential palace and state television. The president\'s location is unknown. AU and ECOWAS have called emergency sessions. Border closures reported. Situation is fluid with limited communications.',
        category: 'COUP',
        risk_level: 'CRITICAL',
        location_name: 'Niamey, Niger',
        country: 'Niger',
        lat: 13.5127,
        lng: 2.1128,
        image_url: 'https://images.unsplash.com/photo-1591696205602-2f950c417cb9?w=800',
        is_breaking: 1,
        entities_json: JSON.stringify({
            countries: ['Niger', 'France', 'Nigeria', 'Mali'],
            cities: ['Niamey'],
            leaders: ['Presidential Guard Commander'],
            organizations: ['ECOWAS', 'African Union', 'French Military']
        }),
        sources: [
            { name: 'France 24', url: 'https://france24.com', credibility: 'HIGH' },
            { name: 'Reuters', url: 'https://reuters.com', credibility: 'HIGH' },
            { name: 'Local journalists (X/Twitter)', url: 'https://twitter.com', credibility: 'MEDIUM' }
        ]
    },
    {
        title: 'Nuclear Talks Collapse Between Major Powers',
        summary: 'Negotiations aimed at renewing a key nuclear arms limitation treaty have broken down after delegates failed to agree on verification mechanisms and missile defense provisions. Both sides have announced they will resume independent testing.',
        ai_brief: '⚠️ HIGH: Nuclear arms talks have collapsed. Both parties cited irreconcilable positions on verification. Resumption of testing announced. This represents the most significant setback in nuclear diplomacy in a decade. Watch for UN Security Council emergency session.',
        category: 'NUCLEAR_THREAT',
        risk_level: 'HIGH',
        location_name: 'Geneva, Switzerland',
        country: 'Switzerland',
        lat: 46.2044,
        lng: 6.1432,
        image_url: 'https://images.unsplash.com/photo-1569163139394-de4e4f43e4e3?w=800',
        is_breaking: 0,
        entities_json: JSON.stringify({
            countries: ['USA', 'Russia', 'China'],
            cities: ['Geneva', 'Washington DC', 'Moscow', 'Beijing'],
            leaders: ['US Arms Negotiator', 'Russian Deputy FM'],
            organizations: ['UN', 'IAEA', 'State Department']
        }),
        sources: [
            { name: 'Associated Press', url: 'https://apnews.com', credibility: 'HIGH' },
            { name: 'Arms Control Association', url: 'https://armscontrol.org', credibility: 'HIGH' },
            { name: 'RT News', url: 'https://rt.com', credibility: 'LOW' }
        ]
    },
    {
        title: 'Diplomatic Crisis Between South Asian Nuclear States',
        summary: 'Relations between two nuclear-armed South Asian nations have deteriorated rapidly after a cross-border incident along the line of control. Both nations have recalled ambassadors and suspended bilateral trade agreements.',
        ai_brief: '🟡 MEDIUM-HIGH: Ambassador recall between nuclear-armed neighbors following LoC incident. Military alert levels elevated on both sides. International community calling for restraint. Trade suspension could affect regional food supply chains.',
        category: 'DIPLOMATIC_ESCALATION',
        risk_level: 'HIGH',
        location_name: 'Line of Control, Kashmir',
        country: 'India/Pakistan',
        lat: 34.0837,
        lng: 74.7973,
        image_url: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800',
        is_breaking: 0,
        entities_json: JSON.stringify({
            countries: ['India', 'Pakistan', 'China', 'USA'],
            cities: ['New Delhi', 'Islamabad', 'Srinagar'],
            leaders: ['Indian PM', 'Pakistani PM', 'Indian Army Chief'],
            organizations: ['UN Security Council', 'SAARC']
        }),
        sources: [
            { name: 'The Hindu', url: 'https://thehindu.com', credibility: 'HIGH' },
            { name: 'Dawn News', url: 'https://dawn.com', credibility: 'HIGH' },
            { name: 'BBC South Asia', url: 'https://bbc.com', credibility: 'HIGH' }
        ]
    },
    {
        title: 'Massive Cyber Attack Targets European Infrastructure',
        summary: 'A coordinated cyber attack has disrupted critical infrastructure across multiple European countries, affecting power grids, transportation networks, and government communication systems. Attribution points to a state-sponsored group.',
        ai_brief: '⚠️ HIGH: Coordinated cyber offensive targeting EU critical infrastructure. Power outages reported in 3 countries. State-sponsored attribution likely. NATO Article 5 cyber provisions being discussed. Expect retaliatory cyber operations within 72 hours.',
        category: 'CYBER_ATTACK',
        risk_level: 'HIGH',
        location_name: 'Multiple EU Countries',
        country: 'European Union',
        lat: 50.1109,
        lng: 8.6821,
        image_url: 'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800',
        is_breaking: 1,
        entities_json: JSON.stringify({
            countries: ['Germany', 'Poland', 'Baltic States', 'EU'],
            cities: ['Frankfurt', 'Warsaw', 'Tallinn', 'Brussels'],
            leaders: ['NATO Secretary General', 'EU Cyber Commissioner'],
            organizations: ['NATO', 'ENISA', 'NSA', 'GCHQ']
        }),
        sources: [
            { name: 'Reuters', url: 'https://reuters.com', credibility: 'HIGH' },
            { name: 'Wired', url: 'https://wired.com', credibility: 'HIGH' },
            { name: 'CrowdStrike Intelligence', url: 'https://crowdstrike.com', credibility: 'HIGH' }
        ]
    },
    {
        title: 'Humanitarian Crisis Deepens in Horn of Africa',
        summary: 'The ongoing conflict and drought in the Horn of Africa has created one of the worst humanitarian disasters in decades, with over 20 million people facing severe food insecurity and mass displacement across multiple countries.',
        ai_brief: '🟡 MEDIUM: Famine conditions declared in 3 regions. 20M+ affected across Ethiopia, Somalia, Sudan. UN aid corridors blocked by fighting. Refugee flows destabilizing neighboring countries. International donor conference scheduled.',
        category: 'HUMANITARIAN',
        risk_level: 'MEDIUM',
        location_name: 'Horn of Africa',
        country: 'Somalia/Ethiopia/Sudan',
        lat: 5.1521,
        lng: 46.1996,
        image_url: 'https://images.unsplash.com/photo-1488521787991-ed7bbaae773c?w=800',
        is_breaking: 0,
        entities_json: JSON.stringify({
            countries: ['Somalia', 'Ethiopia', 'Sudan', 'Kenya'],
            cities: ['Mogadishu', 'Addis Ababa', 'Khartoum'],
            leaders: ['UN Secretary General', 'WFP Director'],
            organizations: ['United Nations', 'WFP', 'UNHCR', 'Red Cross']
        }),
        sources: [
            { name: 'UNHCR', url: 'https://unhcr.org', credibility: 'HIGH' },
            { name: 'Al Jazeera', url: 'https://aljazeera.com', credibility: 'MEDIUM' },
            { name: 'The Guardian', url: 'https://theguardian.com', credibility: 'HIGH' }
        ]
    },
    {
        title: 'South China Sea Confrontation Escalates',
        summary: 'A tense standoff between coast guard and naval vessels in the South China Sea has intensified after a collision between ships from rival claimant nations. Both sides have deployed additional military assets to the contested area.',
        ai_brief: '🔴 CRITICAL: Ship collision in contested waters near Second Thomas Shoal. Both nations deploying reinforcements. US 7th Fleet repositioning CSG to Western Pacific. ASEAN emergency meeting called. High risk of armed confrontation.',
        category: 'WAR',
        risk_level: 'CRITICAL',
        location_name: 'South China Sea',
        country: 'Disputed Territory',
        lat: 10.5,
        lng: 115.0,
        image_url: 'https://images.unsplash.com/photo-1559827291-bce0b8a0f4a3?w=800',
        is_breaking: 1,
        entities_json: JSON.stringify({
            countries: ['China', 'Philippines', 'USA', 'Vietnam', 'Taiwan'],
            cities: ['Manila', 'Beijing', 'Hanoi'],
            leaders: ['Philippine President', 'Chinese Defense Minister'],
            organizations: ['PLA Navy', 'Philippine Navy', 'US 7th Fleet', 'ASEAN']
        }),
        sources: [
            { name: 'Reuters', url: 'https://reuters.com', credibility: 'HIGH' },
            { name: 'CSIS Asia Maritime', url: 'https://amti.csis.org', credibility: 'HIGH' },
            { name: 'South China Morning Post', url: 'https://scmp.com', credibility: 'MEDIUM' }
        ]
    },
    {
        title: 'Political Instability Grips Central American Nation',
        summary: 'Widespread protests have erupted following disputed election results, with opposition leaders calling for a general strike. Security forces have been deployed to major cities amid reports of clashes and arbitrary arrests.',
        ai_brief: '🟡 MEDIUM: Post-election unrest spreading to major cities. Opposition claims fraud; OAS monitors note irregularities. Military positioning ambiguous. US State Department issued Level 4 travel advisory. Migration surge expected at southern border.',
        category: 'POLITICAL_INSTABILITY',
        risk_level: 'MEDIUM',
        location_name: 'Guatemala City, Guatemala',
        country: 'Guatemala',
        lat: 14.6349,
        lng: -90.5069,
        image_url: 'https://images.unsplash.com/photo-1591901206069-ed60c4429a2e?w=800',
        is_breaking: 0,
        entities_json: JSON.stringify({
            countries: ['Guatemala', 'USA', 'Mexico', 'Honduras'],
            cities: ['Guatemala City', 'Washington DC'],
            leaders: ['Guatemalan President', 'Opposition Leader'],
            organizations: ['OAS', 'US State Department', 'Central American Parliament']
        }),
        sources: [
            { name: 'Associated Press', url: 'https://apnews.com', credibility: 'HIGH' },
            { name: 'BBC Mundo', url: 'https://bbc.com/mundo', credibility: 'HIGH' },
            { name: 'Local Media Network', url: 'https://prensalibre.com', credibility: 'MEDIUM' }
        ]
    },
    {
        title: 'Terrorist Attack on Energy Infrastructure in Middle East',
        summary: 'A sophisticated attack on oil processing facilities has disrupted energy supplies, causing a sudden spike in global oil prices. Multiple armed drones and missiles were used in the coordinated assault on two major facilities.',
        ai_brief: '🔴 CRITICAL: Coordinated drone/missile attack on 2 oil facilities. Production reduced by 5.7M barrels/day (~5% global supply). Brent crude surged 14%. State-sponsored proxy group claimed responsibility. Expect military retaliation within 48-72 hours.',
        category: 'TERRORISM',
        risk_level: 'CRITICAL',
        location_name: 'Persian Gulf Region',
        country: 'Saudi Arabia',
        lat: 25.3548,
        lng: 49.9555,
        image_url: 'https://images.unsplash.com/photo-1513828583688-c52646db42da?w=800',
        is_breaking: 1,
        entities_json: JSON.stringify({
            countries: ['Saudi Arabia', 'Iran', 'USA', 'Yemen'],
            cities: ['Riyadh', 'Tehran', 'Sanaa'],
            leaders: ['Saudi Crown Prince', 'Iranian Supreme Leader'],
            organizations: ['Aramco', 'OPEC', 'US CENTCOM', 'Houthi Forces']
        }),
        sources: [
            { name: 'Reuters', url: 'https://reuters.com', credibility: 'HIGH' },
            { name: 'AP News', url: 'https://apnews.com', credibility: 'HIGH' },
            { name: 'CNBC Energy', url: 'https://cnbc.com', credibility: 'HIGH' },
            { name: 'Al Arabiya', url: 'https://alarabiya.net', credibility: 'MEDIUM' }
        ]
    }
];

const DARK_WEB_INTEL = [
    {
        source_id: 'abusech-101',
        source: 'abuse.ch',
        category: 'MALWARE',
        title: 'Lumina Stealer C2 Active',
        content: 'New Lumina Stealer C2 server detected at 104.21.75.12. Targeting European financial institutions with high-frequency credential harvesting observed in the last 6 hours.',
        threat_level: 'HIGH',
        url: 'https://urlhaus.abuse.ch/browse/',
        tags: JSON.stringify(['lumina', 'stealer', 'finance'])
    },
    {
        source_id: 'ransom-lockbit-1',
        source: 'ransomware.live',
        category: 'RANSOMWARE',
        title: '[LockBit 3.0] Global Logistics Corp Victim Posted',
        content: 'LockBit 3.0 has claimed responsibility for a breach at Global Logistics Corp. Estimated 4TB of data exfiltrated including client manifests and financial records. Deadline for payment: 48 hours.',
        threat_level: 'CRITICAL',
        url: 'http://lockbitapt2...onion/',
        tags: JSON.stringify(['lockbit', 'logistics', 'extortion'])
    },
    {
        source_id: 'shodan-ics-1',
        source: 'Shodan',
        category: 'EXPOSED_INFRA',
        title: 'Exposed Siemens S7-1500 PLC in Industrial Zone',
        content: 'Siemens S7 series PLC exposed on port 102. Located in Shenzhen Industrial District. No authentication required for program state access. Risk of industrial sabotage is high.',
        threat_level: 'CRITICAL',
        tags: JSON.stringify(['ics', 'scada', 'vuln'])
    },
    {
        source_id: 'otx-pulse-1',
        source: 'AlienVault OTX',
        category: 'THREAT_INTEL',
        title: 'Oil & Gas Sector Targetting by APT41',
        content: 'Ongoing campaign against Middle Eastern energy firms. Using spear-phishing with malicious PDFs. Indicators include 15 new domain registrations mimicking regional regulators.',
        threat_level: 'HIGH',
        url: 'https://otx.alienvault.com/pulse/apt41-energy',
        tags: JSON.stringify(['apt41', 'energy', 'phishing'])
    }
];

const DARK_WEB_ASSESSMENT = "Relentless targeting of European financial hubs and Asian industrial infrastructure dominates the current landscape. LockBit 3.0 activity has surged by 15% this week, while exposed SCADA systems in manufacturing zones remain a critical vector for state-sponsored disruption.";

function seed() {
    const db = getDb();

    // Clear existing data
    db.exec('DELETE FROM alerts');
    db.exec('DELETE FROM sources');
    db.exec('DELETE FROM events');
    db.exec('DELETE FROM dark_web_intel');
    db.exec('DELETE FROM dark_web_assessment');
    db.exec('DELETE FROM entities');
    db.exec('DELETE FROM nexus_links');

    const insertEvent = db.prepare(`
        INSERT INTO events (id, title, summary, ai_brief, category, risk_level, 
            location_name, country, lat, lng, image_url, is_breaking, cluster_id, 
            entities_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const insertSource = db.prepare(`
        INSERT INTO sources (id, event_id, name, url, credibility, published_at)
        VALUES (?, ?, ?, ?, ?, ?)
    `);

    const insertAlert = db.prepare(`
        INSERT INTO alerts (id, event_id, type, message, is_read, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    `);

    const insertDarkWeb = db.prepare(`
        INSERT INTO dark_web_intel (source_id, source, category, title, content, threat_level, url, tags, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    `);

    const now = new Date();

    const transaction = db.transaction(() => {
        // Events
        EVENTS.forEach((event, index) => {
            const eventId = uuidv4();
            const eventTime = new Date(now.getTime() - (index * 4 * 60 * 60 * 1000));
            const timeStr = eventTime.toISOString().replace('T', ' ').replace('Z', '');

            insertEvent.run(
                eventId,
                event.title,
                event.summary,
                event.ai_brief,
                event.category,
                event.risk_level,
                event.location_name,
                event.country,
                event.lat,
                event.lng,
                event.image_url,
                event.is_breaking,
                null,
                event.entities_json,
                timeStr,
                timeStr
            );

            event.sources.forEach(source => {
                insertSource.run(
                    uuidv4(),
                    eventId,
                    source.name,
                    source.url,
                    source.credibility,
                    timeStr
                );
            });

            if (event.is_breaking || event.risk_level === 'CRITICAL') {
                const alertType = event.is_breaking ? 'BREAKING' : 'CRITICAL';
                const alertMessage = event.is_breaking
                    ? `🔴 BREAKING: ${event.title}`
                    : `⚠️ ${event.risk_level}: ${event.title}`;

                insertAlert.run(
                    uuidv4(),
                    eventId,
                    alertType,
                    alertMessage,
                    0,
                    timeStr
                );
            }
        });

        // Dark Web
        DARK_WEB_INTEL.forEach(item => {
            insertDarkWeb.run(
                item.source_id,
                item.source,
                item.category,
                item.title,
                item.content,
                item.threat_level,
                item.url || '',
                item.tags,
            );
        });

        // Assessment
        db.prepare('INSERT INTO dark_web_assessment (assessment) VALUES (?)').run(DARK_WEB_ASSESSMENT);

        // --- Nexus Relational Seeds ---
        // Insert some entities for the graph
        const entities = [
            { id: uuidv4(), name: 'LockBit 3.0', type: 'ORGANIZATION', metadata: JSON.stringify({ sector: 'Ransomware' }) },
            { id: uuidv4(), name: 'APT41', type: 'ACTOR', metadata: JSON.stringify({ origin: 'CN' }) },
            { id: uuidv4(), name: 'Siemens S7', type: 'ASSET', metadata: JSON.stringify({ class: 'PLC' }) },
            { id: uuidv4(), name: 'Russian Navy', type: 'ORGANIZATION', metadata: JSON.stringify({ class: 'Military' }) }
        ];

        const insertEntity = db.prepare('INSERT INTO entities (id, name, type, metadata) VALUES (?, ?, ?, ?)');
        entities.forEach(e => insertEntity.run(e.id, e.name, e.type, e.metadata));
    });

    transaction();

    const eventCount = db.prepare('SELECT COUNT(*) as count FROM events').get();
    const dwCount = db.prepare('SELECT COUNT(*) as count FROM dark_web_intel').get();

    console.log(`\n🌍 Seed data loaded successfully:`);
    console.log(`   📰 ${eventCount.count} geopolitical events`);
    console.log(`   🕸️ ${dwCount.count} dark web items\n`);
}

if (require.main === module) {
    seed();
    const { closeDb } = require('./index');
    closeDb();
}

module.exports = seed;
