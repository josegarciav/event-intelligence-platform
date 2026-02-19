# Start Here — Pulsecity Developer Orientation

---

## What Is Pulsecity

Pulsecity is an event intelligence platform that treats events as data products, not listings.
Raw event signals are ingested from APIs and scrapers, normalized into a canonical schema, and then processed by a chain of LLM agents that add taxonomy, emotional context, quality scores, and deduplication intelligence.
The result is a rich, structured event dataset designed for discovery, analytics, and machine-learning applications.

---

## Repo Layout

```text
event-intelligence-platform/
├── apps/
│   ├── landing/          Next.js 15 static site — live on GitHub Pages
│   ├── web/              (stub)
│   └── mobile/           (stub)
│
├── services/
│   ├── api/              FastAPI backend + MCP agent enrichment system
│   │   └── src/
│   │       ├── agents/   LLM enrichment agents + MCP layer
│   │       ├── ingestion/ Config-driven pipeline system
│   │       ├── schemas/  Canonical EventSchema (Pydantic)
│   │       ├── configs/  ingestion.yaml, agents.yaml
│   │       └── main.py   FastAPI entrypoint
│   └── scrapping/        Config-driven web scraping service
│
├── packages/
│   └── ui/               Shared UI components
│
├── infra/
│   ├── postgres/         PostgreSQL 16 via Docker Compose (port 5433)
│   └── api/              API Dockerfile
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── notebooks/            Jupyter exploration notebooks
├── docs/                 Architecture documentation
└── data/raw/
```

---

## The Two-Phase Data Flow

```
┌──────────────────────────────────────────────────────────┐
│                     External Sources                      │
│   GetYourGuide · RA.co · Ticketmaster · Eventbrite       │
│   Civitatis · TripAdvisor  (+ scraped sources)           │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│             PHASE 1 — Ingestion Pipeline                  │
│                                                          │
│  ingestion.yaml  →  PipelineFactory                      │
│       ↓                                                  │
│  APIAdapter / ScraperAdapter                             │
│       ↓                                                  │
│  Normalization (field_mapper · location · currency · tax)│
│       ↓                                                  │
│  Deduplication (exact match by source_event_id)          │
│       ↓                                                  │
│  PostgreSQL 16 (port 5433)                               │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│             PHASE 2 — Agent Enrichment Chain              │
│                                                          │
│  MCP Layer  (local mode — in-process FastMCP)            │
│       ↓                                                  │
│  [1] FeatureAlignmentAgent   → event_type, tags          │
│  [2] TaxonomyClassifierAgent → category, dimensions      │
│  [3] EmotionMapperAgent      → vibe, energy, cost        │
│  [4] DataQualityAgent        → quality_score             │
│  [5] DeduplicationAgent      → fuzzy dedup               │
│                                                          │
│  LLM: Ollama llama3.2:3b (default) · Claude · GPT       │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                   Enriched Event Store                    │
│             PostgreSQL  ·  FastAPI REST layer             │
└──────────────────────────────────────────────────────────┘
```

---

## Running Locally

**1. Start PostgreSQL**
```bash
cd infra/postgres
docker compose up -d
# Runs on port 5433
```

**2. Set up the Python environment**
```bash
cd services/api
uv venv
uv sync
source .venv/bin/activate
```

**3. Install Ollama (default LLM provider)**
```bash
brew install ollama && ollama pull llama3.2:3b
# Ollama starts automatically on port 11434 — no API key needed
```

**4. Run ingestion**
```python
from src.ingestion.factory import PipelineFactory

factory = PipelineFactory("src/configs/ingestion.yaml")
pipeline = factory.create("getyourguide")
result = await pipeline.execute()
```

**5. Run agent enrichment**
```python
from src.agents.orchestration.pipeline_triggers import load_agents_config, PostIngestionTrigger

agents_config = load_agents_config()
trigger = PostIngestionTrigger(agents_config)
enrichment_result = await trigger.on_pipeline_complete(result)
```

---

## Where to Go Next

| I want to...                            | Go to                  |
|-----------------------------------------|------------------------|
| Add or configure an ingestion source    | `INGESTION_GUIDE.md`   |
| Understand the agent enrichment system  | `AGENT_ARCHITECTURE.md`|
| See the full doc index                  | `DESIGN_INDEX.md`      |
| Read the strategic roadmap              | `ROADMAP.md`           |
| Browse ingestion config                 | `services/api/src/configs/ingestion.yaml` |
| Browse agent config                     | `services/api/src/configs/agents.yaml`    |
