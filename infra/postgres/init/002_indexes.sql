-- ============================================================
-- EVENT FILTERING
-- ============================================================

CREATE INDEX idx_events_start_datetime
ON events(start_datetime);

CREATE INDEX idx_events_location
ON events(location_id);

CREATE INDEX idx_events_primary_category
ON events(primary_category_id);

-- Geospatial & Location
CREATE INDEX idx_locations_geo 
ON locations(latitude, longitude);

CREATE INDEX IF NOT EXISTS idx_locations_city ON locations(city);

-- ============================================================
-- SNAPSHOT LOOKUPS
-- ============================================================

CREATE INDEX idx_price_event
ON price_snapshots(event_id);

CREATE INDEX idx_engagement_event
ON engagement_snapshots(event_id);


-- ============================================================
-- TAXONOMY
-- ============================================================

CREATE INDEX idx_taxonomy_event
ON event_taxonomy_mappings(event_id);

CREATE INDEX idx_taxonomy_subcategory
ON event_taxonomy_mappings(subcategory_id);

-- Search Optimization
-- Index for searching event titles and descriptions
CREATE INDEX idx_events_title_search ON events USING gin(to_tsvector('english', title));

-- Fast lookup for events by a specific artist
CREATE INDEX idx_event_artists_artist_id ON event_artists(artist_id);

-- Fast lookup for events by a specific tag
CREATE INDEX idx_event_tags_tag ON event_tags(tag);



