-- HYDRO MIND Database Schema
-- Uses SQLite

-- ─── CORE ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    type TEXT NOT NULL, -- e.g., 'RESERVOIR', 'RIVER'
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

-- Unified observations table for hydrology, weather, water quality
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    parameter TEXT NOT NULL, -- e.g., 'level', 'storage', 'inflow', 'ph', 'temperature_2m'
    value REAL,              -- NULL if UNAVAILABLE
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url_or_citation TEXT,
    timestamp_utc DATETIME NOT NULL,
    timestamp_ist DATETIME NOT NULL,
    status TEXT NOT NULL,    -- 'LIVE', 'HISTORICAL', 'UNAVAILABLE', etc.
    status_reason TEXT,      -- Reason if UNAVAILABLE
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

CREATE INDEX IF NOT EXISTS idx_obs_station_time ON observations(station_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_obs_param ON observations(parameter);

-- Pre-calculated Water Quality Index records
CREATE TABLE IF NOT EXISTS water_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    wqi_score REAL,
    category TEXT,
    pollution_risk TEXT,
    source TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

-- ML Forecasts
CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    target_parameter TEXT NOT NULL,
    forecast_timestamp_utc DATETIME NOT NULL,
    predicted_value REAL NOT NULL,
    confidence_interval_lower REAL,
    confidence_interval_upper REAL,
    model_version TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

-- Risk Engine Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hazard_category TEXT NOT NULL, -- 'WATER STRESS', 'FLOOD / SURPLUS', 'WATER QUALITY', 'RUNOFF / POLLUTION'
    severity TEXT NOT NULL,        -- 'NORMAL', 'WATCH', 'ELEVATED', 'HIGH', 'CRITICAL'
    message TEXT NOT NULL,
    evidence TEXT,                 -- JSON array of signals
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);

-- Satellite observations (Google Earth Engine)
CREATE TABLE IF NOT EXISTS satellite_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    observation_date_utc DATETIME NOT NULL,
    ndwi REAL,
    mndwi REAL,
    ndci REAL,
    turbidity_proxy REAL,
    cloud_cover_pct REAL,
    source TEXT DEFAULT 'COPERNICUS/S2_SR_HARMONIZED',
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (station_id) REFERENCES stations(id)
);


-- ─── GOOGLE NEWS INTELLIGENCE LAYER ────────────────────────────────

CREATE TABLE IF NOT EXISTS news_sources (
    domain TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    classification TEXT NOT NULL, -- 'OFFICIAL', 'SECONDARY'
    verified_at DATETIME
);

CREATE TABLE IF NOT EXISTS news_fetch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    run_timestamp_utc DATETIME NOT NULL,
    items_fetched INTEGER DEFAULT 0,
    status TEXT NOT NULL, -- 'SUCCESS', 'ERROR'
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS news_items (
    id TEXT PRIMARY KEY, -- Hash of URL or unique ID
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT NOT NULL,
    publisher TEXT NOT NULL,
    source_domain TEXT NOT NULL,
    published_at_utc DATETIME NOT NULL,
    fetched_at_utc DATETIME NOT NULL,
    category TEXT, -- Event Category
    source_type TEXT NOT NULL, -- 'OFFICIAL', 'SECONDARY', 'DISCOVERY_ONLY'
    status TEXT NOT NULL,
    relevance_score INTEGER DEFAULT 0,
    confidence INTEGER DEFAULT 0,
    content_hash TEXT,
    original_source_url TEXT,
    google_news_url TEXT,
    verification_status TEXT, -- 'UNCORROBORATED', 'PARTIALLY_CORROBORATED', 'CORROBORATED', 'CONTRADICTED', 'INSUFFICIENT_DATA'
    verification_reason TEXT,
    first_seen_at_utc DATETIME NOT NULL,
    last_seen_at_utc DATETIME NOT NULL,
    is_new BOOLEAN DEFAULT 1,
    is_duplicate BOOLEAN DEFAULT 0,
    is_relevant BOOLEAN DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at_utc);
CREATE INDEX IF NOT EXISTS idx_news_source ON news_items(source_domain);

CREATE TABLE IF NOT EXISTS news_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    corroboration_status TEXT NOT NULL,
    severity TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
