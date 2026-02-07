-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ============================================================
-- CORE TABLES
-- ============================================================

-- ------------------------------------------------------------
-- Location
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS locations (
    location_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    venue_name TEXT,
    street_address TEXT,
    city TEXT,
    state_or_region TEXT,
    postal_code TEXT,
    country_code CHAR(2) REFERENCES country_codes(country_code),

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    timezone TEXT 
);


-- ------------------------------------------------------------
-- Organizer
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS organizers (
    organizer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    name TEXT NOT NULL UNIQUE,
    url TEXT,
    email TEXT,
    phone TEXT,
    image_url TEXT,
    follower_count INT,
    verified BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);


-- ------------------------------------------------------------
-- Source
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
    source_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    source_name TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    source_url TEXT,

    last_updated_from_source TIMESTAMP,
    ingestion_timestamp TIMESTAMP DEFAULT NOW(),

    UNIQUE (source_name, source_event_id)
);


-- ============================================================
-- TAXONOMY
-- ============================================================

-- ------------------------------------------------------------
-- Primary Category
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS primary_categories (
    primary_category_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    taxonomy_version TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);


-- ------------------------------------------------------------
-- Subcategory
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subcategories (
    subcategory_id TEXT PRIMARY KEY,
    primary_category_id TEXT
        REFERENCES primary_categories(primary_category_id)
        ON DELETE CASCADE,

    name TEXT NOT NULL UNIQUE
);


-- ============================================================
-- EVENT (Central Spine)
-- ============================================================

CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    title TEXT NOT NULL,
    description TEXT,

    primary_category_id TEXT
        REFERENCES primary_categories(primary_category_id),

    event_type TEXT,
    event_format TEXT,
    capacity INT,
    age_restriction TEXT,

    start_datetime TIMESTAMP,
    end_datetime TIMESTAMP,
    duration_minutes INT,
    is_all_day BOOLEAN DEFAULT FALSE,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_pattern TEXT,

    location_id UUID
        REFERENCES locations(location_id),

    organizer_id UUID
        REFERENCES organizers(organizer_id),

    source_id UUID
        REFERENCES sources(source_id),

    data_quality_score FLOAT,

    raw_html TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================
-- SNAPSHOTS
-- ============================================================

-- ------------------------------------------------------------
-- Price Snapshot
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_snapshots (
    price_snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    event_id UUID
        REFERENCES events(event_id)
        ON DELETE CASCADE,

    currency CHAR(3) REFERENCES currency_codes(currency_code),
    is_free BOOLEAN,

    minimum_price FLOAT,
    maximum_price FLOAT,
    early_bird_price FLOAT,
    standard_price FLOAT,
    vip_price FLOAT,

    price_raw_text TEXT,

    valid_from_timestamp TIMESTAMP,
    ingested_at TIMESTAMP DEFAULT NOW()
);


-- ------------------------------------------------------------
-- Engagement Snapshot
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS engagement_snapshots (
    engagement_snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    event_id UUID
        REFERENCES events(event_id)
        ON DELETE CASCADE,

    going_count INT,
    interested_count INT,
    views_count INT,
    shares_count INT,
    comments_count INT,
    likes_count INT,

    captured_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================
-- TICKETING
-- ============================================================

CREATE TABLE IF NOT EXISTS ticket_info (
    ticket_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    event_id UUID
        REFERENCES events(event_id)
        ON DELETE CASCADE,

    url TEXT,
    is_sold_out BOOLEAN DEFAULT FALSE,
    ticket_count_available INT,
    early_bird_deadline TIMESTAMP,

    last_updated TIMESTAMP DEFAULT NOW()
);


-- ============================================================
-- MEDIA
-- ============================================================

CREATE TABLE IF NOT EXISTS media_assets (
    media_asset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    event_id UUID
        REFERENCES events(event_id)
        ON DELETE CASCADE,

    type TEXT, -- e.g., image, video, etc.
    url TEXT,
    title TEXT,
    description TEXT,
    width INT,
    height INT
);


-- ============================================================
-- TAXONOMY MAPPING
-- ============================================================

CREATE TABLE IF NOT EXISTS event_taxonomy_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    event_id UUID NOT NULL,
        -- REFERENCES events(event_id)
        -- ON DELETE CASCADE,

    subcategory_id TEXT
        REFERENCES subcategories(subcategory_id)
        ON DELETE CASCADE,

    activity_id UUID,
    activity_name TEXT,

    energy_level TEXT, 
    social_intensity TEXT,
    cognitive_load TEXT,
    physical_involvement TEXT,
    cost_level TEXT,
    time_scale TEXT,
    environment TEXT,
    risk_level TEXT,
    age_accessibility TEXT,
    repeatability TEXT
);


-- ============================================================
-- ACTIVITIES METADATA
-- Stores atomic activities from taxonomy ontology
-- ============================================================

CREATE TABLE IF NOT EXISTS activities_metadata (
    activity_id UUID PRIMARY KEY,

    primary_category_id TEXT
    REFERENCES primary_categories(primary_category_id)
    ON DELETE CASCADE,

    subcategory_id TEXT
    REFERENCES subcategories(subcategory_id)
    ON DELETE CASCADE,

    name TEXT NOT NULL,

    energy_level TEXT,
    social_intensity TEXT,
    cognitive_load TEXT,
    physical_involvement TEXT,
    cost_level TEXT,
    time_scale TEXT,
    environment TEXT,

    risk_level TEXT,
    age_accessibility TEXT,
    repeatability TEXT,

    notes TEXT
);


-- ============================================================
-- SUBCATEGORY VALUES
-- Philosophical / experiential values
-- ============================================================

CREATE TABLE IF NOT EXISTS subcategory_values (
    value_id UUID PRIMARY KEY,
    subcategory_id TEXT
    REFERENCES subcategories(subcategory_id)
    ON DELETE CASCADE,

    value_name TEXT NOT NULL UNIQUE
);


-- ============================================================
-- ACTIVITY EMOTIONAL OUTPUTS metadata
-- Psychological outputs of activities
-- ============================================================

CREATE TABLE IF NOT EXISTS activity_emotional_outputs (
    emotional_output_id UUID PRIMARY KEY,

    activity_id UUID
    REFERENCES activities_metadata(activity_id)
    ON DELETE CASCADE,

    emotion_name TEXT NOT NULL
);

-- ============================================================
-- Table to map events to their mapped emotional outputs
-- ============================================================
CREATE TABLE IF NOT EXISTS event_emotional_outputs (
    mapping_id UUID NOT NULL,
    emotional_output_id UUID NOT NULL,

    CONSTRAINT fk_event_emotion_mapping
        FOREIGN KEY (mapping_id)
        REFERENCES event_taxonomy_mappings (mapping_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_event_emotion_value
        FOREIGN KEY (emotional_output_id)
        REFERENCES activity_emotional_outputs (emotional_output_id)
        ON DELETE CASCADE,

    CONSTRAINT pk_event_emotion
        PRIMARY KEY (mapping_id, emotional_output_id)
);


-- ============================================================
-- Event Tags
-- ============================================================

CREATE TABLE IF NOT EXISTS event_tags (
    event_id UUID NOT NULL,
    tag TEXT NOT NULL,

    CONSTRAINT fk_event_tag_event
        FOREIGN KEY (event_id)
        REFERENCES events (event_id)
        ON DELETE CASCADE,

    CONSTRAINT pk_event_tag
        PRIMARY KEY (event_id, tag)
);


-- ============================================================
-- Artists
-- ============================================================

CREATE TABLE IF NOT EXISTS artists (
    artist_id SERIAL PRIMARY KEY,

    name TEXT NOT NULL,
    soundcloud_url TEXT,
    spotify_url TEXT,
    instagram_url TEXT,
    genre TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- Event ↔ Artist Mapping
-- ============================================================

CREATE TABLE IF NOT EXISTS event_artists (
    event_id UUID NOT NULL,
    artist_id INT NOT NULL,

    CONSTRAINT fk_event_artist_event
        FOREIGN KEY (event_id)
        REFERENCES events (event_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_event_artist_artist
        FOREIGN KEY (artist_id)
        REFERENCES artists (artist_id)
        ON DELETE CASCADE,

    CONSTRAINT pk_event_artist
        PRIMARY KEY (event_id, artist_id)
);


-- ============================================================
-- Data Normalization Errors
-- ============================================================

CREATE TABLE IF NOT EXISTS normalization_errors (
    error_id SERIAL PRIMARY KEY,

    event_id UUID,

    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_error_event
        FOREIGN KEY (event_id)
        REFERENCES events (event_id)
        ON DELETE SET NULL
);


-- ============================================================
-- TABLES TO integrate through seed values for standardization and normalization
-- ============================================================

-- ============================================================
-- COUNTRY CODES (ISO 3166-1 alpha-2)
-- ============================================================

CREATE TABLE IF NOT EXISTS country_codes (
    country_code CHAR(2) PRIMARY KEY,   -- ES, US, GB, etc.
    country_name TEXT NOT NULL,
    iso3_code CHAR(3),                  -- ESP, USA, GBR
    numeric_code INT,                   -- 724, 840, 826
    region TEXT,                        -- Europe, Americas, etc.
    subregion TEXT,                     -- Southern Europe, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- CURRENCY CODES (ISO 4217)
-- ============================================================

CREATE TABLE IF NOT EXISTS currency_codes (
    currency_code CHAR(3) PRIMARY KEY,  -- EUR, USD, GBP
    currency_name TEXT NOT NULL,
    symbol TEXT,                        -- €, $, £
    numeric_code INT,                   -- 978, 840, 826
    minor_unit INT,                     -- decimal places
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

