
# Pulsecity

## Event Intelligence Platform

A scalable data platform for ingesting, normalizing, and analyzing event data from multiple heterogeneous sources.
The system transforms raw event signals into a canonical, city-aware dataset designed for analytics, experimentation, and machine-learning-driven discovery.
Built with extensibility in mind, the platform supports rapid onboarding of new sources, cities, and downstream use cases.
At its core, events are treated as data products, not just listings.


## Repo Structure

Turbo monorepo — apps, backend services, and shared packages are developed independently and composed at the CI/CD layer.

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


## High-Level Architecture

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
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                    Application Layer                      │
│     Landing (live)  ·  Web app (planned)  ·  Mobile      │
└──────────────────────────────────────────────────────────┘
```

## Roadmap (Initial Phases)

1. **Foundations** — Define canonical event schema, city resolution, and category taxonomy.
2. **Ingestion** — Build reliable pipelines for initial sources with scheduling and monitoring.
3. **Normalization** — Standardize dates, locations, prices, and categories; track data quality.
4. **Analytics** — Expose core metrics and instrument user interaction signals.
5. **Experimentation** — Prepare A/B testing framework and baseline recommendation logic.

### Brainstorming

- It'd be nice to be able to get the artist name (assuming musical artist) and fetch some popular music sample from their SoundCloud page, so that users can get a feel of what the artist feels like.



## Environment Setup


This project uses **uv** for fast, deterministic Python dependency management.


### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Fast Python package manager)

```bash
# uv installation guidelines
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

Should output `uv 0.9.26`.

### Setup
This project is pinned to **Python 3.11**. Run the following to set up your local environment:

```bash
# Force uv to use Python 3.11 and create the .venv
uv venv --python 3.11

# change wd
cd services/api
uv venv
uv sync

# Activate it
source services/api/.venv/bin/activate

# Sync your dependencies
uv sync
uv lock
```


Running pre-commit:

```bash
uv run pre-commit run --all-files --unsafe-fixes
```

Opening Claude
```bash
claude --dangerously-skip-permissions
```

## Contribution Guidelines

This repository **strictly enforces the Conventional Commits specification**.
All contributions must follow this format to ensure consistent changelogs, versioning, and collaboration.

Examples:
- `feat: add meetup ingestion pipeline`
- `fix: correct timezone parsing for events`
- `refactor: normalize city resolution logic`

Documentation: https://www.conventionalcommits.org/


## Scaling Toward Mobile + Web

1. API-first design
    - Make all backend functionality accessible via REST or GraphQL
    - Version your API from day 1

2. Modular packaging
    - Keep backend logic in modules that are independent of the frontend
    - This makes it reusable for web, mobile, or even other clients (IoT, partners)

3. CI/CD branching
    - You can create separate workflows for backend, web frontend, mobile frontend
    - Your current PR quality checks form the core for backend reliability


## Python-Native Architecture & Design Patterns

This project is structured with clear separation of concerns and Python-first design, enabling future web and mobile clients without touching backend logic.

### Layers

**Backend / Ingestion & Normalization**
- FastAPI + SQLAlchemy + Pydantic
- Handles data ingestion from multiple sources, normalization, enrichment, and storage.

**Analytics / ML Layer**
- FastAPI endpoints, Celery or Prefect pipelines, Jupyter dashboards
- Exposes analytics, recommendation, and experimentation services.

**Application Layer**
- Web app → Django, Flask + Jinja, or FastAPI + HTMX
- Mobile app → REST/GraphQL endpoints consumed by native SDKs or Flutter/Dart
- Frontend is fully decoupled, consuming the same API-first backend.

### Design Patterns

**Adapter Pattern**
- Used at the **pipeline-source level** to standardize diverse event sources (Meetup, Facebook, Ticketing APIs) into a **canonical event schema**.
- Each source implements a common interface, allowing the ingestion layer to treat all sources uniformly.

**Other To-Be-Used Patterns**
- **Factory Pattern** → dynamically create ingestion pipelines or ML model objects depending on event type or client requirements.
- **Observer / Pub-Sub** → track event updates and trigger downstream analytics or experimentation pipelines asynchronously.
- **Strategy Pattern** → enable dynamic pricing or recommendation strategies in the analytics layer without changing the core logic.
- **Singleton Pattern** → for global configuration, logging, or experiment registry within the system.

### Best Practices

- **FastAPI** for API-first design ensures all clients (web, mobile, CLI) can consume the backend consistently.
- **Pydantic models** enforce schema consistency across layers.
- **Docker** containerization ensures reproducible environments for backend and CI/CD.
- **Adapters at source-level** keep the system flexible to add/remove event sources without impacting the pipeline logic.
