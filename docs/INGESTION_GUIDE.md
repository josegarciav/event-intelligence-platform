# Ingestion Guide — Pulsecity Event Intelligence Platform

---

## How Ingestion Works

Ingestion is fully config-driven. No Python subclassing is required to add a new source.
`ingestion.yaml` declares sources; `PipelineFactory` reads the config and instantiates the right adapter.

```
services/api/src/configs/ingestion.yaml
          │
          ▼
services/api/src/ingestion/factory.py  (PipelineFactory)
          │
          ├─ pipeline_type: "api"     → APIAdapter
          └─ pipeline_type: "scraper" → ScraperAdapter
                    │
                    ▼
          Normalization
          (field_mapper · location_parser · currency · taxonomy_mapper)
                    │
                    ▼
          Deduplication (exact match by source_event_id)
                    │
                    ▼
          PostgreSQL 16 (port 5433)
```

---

## Source Status

| Source        | Type    | Enabled | Notes                                      |
|---------------|---------|---------|--------------------------------------------|
| GetYourGuide  | api     | true    | Primary active source                      |
| Eventbrite    | api     | true    | Primary active source                      |
| RA.co         | api     | false   | GraphQL; config complete, needs API access |
| Ticketmaster  | api     | false   | REST; config complete, needs API key       |
| Civitatis     | api     | false   | REST; config complete, needs API key       |
| TripAdvisor   | api     | false   | REST; config complete, needs API key       |

---

## How to Add a New API Source

All configuration lives in `services/api/src/configs/ingestion.yaml`. No Python needed for standard REST/GraphQL sources.

**Step 1** — Add a source block under `sources:`:

```yaml
sources:
  my_source:
    enabled: true
    pipeline_type: "api"

    connection:
      endpoint: "https://api.example.com/events"
      protocol: "rest"
      timeout_seconds: 30

    max_retries: 3
    rate_limit_per_second: 2.0
```

**Step 2** — Define query parameters and response path:

```yaml
    query:
      params:
        api_key: "${MY_SOURCE_API_KEY}"
        city: "{{city}}"
        page: "{{page}}"
        limit: "{{page_size}}"
      response_path: "data.events"
      total_results_path: "data.total"
```

**Step 3** — Map source fields to canonical EventSchema fields:

```yaml
    field_mappings:
      source_event_id: "id"
      title: "name"
      description: "description"
      date: "start_date"
      city: "location.city"
      country_code: "location.country"
```

**Step 4** — Add transformations (optional):

```yaml
    transformations:
      description:
        type: "strip_html"
        source: "description"
      country_code:
        type: "uppercase"
      source_url:
        type: "template"
        template: "https://example.com/events/{{source_event_id}}"
```

**Step 5** — Set defaults and validation:

```yaml
    defaults:
      page_size: 50
      days_ahead: 7
      location:
        country_code: "ES"
        timezone: "Europe/Madrid"

    validation:
      required_fields: ["title", "source_event_id"]
      future_events_only: true
```

---

## Running a Pipeline

```python
from src.ingestion.factory import PipelineFactory

# Load config and create a pipeline for a specific source
factory = PipelineFactory("src/configs/ingestion.yaml")
pipeline = factory.create("getyourguide")
result = await pipeline.execute()

print(f"Ingested: {result.events_ingested}, Skipped: {result.events_skipped}")
```

To run all enabled sources:

```python
factory = PipelineFactory("src/configs/ingestion.yaml")
for source_name in factory.list_enabled():
    pipeline = factory.create(source_name)
    result = await pipeline.execute()
```

---

## Normalization Layer

After field extraction, every event passes through four normalization steps before being stored.

| Module                | File                                              | What it does                                                          |
|-----------------------|---------------------------------------------------|-----------------------------------------------------------------------|
| `field_mapper`        | `ingestion/normalization/field_mapper.py`         | Maps source-specific field names to canonical EventSchema fields      |
| `location_parser`     | `ingestion/normalization/location_parser.py`      | Resolves city, country, coordinates, timezone                         |
| `currency`            | `ingestion/normalization/currency.py`             | Normalizes price fields and currency codes                            |
| `taxonomy_mapper`     | `ingestion/normalization/taxonomy_mapper.py`      | Applies `taxonomy_suggestions` and `event_type_rules` from config     |

---

## Scraper Sources

For sources with no API, set `pipeline_type: "scraper"` in `ingestion.yaml`.
The scraping logic lives in `services/scrapping/` and is invoked via `ScraperAdapter`.

```yaml
sources:
  my_scraped_source:
    enabled: false
    pipeline_type: "scraper"
    connection:
      base_url: "https://example.com/events"
```

See `services/scrapping/README.md` for scraper configuration and the escalation ladder.

---

## Key Files Reference

| Path                                                        | Description                            |
|-------------------------------------------------------------|----------------------------------------|
| `services/api/src/configs/ingestion.yaml`                   | All source configurations              |
| `services/api/src/ingestion/factory.py`                     | `PipelineFactory` — creates pipelines  |
| `services/api/src/ingestion/adapters/api_adapter.py`        | Handles REST/GraphQL API sources       |
| `services/api/src/ingestion/adapters/scraper_adapter.py`    | Delegates to `services/scrapping/`     |
| `services/api/src/ingestion/normalization/field_mapper.py`  | Canonical field mapping                |
| `services/api/src/ingestion/normalization/location_parser.py` | Location/geo resolution              |
| `services/api/src/ingestion/normalization/currency.py`      | Price normalization                    |
| `services/api/src/ingestion/normalization/taxonomy_mapper.py` | Category and event_type assignment   |
| `services/api/src/ingestion/deduplication.py`               | Exact-match dedup by source_event_id  |
| `services/api/src/ingestion/orchestrator.py`                | Ties adapters → normalization → storage|
| `services/scrapping/`                                       | Config-driven web scraping service     |
