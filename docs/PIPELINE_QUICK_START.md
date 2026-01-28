# Pipeline Architecture - Quick Start Guide

## Overview

The event intelligence platform uses a modular, extensible pipeline architecture for ingesting events from diverse sources. Each source (ra.co, Meetup, Ticketmaster, etc.) has its own pipeline that inherits from `BasePipeline` and implements source-specific logic.

---

## Key Files & Their Purpose

### Core Architecture
| File | Purpose |
|------|---------|
| `ingestion/base_pipeline.py` | Abstract base class with standardized workflow |
| `ingestion/orchestrator.py` | Coordinates execution and scheduling of all pipelines |
| `normalization/event_schema.py` | Canonical EventSchema and supporting models |

### Source Implementations
| File | Purpose |
|------|---------|
| `ingestion/sources/ra_co.py` | Ra.co electronic music platform pipeline |
| `ingestion/sources/meetup.py` | Meetup community events pipeline (skeleton) |
| `ingestion/sources/ticketmaster.py` | Ticketmaster ticketing platform (future) |

### Configuration
| File | Purpose |
|------|---------|
| `configs/ingestion.yaml` | Pipeline sources, schedules, and settings |

### Documentation
| File | Purpose |
|------|---------|
| `docs/PIPELINE_ARCHITECTURE.md` | Full UML diagrams, data flow, design details |

---

## How to Add a New Source

### Step 1: Create Pipeline Class

Create a new file in `ingestion/sources/` (e.g., `ticketmaster.py`):

```python
from typing import List, Dict, Any, Tuple
from ingestion.base_pipeline import BasePipeline, PipelineConfig
from normalization.event_schema import EventSchema

class TicketmasterEventPipeline(BasePipeline):
    """Pipeline for Ticketmaster events."""
    
    def fetch_raw_data(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetch events from Ticketmaster API."""
        # Call Ticketmaster API
        # Handle pagination
        # Return list of raw event dicts
        pass
    
    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Ticketmaster event into intermediate format."""
        # Extract title, date, venue, price, etc.
        # Normalize dates and locations
        # Return cleaned dict
        pass
    
    def map_to_taxonomy(self, parsed_event: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """Map to Human Experience Taxonomy."""
        # Classify event (concert? sports? theater?)
        # Return (primary_category, taxonomy_dimensions)
        pass
    
    def normalize_to_schema(self, parsed_event: Dict[str, Any], 
                           primary_cat: str,
                           taxonomy_dims: List[Dict[str, Any]]) -> EventSchema:
        """Normalize to canonical EventSchema."""
        # Create fully validated EventSchema instance
        # Map all fields from parsed_event to schema fields
        pass
    
    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """Validate event with source-specific rules."""
        # Check location, time, price, etc.
        # Return (is_valid, errors_list)
        pass
    
    def enrich_event(self, event: EventSchema) -> EventSchema:
        """Enrich event with additional data."""
        # Geocode venue if coordinates missing
        # Fetch artist images
        # Calculate duration
        # Return enriched event
        pass
```

### Step 2: Update Configuration

Add source to `configs/ingestion.yaml`:

```yaml
sources:
  ticketmaster:
    enabled: true
    base_url: "https://app.ticketmaster.com/discovery/v2"
    api_key: "${TICKETMASTER_API_KEY}"
    batch_size: 200
    rate_limit_per_second: 2.0
    
    schedule:
      type: "interval"
      interval_hours: 12
    
    custom:
      countries: ["US", "GB"]
      classifiers: ["music", "sports", "arts"]
```

### Step 3: Register in Orchestrator

In `orchestrator.py`, update `create_orchestrator_from_config()`:

```python
from ingestion.sources.ticketmaster import TicketmasterEventPipeline

# ...in create_orchestrator_from_config():
elif source_name == 'ticketmaster':
    pipeline_class = TicketmasterEventPipeline
```

### Step 4: Write Tests

Create `tests/unit/sources/test_ticketmaster.py`:

```python
import pytest
from ingestion.sources.ticketmaster import TicketmasterEventPipeline
from ingestion.base_pipeline import PipelineConfig

@pytest.fixture
def pipeline():
    config = PipelineConfig(source_name="ticketmaster")
    return TicketmasterEventPipeline(config)

def test_parse_raw_event(pipeline):
    raw_event = {
        "id": "123",
        "name": "Concert Name",
        # ... other fields
    }
    parsed = pipeline.parse_raw_event(raw_event)
    assert parsed["title"] == "Concert Name"
    # ... more assertions
```

---

## Running Pipelines

### Execute Single Pipeline

```python
from ingestion import PipelineOrchestrator
from ingestion.base_pipeline import PipelineConfig
from ingestion.sources.ra_co import RaCoEventPipeline

# Create config
config = PipelineConfig(
    source_name="ra_co",
    base_url="https://ra.co/graphql",
    api_key="your-api-key"
)

# Create orchestrator and register pipeline
orchestrator = PipelineOrchestrator()
orchestrator.register_pipeline("ra_co", RaCoEventPipeline, config)

# Execute
result = orchestrator.execute_pipeline("ra_co", cities=["London", "Berlin"])

# Access results
print(f"Events processed: {result.total_events_processed}")
print(f"Successful: {result.successful_events}")
print(f"Events: {result.events}")
```

### Execute All Pipelines

```python
import yaml
from ingestion import create_orchestrator_from_config

# Load config
with open("configs/ingestion.yaml") as f:
    config = yaml.safe_load(f)

# Create orchestrator
orchestrator = create_orchestrator_from_config(config)

# Execute all enabled pipelines
results = orchestrator.execute_all_pipelines()

for source_name, result in results.items():
    print(f"{source_name}: {result.successful_events} events")
```

### Schedule Pipelines

```python
# Schedule with cron (requires APScheduler)
orchestrator.schedule_pipeline("ra_co", {
    "type": "cron",
    "cron": "0 */6 * * *"  # Every 6 hours
})

# Schedule with interval
orchestrator.schedule_pipeline("meetup", {
    "type": "interval",
    "interval_hours": 4
})
```

### Get Execution History

```python
# All executions
all_executions = orchestrator.get_execution_history()

# Recent executions for a source
ra_co_executions = orchestrator.get_execution_history("ra_co", limit=10)

# Statistics
stats = orchestrator.get_execution_stats("ra_co")
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Total events: {stats['total_events_processed']}")
```

---

## Understanding the Workflow

### The Pipeline Execution Flow

Each pipeline execution follows these 6 sequential steps (all implemented in `BasePipeline.execute()`):

```
┌─────────┐
│ FETCH   │  Retrieve raw data from source (API/scraping)
└────┬────┘
     │
     ▼
┌─────────┐
│ PARSE   │  Extract structured fields from raw data
└────┬────┘
     │
     ▼
┌──────────────┐
│ TAXONOMY MAP │  Classify to Human Experience Taxonomy
└────┬─────────┘
     │
     ▼
┌──────────────┐
│ NORMALIZE    │  Transform to canonical EventSchema
└────┬─────────┘
     │
     ▼
┌──────────────┐
│ VALIDATE     │  Check data quality and business rules
└────┬─────────┘
     │
     ▼
┌──────────────┐
│ ENRICH       │  Add additional data (geocoding, images, etc.)
└────┬─────────┘
     │
     ▼
┌──────────────────┐
│ QUALITY SCORING  │  Calculate data quality (0.0-1.0)
└────┬─────────────┘
     │
     ▼
┌──────────────┐
│ STORE        │  Save to database
└──────────────┘
```

Each step can fail on individual events without stopping the pipeline. Errors are logged and reported in the final `PipelineExecutionResult`.

---

## Schema Structure

The canonical `EventSchema` captures:

1. **Core Event Info** - title, description, URL
2. **Human Experience Taxonomy** - primary category + multi-dimensional taxonomy mappings
3. **Timing** - start/end datetime, timezone, duration
4. **Location** - venue name, address, coordinates, city, timezone
5. **Pricing** - free/paid, min/max price, ticket info
6. **Organizer** - name, URL, contact, social metrics
7. **Media** - images, videos, assets
8. **Source Metadata** - which source, original ID, URL, last sync
9. **Quality Metrics** - data quality score, validation errors
10. **Engagement** - attendees, views, shares, likes
11. **Taxonomy Mappings** - confidence scores for category classifications

---

## Taxonomy Integration

Every event is mapped to the Human Experience Taxonomy with **confidence scores**:

```python
event.taxonomy_dimensions = [
    TaxonomyDimension(
        primary_category="play_and_fun",           # Primary experience
        subcategory="music_and_rhythm_play",       # Specific activity
        values=["expression", "energy", "flow"],   # Core values
        confidence=0.95                            # How sure we are
    ),
    TaxonomyDimension(
        primary_category="social_connection",
        subcategory="shared_activities_and_co_experience",
        values=["belonging", "shared joy"],
        confidence=0.8
    ),
]
```

This enables **intelligent downstream analytics** - you can analyze:
- Which experiences are most valuable to users
- What factors drive engagement
- How to recommend events based on user interests

---

## Quality Scoring

Each event gets a quality score (0.0 to 1.0) based on:

- **40%** - Key fields present (title, location, start_datetime)
- **30%** - Enrichment fields (image, coordinates, price, description)
- **20%** - Taxonomy mapping confidence
- **-10%** - Penalty for validation errors

This allows downstream consumers to filter events by data quality.

---

## Error Handling

The pipeline is **resilient to individual event failures**:

- If parsing one event fails → skip it, continue with next
- If validation fails → log error, still include event (with warnings)
- If enrichment fails → continue without enrichment (non-critical)
- If the entire source fails → return empty result with error details

All errors are captured in `PipelineExecutionResult.errors` for debugging.

---

## Best Practices

1. **Implement parse_raw_event() carefully**
   - Extract ALL available fields from the source
   - Handle various data formats (dates, prices, etc.)
   - Set defaults for missing fields

2. **Be conservative with taxonomy mapping**
   - Use high confidence (0.8+) only when very certain
   - Include multiple dimensions if applicable
   - Consider future machine learning classification

3. **Validate rigorously in validate_event()**
   - Check business logic (start time in future?)
   - Verify data consistency
   - Report specific, actionable errors

4. **Make enrichment non-blocking**
   - Enrichment failures should not fail the entire event
   - Always try to complete pipeline even with partial data
   - Log enrichment failures separately

5. **Document source-specific quirks**
   - Comment on date/time formats unique to source
   - Note any limitations (e.g., no phone numbers)
   - Record rate limits and API constraints

---

## Advanced Usage

### Custom Validation

Override validation for your source:

```python
def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
    errors = []
    
    # Meetup-specific: require minimum RSVP count
    if event.engagement and event.engagement.going_count < 5:
        errors.append("Event has too few RSVPs to be included")
    
    # Meetup requires group info
    if "group_id" not in event.custom_fields:
        errors.append("Missing group information")
    
    return len(errors) == 0, errors
```

### Custom Enrichment

```python
def enrich_event(self, event: EventSchema) -> EventSchema:
    # Fetch additional Meetup-specific data
    if event.source.source_name == "meetup":
        group_id = event.custom_fields.get("group_id")
        if group_id:
            group_data = self._fetch_group_data(group_id)
            event.organizer.follower_count = group_data["member_count"]
    
    return event
```

### Parallel Execution

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=3)

sources = ["ra_co", "meetup", "ticketmaster"]
futures = [
    executor.submit(orchestrator.execute_pipeline, source)
    for source in sources
]

results = {source: future.result() for source, future in zip(sources, futures)}
```

---

## Monitoring & Debugging

### Check Pipeline Status

```python
# List registered pipelines
print(orchestrator.list_pipelines())

# Get latest execution
latest = orchestrator.get_latest_execution("ra_co")
print(f"Status: {latest.status}")
print(f"Duration: {latest.duration_seconds}s")
print(f"Success rate: {latest.success_rate:.1f}%")
```

### Debug Individual Events

```python
# Access events with low quality scores
low_quality = [e for e in result.events if e.data_quality_score < 0.5]

# Check validation errors
for event in result.events:
    if event.normalization_errors:
        print(f"{event.title}: {event.normalization_errors}")
```

### Monitor API Usage

```python
# Get statistics
stats = orchestrator.get_execution_stats()

print(f"Total API calls: {stats['total_executions']}")
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Avg events/run: {stats['average_events_per_run']:.0f}")
```

---

## Next Steps

1. **Implement Meetup pipeline** (follow ra.co as template)
2. **Set up database models** for storing normalized events
3. **Add enrichment services** (geocoding, image validation)
4. **Implement scheduling** with APScheduler
5. **Build monitoring dashboard** for execution stats
6. **Add data quality reports** for each source
7. **Create downstream analytics** leveraging taxonomy

Refer to `docs/PIPELINE_ARCHITECTURE.md` for detailed UML diagrams and design documentation.
