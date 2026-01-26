
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
│   └── run_pipeline.py
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


## Environment Setup


This project uses **uv** for fast, deterministic Python dependency management.


### Prerequisites
- Python 3.11+
- uv installed (https://github.com/astral-sh/uv)


### Setup
Clone the repository, create a virtual environment named `pulsecity`, and install all dependencies:


```bash
uv venv pulsecity
uv sync --venv pulsecity

source pulsecity/bin/activate
```

## Contribution Guidelines

This repository **strictly enforces the Conventional Commits specification**.  
All contributions must follow this format to ensure consistent changelogs, versioning, and collaboration.

Examples:
- `feat: add meetup ingestion pipeline`
- `fix: correct timezone parsing for events`
- `refactor: normalize city resolution logic`

Documentation: https://www.conventionalcommits.org/



