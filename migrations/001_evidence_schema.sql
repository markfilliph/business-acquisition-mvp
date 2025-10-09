-- Migration 001: Evidence-Based Lead Generation Schema
-- Created: 2025-01-08
-- Purpose: Implement evidence ledger, fingerprinting, and validation tracking

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS exports;
DROP TABLE IF EXISTS exclusions;
DROP TABLE IF EXISTS validations;
DROP TABLE IF EXISTS observations;
DROP TABLE IF EXISTS validation_versions;
DROP TABLE IF EXISTS businesses;

-- Core business record (canonical)
CREATE TABLE businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    normalized_name TEXT NOT NULL,
    original_name TEXT,
    street TEXT,
    city TEXT,
    postal_code TEXT,
    province TEXT DEFAULT 'ON',
    phone TEXT,
    website TEXT,
    latitude REAL,
    longitude REAL,
    distance_km REAL,
    status TEXT DEFAULT 'DISCOVERED',
    manual_override BOOLEAN DEFAULT FALSE,
    override_reason TEXT,
    override_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('DISCOVERED', 'GEOCODED', 'ENRICHED', 'VALIDATED', 'QUALIFIED', 'EXCLUDED', 'REVIEW_REQUIRED', 'EXPORTED'))
);

CREATE INDEX idx_businesses_status ON businesses(status);
CREATE INDEX idx_businesses_fingerprint ON businesses(fingerprint);
CREATE INDEX idx_businesses_city ON businesses(city);

-- Evidence ledger (one row per source check)
CREATE TABLE observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT,
    confidence REAL DEFAULT 1.0,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    http_status INTEGER,
    api_version TEXT,
    error TEXT,
    FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    CHECK (confidence BETWEEN 0.0 AND 1.0)
);

CREATE INDEX idx_observations_business_field ON observations(business_id, field);
CREATE INDEX idx_observations_source ON observations(source_url);

-- Validation gates results
CREATE TABLE validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    reason TEXT,
    evidence_ids TEXT,
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE INDEX idx_validations_business ON validations(business_id);
CREATE INDEX idx_validations_rule ON validations(rule_id);

-- Exclusion reasons (audit trail)
CREATE TABLE exclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_ids TEXT,
    excluded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE INDEX idx_exclusions_business ON exclusions(business_id);
CREATE INDEX idx_exclusions_rule ON exclusions(rule_id);

-- Export snapshots
CREATE TABLE exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    validation_version INTEGER NOT NULL,
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    export_file TEXT,
    FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE INDEX idx_exports_business ON exports(business_id);
CREATE INDEX idx_exports_version ON exports(validation_version);

-- Validation version tracking
CREATE TABLE validation_versions (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    config_snapshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial version
INSERT INTO validation_versions (version, description, config_snapshot)
VALUES (1, 'Initial evidence-based validation system', '{"min_corroboration_sources": 2, "min_website_age_years": 3, "min_revenue_confidence": 0.6}');
