# Design Index — Pulsecity Event Intelligence Platform

---

## Quick Navigation

| I want to...                                  | Go to                   |
|-----------------------------------------------|-------------------------|
| Get oriented in the codebase (5 min)          | `START_HERE.md`         |
| Add or configure an ingestion source          | `INGESTION_GUIDE.md`    |
| Understand the LLM agent enrichment system    | `AGENT_ARCHITECTURE.md` |
| Read the strategic and technical roadmap      | `ROADMAP.md`            |
| See the product vision doc                    | `readme_free_time_discovery_platform.md` |

---

## Doc Inventory

| File                                    | Status   | Description                                              |
|-----------------------------------------|----------|----------------------------------------------------------|
| `START_HERE.md`                         | Current  | 5-minute monorepo orientation, local run instructions    |
| `INGESTION_GUIDE.md`                    | Current  | Config-driven ingestion: sources, factory, normalization |
| `AGENT_ARCHITECTURE.md`                 | Current  | MCP agent chain: how enrichment works end-to-end         |
| `ROADMAP.md`                            | Current  | Strategic vision, agent architecture, expansion ideas    |
| `DESIGN_INDEX.md`                       | Current  | This file — navigation index                             |
| `readme_free_time_discovery_platform.md`| Preserved| Original product vision document                         |

---

## Architecture in One Diagram

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
