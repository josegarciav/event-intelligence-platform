# Proposed Repository Improvements

This document outlines 5 ranked improvements for the Event Intelligence Platform, categorized by impact and importance. These recommendations focus on data quality, user-facing features, technical debt reduction, and operational visibility.

---

## 1. Integrated Ingestion-to-Enrichment Triggering Architecture
**Rank:** 1 | **Impact:** High | **Category:** Data Quality / Architecture | **Status:** ✅ Implemented

### Description
Currently, the ingestion pipeline and the enrichment layer (taxonomy mapping, emotional outputs, etc.) operate somewhat independently or in a tightly coupled sequential manner within the `orchestrator`. As the platform scales, we need a more robust, event-driven or batch-triggered architecture that ensures every ingested event undergoes a full enrichment cycle (e.g., LLM-based categorization, artist metadata fetching, etc.) before being marked as "ready" for the public API.

### Proposed Solution
- Implement a post-persistence hook in `PipelineOrchestrator` or a separate `EnrichmentService`.
- Introduce a status-tracking mechanism for events to manage the enrichment lifecycle.
- Support "batch enrichment" to optimize LLM API calls and artist metadata lookups.

### Implementation
`PostIngestionTrigger` (`services/api/src/agents/orchestration/pipeline_triggers.py`) — call `trigger.on_pipeline_complete(pipeline_result)` after any `pipeline.execute()`. The ingestion pipeline writes JSONL batches to `data/batches/`; the trigger reads them, runs the full agent chain (`BatchEnrichmentRunner`), and persists enriched events to PostgreSQL. Batch size is configurable per agent in `agents.yaml`.

### Schema Changes
```sql
-- Track enrichment status on the central event record
ALTER TABLE events ADD COLUMN enrichment_status TEXT DEFAULT 'pending'; -- pending, in_progress, completed, failed
ALTER TABLE events ADD COLUMN last_enriched_at TIMESTAMP;

-- Optional: Detailed enrichment logs for debugging
CREATE TABLE enrichment_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(event_id) ON DELETE CASCADE,
    stage TEXT NOT NULL, -- taxonomy, artists, location_refinement
    status TEXT NOT NULL,
    error_message TEXT,
    duration_ms INT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 2. Event Discovery & Advanced Filtering API
**Rank:** 2 | **Impact:** High | **Category:** User Facing Features

### Description
The current FastAPI implementation provides only basic health and taxonomy listing endpoints. To support the "Event Discovery App" mentioned in the roadmap, we need a robust search API that allows users to find events based on their current context (location, time, interests).

### Proposed Solution
- Implement a `/events/search` endpoint with support for:
  - Geo-spatial queries (nearby events).
  - Temporal filtering (this weekend, tonight, etc.).
  - Taxonomy filtering (primary category, subcategory).
  - Text-based search across titles and descriptions.

### Schema Changes
- Add Full-Text Search (FTS) capabilities to the `events` table to improve search performance.
```sql
-- Add a search vector for efficient title/description lookup
ALTER TABLE events ADD COLUMN search_vector tsvector;
CREATE INDEX idx_events_search ON events USING GIN(search_vector);

-- Update trigger to maintain the search vector
CREATE FUNCTION events_search_trigger() RETURNS trigger AS $$
begin
  new.search_vector :=
     setweight(to_tsvector('english', coalesce(new.title,'')), 'A') ||
     setweight(to_tsvector('english', coalesce(new.description,'')), 'B');
  return new;
end
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_events_search_update BEFORE INSERT OR UPDATE
ON events FOR EACH ROW EXECUTE FUNCTION events_search_trigger();
```

---

## 3. Artist Profile Enrichment (Multimedia & Social)
**Rank:** 3 | **Impact:** Medium-High | **Category:** User Facing Features

### Description
As noted in the README "Brainstorming" section, users should get a feel for an artist's style directly on the platform. The current `artists` table has placeholders for URLs but lacks the metadata needed for a rich UI (e.g., profile images, popular tracks, genres).

### Proposed Solution
- **Genre enrichment (done):** `FeatureAlignmentAgent` already runs a MusicBrainz HTTP pass after its LLM batch to fill `artists[*].genre` (fill-null-only, no auth required).
- **Multimedia enrichment (open):** Extend with SoundCloud, Spotify, or Instagram APIs to fetch profile images, popular tracks, and follower counts.
- Cache artist-level metadata to avoid redundant external API calls during event ingestion.

### Schema Changes
```sql
ALTER TABLE artists ADD COLUMN profile_image_url TEXT;
ALTER TABLE artists ADD COLUMN popularity_score INT; -- 0-100
ALTER TABLE artists ADD COLUMN follower_count INT;
ALTER TABLE artists ADD COLUMN bio TEXT;
ALTER TABLE artists ADD COLUMN last_enriched_at TIMESTAMP;

-- Track artist-specific media (top tracks, promo videos)
CREATE TABLE artist_media_assets (
    asset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    artist_id UUID REFERENCES artists(artist_id) ON DELETE CASCADE,
    type TEXT, -- 'audio_sample', 'image', 'video'
    url TEXT NOT NULL,
    provider TEXT, -- 'spotify', 'soundcloud'
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 4. Fuzzy Event Deduplication & Conflict Resolution
**Rank:** 4 | **Impact:** Medium | **Category:** Data Quality / Technical Debt | **Status:** ✅ Implemented

### Description
The platform ingests data from multiple heterogeneous sources. While UUIDv5 provides deterministic IDs, events might still be duplicated across sources with slightly different titles or start times. We need a way to merge these into a single "Canonical Event" while preserving the source-specific details for auditing.

### Proposed Solution
- Upgrade `EventDeduplicator` to use fuzzy string matching (e.g., Levenshtein distance) on titles and location names.
- Implement a "Master Record" pattern where one event is chosen as the canonical version and others are linked to it.

### Implementation
`DeduplicationAgent` (`services/api/src/agents/enrichment/deduplication_agent.py`) — two-pass architecture: (1) rule-based exact match on `(title_slug, date, venue_slug)` using deterministic UUID5 group IDs, always runs with no LLM; (2) LLM fuzzy analysis on remaining candidates for near-duplicates and recurring series, only accepts groups with confidence ≥ 0.80. Results written to `event.custom_fields` and persisted to the `event_groups` table. Recurring groups additionally set `event.is_recurring = True` and `event.recurrence_pattern` (one of `intraday | daily | weekly | monthly | annual`) directly on the EventSchema, which the persistence layer writes to `events.is_recurring` and `events.recurrence_pattern`.

### Schema Changes
```sql
-- Support linking duplicate events to a single canonical record
ALTER TABLE events ADD COLUMN is_canonical BOOLEAN DEFAULT TRUE;
ALTER TABLE events ADD COLUMN merged_into_id UUID REFERENCES events(event_id);

-- Track confidence in the merge
CREATE TABLE deduplication_logs (
    dedup_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_event_id UUID REFERENCES events(event_id),
    duplicate_event_id UUID REFERENCES events(event_id),
    match_score FLOAT,
    match_strategy TEXT, -- 'fuzzy_title', 'geo_temporal_proximity'
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. Operational Health & Data Quality Metrics
**Rank:** 5 | **Impact:** Medium | **Category:** Operational Visibility

### Description
Operational visibility is currently limited to logs. We need structured metrics to monitor the health of the ingestion pipelines, the accuracy of normalization, and the overall "freshness" of the data.

### Proposed Solution
- Integrate Prometheus/OpenTelemetry for real-time monitoring of pipeline latency and success rates.
- Periodically aggregate `normalization_errors` and `data_quality_score` into a dashboard-ready table.

### Schema Changes
```sql
-- Aggregate metrics for dashboarding
CREATE TABLE pipeline_metrics (
    metric_id SERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    run_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    events_fetched INT,
    events_saved INT,
    errors_count INT,
    avg_quality_score FLOAT,
    duration_seconds FLOAT
);

-- Index for efficient historical health lookups
CREATE INDEX idx_pipeline_metrics_source_time ON pipeline_metrics(source_name, run_timestamp DESC);
```
