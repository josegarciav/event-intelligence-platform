
# Pulsecity

## Event Intelligence Platform

A scalable data platform for ingesting, normalizing, and analyzing event data from multiple heterogeneous sources.  
The system transforms raw event signals into a canonical, city-aware dataset designed for analytics, experimentation, and machine-learning-driven discovery.  
Built with extensibility in mind, the platform supports rapid onboarding of new sources, cities, and downstream use cases.  
At its core, events are treated as data products, not just listings.


## Repo Structure

A modular event intelligence platform that separates data ingestion, core intelligence, and application logic, with experimentation treated as a first-class, admin-driven system.


```text
event-intelligence-platform/
│
├── ingestion/
│   ├── sources/
│   └── pipelines.py
│
├── normalization/
│   ├── schema.py
│   └── enrich.py
│
├── storage/
│   ├── raw/
│   ├── clean/
│   └── features/
│
├── intelligence/
│   ├── metrics/
│   ├── allocation/
│   └── models/
│
├── app/
│   ├── api/
│   ├── admin/
│   │   ├── experiments/
│   │   ├── metrics/
│   │   └── dashboards/
│   └── public/
│
├── configs/
│   └── settings.yaml
│
├── scripts/
│
├── tests/
│   ├── integration/
│   ├── unit/
│
├── docs/
│
├── pyproject.toml
├── uv.lock
└── README.md
```


## High-Level Architecture


```code

┌───────────────────┐
│  External Sources │
│───────────────────│
│ Meetup            │
│ Facebook / Ads    │
│ Ticketing APIs    │
│ Cultural Feeds    │
│ Scraped Sources   │
└─────────┬─────────┘
          │
          ▼
┌──────────────────────────┐
│ Ingestion Layer          │
│──────────────────────────│
│ - API collectors         │
│ - Scrapers               │
│ - Scheduled jobs         │
│ - Webhooks (future)      │
└─────────┬────────────────┘
          │
          ▼
┌───────────────────────────┐
│ Normalization & Enrichment│
│───────────────────────────│
│ - Canonical event schema  │
│ - City & geo resolution   │
│ - Category taxonomy       │
│ - Price & time parsing    │
└─────────┬─────────────────┘
          │
          ▼
┌──────────────────────────┐
│ Storage & Feature Layer  │
│──────────────────────────│
│ - Raw data lake          │
│ - Clean event tables     │
│ - Feature-ready datasets │
└─────────┬────────────────┘
          │
          ▼
┌───────────────────────────┐
│ Analytics & ML Layer      │
│───────────────────────────│
│ - Dashboards & metrics    │
│ - Experimentation platform│
│ - Recommender systems     │
│ - Pricing models          │
└─────────┬─────────────────┘
          │
          ▼
┌──────────────────────────┐
│ Application Layer        │
│──────────────────────────│
│ - Event discovery app    │
│ - Filters & preferences  │
│ - User feedback signals  │
└──────────────────────────┘
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

# Activate it
source .venv/bin/activate

# Sync your dependencies
uv sync
uv lock
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
