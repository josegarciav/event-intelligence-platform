# Pipeline Architecture - UML Diagram & Design Documentation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────────┘

                                   External Sources
                   ┌──────────────────┬──────────────────┬──────────────────┐
                   │     ra.co        │     Meetup       │   Ticketmaster   │
                   │   (Web API)      │   (REST API)     │   (REST API)     │
                   └────────┬─────────┴────────┬─────────┴────────┬────────┘
                            │                  │                  │
                            ▼                  ▼                  ▼
        ┌──────────────────────────────┐ ┌──────────────────────────────────┐
        │  RaCoEventPipeline           │ │  MeetupEventPipeline             │ ...
        │  (inherits from BasePipeline)│ │  (inherits from BasePipeline)    │
        └──────────────────────────────┘ └──────────────────────────────────┘
                   │                                      │
                   └──────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼─────────────────┐
                    │      ORCHESTRATION LAYER          │
                    │  (PipelineOrchestrator)           │
                    │  - Scheduling                     │
                    │  - Execution management           │
                    │  - Error handling                 │
                    │  - Storage coordination           │
                    └─────────────────┬─────────────────┘
                                      │
        ┌─────────────────────────────▼─────────────────────────────┐
        │         NORMALIZATION & VALIDATION (Canonical Schema)      │
        │         - Event Schema Validation                          │
        │         - Quality Scoring                                  │
        │         - Data Enrichment                                  │
        └─────────────────────────────┬─────────────────────────────┘
                                      │
                    ┌─────────────────▼─────────────────┐
                    │      STORAGE LAYER                │
                    │  - Raw Event Table                │
                    │  - Clean Event Table              │
                    │  - Audit Trail                    │
                    └─────────────────────────────────┘
```

---

## Class Hierarchy UML

```
                    ┌─────────────────────────────────┐
                    │   BasePipeline (ABC)            │
                    ├─────────────────────────────────┤
                    │ - config: PipelineConfig        │
                    │ - logger: Logger                │
                    │ - execution_id: str             │
                    ├─────────────────────────────────┤
                    │ + execute(**kwargs)             │
                    │ + _process_events_batch()       │
                    │ + _calculate_quality_score()    │
                    │ # fetch_raw_data() [abstract]   │
                    │ # parse_raw_event() [abstract]  │
                    │ # map_to_taxonomy() [abstract]  │
                    │ # normalize_to_schema() [ab]    │
                    │ # validate_event() [abstract]   │
                    │ # enrich_event() [abstract]     │
                    └─────────────────────────────────┘
                            ▲           ▲           ▲
                    ┌───────┘           │           └──────┐
                    │                   │                  │
        ┌───────────▼──────────┐  ┌─────▼────────────┐  ┌─▼──────────────────┐
        │ RaCoEventPipeline    │  │ MeetupPipeline   │  │TicketmasterPipeline│
        ├──────────────────────┤  ├──────────────────┤  ├───────────────────┤
        │ - base_url: str      │  │ - base_url: str  │  │ - base_url: str   │
        │ - api_key: str       │  │ - api_key: str   │  │ - api_key: str    │
        │ - cache_ttl: int     │  │ - group_ids: []  │  │ - markets: []     │
        ├──────────────────────┤  ├──────────────────┤  ├───────────────────┤
        │ + fetch_raw_data()   │  │ + fetch_raw_data │  │ + fetch_raw_data()│
        │ + parse_raw_event()  │  │ + parse_raw_event│  │ + parse_raw_event │
        │ + map_to_taxonomy()  │  │ + map_to_taxonomy│  │ + map_to_taxonomy │
        │ + normalize_to_schema│  │ + normalize_to.. │  │ + normalize_to..  │
        │ + validate_event()   │  │ + validate_event │  │ + validate_event()│
        │ + enrich_event()     │  │ + enrich_event() │  │ + enrich_event()  │
        └──────────────────────┘  └──────────────────┘  └───────────────────┘
                    │                   │                  │
                    └───────┬───────────┘──────────┬───────┘
                            │                      │
                            └──────────────────────┘
                                     │
                    ┌────────────────▼──────────────────┐
                    │  PipelineOrchestrator             │
                    ├───────────────────────────────────┤
                    │ - pipelines: Dict[str, Pipeline]  │
                    │ - scheduler: APScheduler          │
                    ├───────────────────────────────────┤
                    │ + register_pipeline()             │
                    │ + execute_pipeline()              │
                    │ + execute_all()                   │
                    │ + schedule_pipeline()             │
                    │ + get_execution_results()         │
                    └───────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           DATA PROCESSING PIPELINE                         │
└────────────────────────────────────────────────────────────────────────────┘

STAGE 1: FETCH
┌─────────────────────────────────┐
│ fetch_raw_data()                │
│                                 │
│ Input: Source API parameters    │
│ Output: Raw JSON/HTML list      │
│                                 │
│ Example (ra.co):                │
│ [                               │
│   {                             │
│     "id": "12345",              │
│     "name": "Event Title",      │
│     "date": "2026-03-15",       │
│     ...                         │
│   },                            │
│   ...                           │
│ ]                               │
└──────────────┬──────────────────┘
               │
               ▼
STAGE 2: PARSE (for each raw_event)
┌─────────────────────────────────┐
│ parse_raw_event()               │
│                                 │
│ Input: Single raw event dict    │
│ Output: Intermediate struct     │
│                                 │
│ Parsed Event {                  │
│   title,                        │
│   start_datetime,               │
│   end_datetime,                 │
│   location {                    │
│     venue_name,                 │
│     city,                       │
│     coordinates,                │
│     ...                         │
│   },                            │
│   price {                       │
│     min,                        │
│     max,                        │
│     ...                         │
│   },                            │
│   organizer,                    │
│   ...                           │
│ }                               │
└──────────────┬──────────────────┘
               │
               ▼
STAGE 3: TAXONOMY MAPPING
┌─────────────────────────────────┐
│ map_to_taxonomy()               │
│                                 │
│ Input: Parsed event             │
│ Output: (primary_category,      │
│          taxonomy_dimensions)   │
│                                 │
│ Example:                        │
│ Primary: "play_and_fun"         │
│ Dimensions: [                   │
│   {                             │
│     "primary": "play_and_fun",  │
│     "subcategory": "music..",   │
│     "values": [...],            │
│     "confidence": 0.95          │
│   },                            │
│   {                             │
│     "primary": "social..",      │
│     "subcategory": "shared..",  │
│     "values": [...],            │
│     "confidence": 0.8           │
│   }                             │
│ ]                               │
└──────────────┬──────────────────┘
               │
               ▼
STAGE 4: NORMALIZATION TO SCHEMA
┌─────────────────────────────────┐
│ normalize_to_schema()           │
│                                 │
│ Input: Parsed event +           │
│        taxonomy data            │
│ Output: EventSchema (validated) │
│                                 │
│ Fully normalized EventSchema    │
│ with all fields typed &         │
│ validated per Pydantic model    │
└──────────────┬──────────────────┘
               │
               ▼
STAGE 5: VALIDATION
┌─────────────────────────────────┐
│ validate_event()                │
│                                 │
│ Input: EventSchema              │
│ Output: (is_valid, errors_list) │
│                                 │
│ Checks:                         │
│ - Location is valid             │
│ - Start time is reasonable      │
│ - Price is reasonable           │
│ - Organizer info exists         │
│ - etc.                          │
└──────────────┬──────────────────┘
               │
               ▼
STAGE 6: ENRICHMENT
┌─────────────────────────────────┐
│ enrich_event()                  │
│                                 │
│ Input: EventSchema              │
│ Output: Enriched EventSchema    │
│                                 │
│ Enrichments:                    │
│ - Geocoding (if missing coords) │
│ - Timezone inference            │
│ - Duration calculation          │
│ - Image validation              │
│ - Organizer enrichment          │
│ - Popularity prediction         │
└──────────────┬──────────────────┘
               │
               ▼
STAGE 7: QUALITY ASSESSMENT
┌─────────────────────────────────┐
│ _calculate_quality_score()      │
│                                 │
│ Factors:                        │
│ - Key field presence (40%)      │
│ - Enrichment (30%)              │
│ - Taxonomy confidence (20%)     │
│ - Error penalty (-10%)          │
│                                 │
│ Result: 0.0 - 1.0 score        │
└──────────────┬──────────────────┘
               │
               ▼
STAGE 8: STORAGE & RETURN
┌─────────────────────────────────┐
│ Orchestrator stores events      │
│ Returns PipelineExecutionResult │
│                                 │
│ PipelineExecutionResult {       │
│   status,                       │
│   execution_id,                 │
│   total_events,                 │
│   successful_events,            │
│   events: [EventSchema],        │
│   errors: [],                   │
│ }                               │
└─────────────────────────────────┘
```

---

## Sequence Diagram: Full Pipeline Execution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Actor    │ Orchestrator    │ RaCoEventPipeline │ EventSchema │ Database    │
└─────────────────────────────────────────────────────────────────────────────┘
    │                │                  │              │            │
    │ execute()      │                  │              │            │
    ├───────────────►│                  │              │            │
    │                │ execute()        │              │            │
    │                ├─────────────────►│              │            │
    │                │                  │ fetch_raw    │            │
    │                │                  ├─────►[ra.co]             │
    │                │                  │◄─────[raw]               │
    │                │                  │              │            │
    │                │                  │ parse event ◄┤            │
    │                │                  │              │            │
    │                │                  │ map_taxonomy │            │
    │                │                  │              │            │
    │                │                  │ normalize    │ ╔════════╗ │
    │                │                  ├─────────────►║ create  ║ │
    │                │                  │◄─────────────╚════════╝ │
    │                │                  │              │            │
    │                │                  │ validate     │            │
    │                │                  │              │            │
    │                │                  │ enrich       │            │
    │                │                  │              │            │
    │                │◄─────EventSchema─┤              │            │
    │                │                  │              │ store()    │
    │                ├──────────────────────────────────────────►│
    │                │                  │              │            │
    │ ExecutionResult│                  │              │            │
    │◄───────────────┤                  │              │            │
    │                │                  │              │            │
```

---

## Directory Structure

```
ingestion/
│
├── __init__.py
├── base_pipeline.py              # BasePipeline abstract class + configs
│
├── sources/
│   ├── __init__.py
│   ├── ra_co.py                  # RaCoEventPipeline implementation
│   ├── meetup.py                 # MeetupEventPipeline implementation
│   ├── ticketmaster.py           # TicketmasterEventPipeline (future)
│   └── ...
│
├── orchestrator.py               # PipelineOrchestrator for scheduling
│
├── enrichment/
│   ├── __init__.py
│   ├── geocoding.py              # Geocoding service
│   ├── timezone.py               # Timezone inference
│   ├── image_validation.py       # Image URL checking
│   └── organizer_enrichment.py   # Org social metrics
│
├── validators/
│   ├── __init__.py
│   ├── location_validator.py     # Location validation
│   ├── price_validator.py        # Price validation
│   └── event_validator.py        # Event-specific validation
│
└── utils/
    ├── __init__.py
    ├── http_client.py            # Shared HTTP client with retry logic
    ├── rate_limiter.py           # Rate limiting utilities
    ├── cache.py                  # Caching layer
    └── parsers.py                # Common parsing utilities (dates, prices)

normalization/
├── __init__.py
├── event_schema.py               # Canonical EventSchema (new)
├── schema.py                     # Old schema (to be deprecated/consolidated)
└── enrich.py                     # Enrichment logic

storage/
├── __init__.py
├── database.py                   # SQLAlchemy models
├── repository.py                 # Data access layer
└── migrations/
    └── versions/
```

---

## Configuration Example

```yaml
# configs/ingestion.yaml

sources:
  
  ra_co:
    enabled: true
    base_url: "https://ra.co/graphql"
    batch_size: 100
    rate_limit_per_second: 1.0
    max_retries: 3
    request_timeout: 30
    schedule:
      type: "interval"
      interval_hours: 6
      start_hours: [0, 6, 12, 18]
    enrichment:
      geocoding: true
      organizer_metrics: true
      image_validation: true
    validation:
      require_coordinates: false
      require_image: false
      future_events_only: true
      days_ahead: 90
    custom:
      cities: ["London", "Berlin", "Barcelona", "Amsterdam"]
      event_types: ["DJ", "Live", "Festival"]
  
  meetup:
    enabled: true
    base_url: "https://api.meetup.com"
    api_key: "${MEETUP_API_KEY}"
    batch_size: 50
    rate_limit_per_second: 0.5
    max_retries: 3
    request_timeout: 30
    schedule:
      type: "cron"
      cron: "0 */4 * * *"  # Every 4 hours
    custom:
      group_ids: ["12345", "67890"]
      categories: ["tech", "music", "sports"]
```

---

## Implementation Checklist for New Sources

When adding a new event source, follow these steps:

- [ ] Create new file in `ingestion/sources/` (e.g., `sources/new_source.py`)
- [ ] Create class inheriting from `BasePipeline`
- [ ] Implement `fetch_raw_data()` - handle API/scraping
- [ ] Implement `parse_raw_event()` - extract key fields
- [ ] Implement `map_to_taxonomy()` - classify to Human Experience Taxonomy
- [ ] Implement `normalize_to_schema()` - map to EventSchema
- [ ] Implement `validate_event()` - source-specific validation
- [ ] Implement `enrich_event()` - optional enrichment logic
- [ ] Write unit tests in `tests/unit/sources/test_new_source.py`
- [ ] Write integration tests in `tests/integration/test_new_source_integration.py`
- [ ] Create config in `configs/ingestion.yaml`
- [ ] Register in orchestrator
- [ ] Add to README documentation

---

## Key Design Principles

### 1. **Separation of Concerns**
Each pipeline step is a separate method with clear input/output contracts.

### 2. **Extensibility**
Abstract methods enforce that all sources implement required steps.
New sources simply inherit and override methods.

### 3. **Error Resilience**
Errors in individual events don't crash the pipeline.
All errors are captured and logged for debugging.

### 4. **Data Quality First**
Quality scoring is built-in, not an afterthought.
Normalization errors are tracked and surfaced.

### 5. **Taxonomy-Centric**
All events are classified using the Human Experience Taxonomy.
This enables intelligent downstream analytics and recommendations.

### 6. **Canonical Schema**
Single source of truth for event representation.
Ensures consistency across all sources and downstream systems.

---

## Example: Ra.co Implementation Skeleton

```python
# ingestion/sources/ra_co.py

from typing import List, Dict, Any, Tuple
from datetime import datetime
import requests

from ingestion.base_pipeline import BasePipeline, PipelineConfig
from normalization.event_schema import EventSchema, EventType, LocationInfo
from normalization.event_schema import PrimaryCategory, Subcategory, TaxonomyDimension


class RaCoEventPipeline(BasePipeline):
    """Pipeline for ingesting events from ra.co (electronic music platform)."""
    
    def fetch_raw_data(self, cities: List[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """Fetch events from ra.co GraphQL API."""
        # Implementation: Call ra.co API with pagination
        pass
    
    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse ra.co event JSON into intermediate format."""
        # Implementation: Extract fields from ra.co response
        pass
    
    def map_to_taxonomy(self, parsed_event: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """Map ra.co event to Human Experience Taxonomy."""
        # Implementation: DJ/live event -> music_and_rhythm_play + social_connection
        pass
    
    def normalize_to_schema(self, parsed_event: Dict[str, Any], 
                           primary_cat: str,
                           taxonomy_dims: List[Dict[str, Any]]) -> EventSchema:
        """Normalize to EventSchema."""
        # Implementation: Create EventSchema from parsed data
        pass
    
    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """Validate ra.co event."""
        # Implementation: Venue must exist, start time must be reasonable, etc.
        pass
    
    def enrich_event(self, event: EventSchema) -> EventSchema:
        """Enrich event with additional data."""
        # Implementation: Geocode venue, fetch artist info, etc.
        pass
```

This comprehensive design provides a solid foundation for scaling the event intelligence platform!
