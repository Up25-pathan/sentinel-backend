-- Geopolitical Intelligence System — Database Schema

-- Raw articles ingested from news sources
CREATE TABLE IF NOT EXISTS raw_articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    url TEXT UNIQUE,
    source_name TEXT,
    image_url TEXT,
    published_at TEXT,
    ingested_at TEXT DEFAULT (datetime('now')),
    processed INTEGER DEFAULT 0
);

-- Processed geopolitical events
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    ai_brief TEXT,
    category TEXT CHECK(category IN (
        'WAR', 'MILITARY_MOVEMENT', 'SANCTIONS', 'COUP',
        'DIPLOMATIC_ESCALATION', 'NUCLEAR_THREAT', 'POLITICAL_INSTABILITY',
        'TERRORISM', 'CYBER_ATTACK', 'HUMANITARIAN', 'OTHER'
    )),
    risk_level TEXT CHECK(risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    location_name TEXT,
    country TEXT,
    lat REAL,
    lng REAL,
    image_url TEXT,
    images_json TEXT,
    is_breaking INTEGER DEFAULT 0,
    cluster_id TEXT,
    entities_json TEXT, -- JSON: countries, cities, leaders, organizations
    escalation_score INTEGER DEFAULT 0,
    second_order_effects TEXT,
    bias_analysis TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Sources linked to events
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT,
    credibility TEXT CHECK(credibility IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')) DEFAULT 'UNKNOWN',
    published_at TEXT,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- Alerts generated for breaking/critical events
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    type TEXT CHECK(type IN ('BREAKING', 'CRITICAL', 'UPDATE', 'ESCALATION')),
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
CREATE INDEX IF NOT EXISTS idx_events_risk ON events(risk_level);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_breaking ON events(is_breaking);
CREATE INDEX IF NOT EXISTS idx_events_location ON events(lat, lng);
CREATE INDEX IF NOT EXISTS idx_sources_event ON sources(event_id);
CREATE INDEX IF NOT EXISTS idx_alerts_event ON alerts(event_id);
CREATE INDEX IF NOT EXISTS idx_alerts_read ON alerts(is_read);
CREATE INDEX IF NOT EXISTS idx_raw_processed ON raw_articles(processed);

-- User-defined watchlists for custom intelligence alerts (Phase 6)
CREATE TABLE IF NOT EXISTS watchlists (
    id TEXT PRIMARY KEY,
    keyword TEXT NOT NULL UNIQUE,
    threshold INTEGER DEFAULT 3,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_triggered_at TEXT
);

-- Macro-Level AI Briefings (Phase 7)
CREATE TABLE IF NOT EXISTS global_briefings (
    id TEXT PRIMARY KEY,
    global_risk_score INTEGER DEFAULT 0,
    major_situations_json TEXT, -- JSON array of active conflicts/situations
    macro_predictions_json TEXT, -- JSON array of global predictions
    briefing_data TEXT, -- JSON blob for daily briefings
    created_at TEXT DEFAULT (datetime('now'))
);

-- Dark Web Intelligence (Phase 4)
CREATE TABLE IF NOT EXISTS dark_web_intel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT UNIQUE, -- dedup key per source
    source TEXT NOT NULL, -- abuse.ch, ransomware.live, OTX, Shodan
    category TEXT NOT NULL, -- MALWARE, BOTNET_C2, RANSOMWARE, THREAT_INTEL, EXPOSED_INFRA
    title TEXT NOT NULL,
    content TEXT,
    threat_level TEXT DEFAULT 'MEDIUM', -- LOW, MEDIUM, HIGH, CRITICAL
    url TEXT,
    tags TEXT, -- JSON array
    discovered_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dark_web_assessment (
    id INTEGER PRIMARY KEY,
    assessment TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ─── PROJECT NEXUS (Advanced Relational Intelligence) ──────────

-- Entities: Actors, Organizations, Facilities, etc.
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- PERSON, ORG, GPE, FACILITY, WEAPON_SYSTEM, etc.
    description TEXT,
    influence_score REAL DEFAULT 0.0,
    metadata_json TEXT, -- Alliances, social handles, technical specs
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Nexus Links: The connective tissue of the graph
CREATE TABLE IF NOT EXISTS nexus_links (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL, -- Entity or Event ID
    target_id TEXT NOT NULL, -- Entity or Event ID
    link_type TEXT NOT NULL, -- e.g., 'FUNDED_BY', 'ALLIED_WITH', 'PARTICIPATED_IN', 'THREATENS'
    strength REAL DEFAULT 1.0, -- Confidence/Strength score (1-5)
    evidence TEXT, -- Text snippet justifying the link
    source_ref TEXT, -- URL or document reference
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_nexus_source ON nexus_links(source_id);
CREATE INDEX IF NOT EXISTS idx_nexus_target ON nexus_links(target_id);
CREATE INDEX IF NOT EXISTS idx_nexus_type ON nexus_links(link_type);

-- ─── PREDICTIVE ENGINE (Second-Order Effects) ──────────

CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY,
    event_id TEXT,
    cluster_id TEXT,
    prediction_text TEXT NOT NULL,
    probability REAL DEFAULT 0.5, -- 0.0 to 1.0
    impact_level TEXT CHECK(impact_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    categories_affected TEXT, -- JSON array
    evidence_json TEXT, -- Supporting data points
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_predictions_event ON predictions(event_id);
CREATE INDEX IF NOT EXISTS idx_predictions_cluster ON predictions(cluster_id);

