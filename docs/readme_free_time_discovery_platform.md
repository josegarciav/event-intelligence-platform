# Free-Time Discovery Platform (Working Title: **Atlas of Experiences**)

> **One-line:** *Spotify + Google Maps + a life coach — but for your free time.*

A universal platform that helps anyone find the best thing to do in their free time — **right now** — by continuously collecting events and experiences from the web and generating **real-time, hyper-personalized recommendations** based on taste, context, and constraints.

---

## Table of Contents

- [Vision](#vision)
- [What Makes This Different](#what-makes-this-different)
- [Core Concepts](#core-concepts)
- [Key User Flows](#key-user-flows)
- [Product Features](#product-features)
- [Personalization Engine](#personalization-engine)
- [Data Ingestion & Scraping](#data-ingestion--scraping)
- [Experience Taxonomy](#experience-taxonomy)
- [System Architecture](#system-architecture)
- [Data Model](#data-model)
- [Roadmap](#roadmap)
- [Monetization (Humane by Design)](#monetization-humane-by-design)
- [Creative Extensions](#creative-extensions)
- [Ethics, Safety, Privacy](#ethics-safety-privacy)
- [Repo Structure (Suggested)](#repo-structure-suggested)
- [Getting Started](#getting-started)
- [Contributing](#contributing)

---

## Vision

Most people have free time… and still don’t know what to do.

- Existing event platforms are fragmented (concerts here, workshops there, nature elsewhere).
- Recommendations are generic and disconnected from context (time, mood, energy, budget).
- People default to scrolling or doing nothing, not because they want to — but because discovery is hard.

**This platform answers a single question extremely well:**

> **“Given who I am, where I am, and the time I have — what is the best thing I can do *now*?”**

It is not just an event listing site.
It is a **real-time experience recommender**, grounded in a **human experience taxonomy**, continuously updated by automated web collection.

---

## What Makes This Different

### ✅ Experience-first (not event-first)
We don’t only recommend ticketed events.
We recommend *experiences* — including:
- local happenings
- online sessions
- self-guided activities
- micro-adventures
- restorative ideas
- creative challenges
- social connection opportunities

### ✅ Contextual intelligence
Recommendations adapt to:
- time available (15 min, 1h, half-day)
- location / mobility
- budget
- weather
- energy level
- mood
- social setting (solo/couple/friends/family)
- desired “vibe” (calm, playful, intense, meaningful, etc.)

### ✅ Taxonomy as a competitive moat
The taxonomy is a **semantic scaffold** that:
- normalizes messy web data
- helps cold-start personalization
- creates explainability (“why this is recommended”)
- enables discovery beyond trending/popularity

---

## Core Concepts

### 1) The Experience Graph
A continuously updated knowledge layer where every experience is:
- normalized
- deduplicated
- enriched
- mapped to taxonomy nodes

### 2) The Personal Experience Profile
Not just interests.
A dynamic model combining:
- long-term preferences (personality, tastes)
- short-term context (time, energy, mood)
- behavioral learning (what the user actually does)

### 3) Real-Time Recommendation
Generate ranked suggestions that are:
- feasible now
- aligned with user state
- diverse (avoid monotony)
- explainable

---

## Key User Flows

### Flow A — Instant Mode (default)
1. User opens app
2. App auto-detects context (time window, location, weather)
3. User selects *state* (optional): energy + mood + vibe
4. App returns top 5 suggestions with “why this fits”

### Flow B — Explore Mode
1. User browses taxonomy categories
2. Filters by vibe, time, budget, distance
3. Saves experiences or plans a day

### Flow C — “Surprise Me” (intentional novelty)
1. User chooses a risk level (safe / medium / spicy)
2. App proposes a novel experience still compatible with constraints

### Flow D — Offline / No-events Mode
If there are no strong events nearby, the platform generates **activity alternatives** (microtasks, self-guided experiences) from the taxonomy.

---

## Product Features

### Discovery
- **Now / Tonight / Weekend** tabs
- map + list view
- filters: time, distance, price, vibe, intensity
- “best with friends” & “best solo” toggles

### Planning
- save to collections (“date ideas”, “low energy”, “creative”)
- smart itinerary builder (2h–1 day)
- calendar export

### Social Layer (optional)
- invite friends, propose options, vote
- “sync your free time” (availability windows)
- group recommendations (optimize for group intersection)

### Trust & Explainability
- “Recommended because…” card
- transparent constraints (“fits 45 min, low cost, indoors, 2km away”)

---

## Personalization Engine

### Signals
- explicit: likes/dislikes, vibe preference, budget range
- implicit: clicks, saves, completions, dwell time
- contextual: time, location, weather, weekday/weekend

### Ranking Objectives
- relevance (taste match)
- feasibility (constraints)
- diversity (avoid same category repeatedly)
- novelty (controlled exploration)
- wellbeing balance (not always high dopamine)

### Simple baseline (MVP)
- taxonomy + rule-based scoring + collaborative filtering later

### Advanced (V2+)
- embeddings for experience text + taxonomy nodes
- multi-objective ranking
- reinforcement learning (with safety constraints)

---

## Data Ingestion & Scraping

### Sources (examples)
- official festival/event sites
- venues and cultural institutions
- community calendars
- meetup-style platforms
- universities, NGOs, sports federations
- ticketing sites
- RSS feeds

### Pipeline Steps
1. **Discovery** (seed URLs + sitemaps + search)
2. **Extraction** (scrape HTML, JSON-LD, iCal)
3. **Normalization** (title, date, location, price)
4. **Deduplication** (hashing + similarity)
5. **Classification** (map to taxonomy nodes)
6. **Enrichment**
   - vibe/intensity
   - accessibility
   - duration estimate
   - required equipment
   - indoor/outdoor
7. **Storage** (events DB + embeddings + graph)
8. **Monitoring** (broken sources, drift)

### Scraping Principles
- respect robots.txt where required
- use caching, rate limiting
- prefer APIs/feeds when available
- keep transparent source attribution

---

## Experience Taxonomy

The taxonomy covers **everything humans do** in their free time:

1. **Play & Pure Fun**
2. **Exploration & Adventure**
3. **Creation & Expression**
4. **Learning & Intellectual Pleasure**
5. **Social Connection & Belonging**
6. **Body, Movement & Physical Experience**
7. **Challenge, Competence & Achievement**
8. **Relaxation & Escapism**
9. **Identity, Meaning & Self-Discovery**
10. **Contribution & Impact**

Each activity node can have metadata like:
- vibe tags (calm / intense / social / introspective…)
- constraints (budget, location, equipment)
- context fit (night/day, indoor/outdoor)
- skill level

---

## System Architecture

### High level
- **Ingestion Layer**: scrapers, APIs, feeds
- **Processing Layer**: normalize, dedupe, classify, enrich
- **Storage Layer**:
  - relational DB for events
  - vector DB for semantic search
  - graph DB for taxonomy + relationships
- **Serving Layer**:
  - recommendation API
  - search API
  - realtime context service
- **Clients**:
  - web app
  - mobile app
  - “assistant mode” (chat interface)

### Suggested tech (flexible)
- ingestion: Playwright/Selenium + async workers
- processing: Python + LLM-assisted extraction (guardrailed)
- embeddings: open source or hosted
- storage: Postgres + pgvector, or dedicated vector DB
- graph: Neo4j / RDF store (optional)
- orchestration: Airflow / Prefect

---

## Data Model

### `Event`
- id
- title
- description
- start_time / end_time
- location (geo)
- online_url
- price_range
- organizer
- source_url
- raw_source_payload

### `ExperienceTag`
- taxonomy_path
- vibe_tags
- intensity_score
- social_score
- novelty_score
- accessibility_tags

### `UserContext`
- time_window
- location
- mobility
- weather
- mood
- energy
- budget

### `Recommendation`
- event_id
- score
- reasons[]
- constraints_matched

---

## Roadmap

### Phase 0 — Proof of Concept
- taxonomy finalized
- scrape 50–200 sources
- normalize + dedupe
- basic browsing + filters

### Phase 1 — MVP
- instant recommendations (rule-based)
- onboarding taste quiz
- save/share

### Phase 2 — Personalization
- user profiling
- implicit feedback loop
- embeddings-based similarity

### Phase 3 — Real-time Intelligence
- live context adaptation
- group recommendations
- “no-events fallback” generator

### Phase 4 — Ecosystem
- organizer portal
- city partnerships
- public API

---

## Monetization (Humane by Design)

- affiliate on ticketed events (opt-in, transparent)
- premium personalization (advanced planning, family modes)
- B2B dashboards for venues/cities (aggregate insights)
- “experience subscriptions” (curated monthly packs)

**Avoid:** attention-farming, infinite scroll addiction loops.

---

## Creative Extensions

### 🧠 1) Mood-to-Experience Translator
User types: *“I feel empty but restless”* → app suggests experiences that match that emotional state.

### 🎲 2) Experience Roulette
A playful slot-machine UI with a “safety slider” (safe → spicy). Novelty with boundaries.

### 🧭 3) Micro-Adventures Generator
Auto-create a 90-minute mission:
- 3 stops
- 1 challenge
- 1 sensory moment
- 1 social micro-interaction

### 🧪 4) Personal Experiment Mode
Run small life experiments:
- “Try 3 new social experiences this week”
- “Replace scrolling with 10-min curiosity sessions”
Tracks outcomes (mood before/after).

### 🧩 5) Experience Building Blocks
Users can compose activities like Lego:
- “walk + photo challenge + coffee + journal prompt”
Shareable templates.

### 🏙️ 6) City Experience Index
Cities get an “experience diversity score” and maps of under-served categories.

### 🤝 7) Friendship Engine
Suggest experiences designed to create *real bonds*:
- structured conversation walks
- co-creation workshops
- volunteering micro-teams

### 🧘 8) Anti-Burnout Autopilot
Detects overload patterns and recommends recovery experiences before crash.

### 🧬 9) Taste DNA (Experience Genome)
A radar chart of user’s experience balance:
- social vs solo
- intense vs calm
- novelty vs routine
- mind vs body

### 🎭 10) “Second Life” Mode (Escapism)
Curated immersive experiences:
- escape rooms
- immersive theatre
- roleplay dinners
- VR experiences

---

## Ethics, Safety, Privacy

- minimal data collection (only what improves recommendations)
- private-by-default profile
- explainable recommendations
- content filtering and safety constraints
- no selling of sensitive personal data

---

## Repo Structure (Suggested)

```
/ingestion
  /scrapers
  /connectors
  /feeds
/processing
  /normalization
  /dedupe
  /classification
  /enrichment
/recommendation
  /ranking
  /user_profiles
  /context_engine
/api
  /routes
  /auth
/web
  /frontend
/docs
  TAXONOMY.md
  SOURCES.md
  ARCHITECTURE.md
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node 18+ (if running web client)
- (Optional) Postgres + pgvector

### Quick Start (placeholder)
1. Clone repo
2. Configure `.env`
3. Run ingestion workers
4. Run API
5. Start web client

---

## Contributing

Contributions welcome:
- new sources connectors
- taxonomy improvements
- enrichment heuristics
- UI/UX enhancements
- evaluation datasets
