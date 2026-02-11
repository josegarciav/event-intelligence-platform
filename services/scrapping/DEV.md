# Developer Guide (internal)

This document is for contributors building and maintaining the **Scrapping** (scraping) library as a shared team repo.

It is intentionally **implementation-oriented**: repo design, collaboration rules, extension patterns, and what we can reuse / improve from the existing codebase and diagrams.

---

## 0) Context: what we already have (assets you shared)

We already have a solid starting point:

### A) Config-driven multi-site job scraper (baseline)

* JSON config that defines each site: `base_url`, pagination behavior, regex patterns for job URLs, captcha/robots, timeouts, SSL, etc.
* Orchestrator that loops sites → pages → extracts job URLs → fetches job pages in parallel → saves results to parquet (snappy).
* Optional Prometheus metrics + statistics printing.

### B) Advanced anti-bot “browser flow” patterns

* A browser-based scraper with:

  * **Human-like behavior** utilities (scroll/mouse drift/micro-delays)
  * **Brave** browser detection helpers (multi-OS)
  * Operational resilience patterns (restart conditions, UI/inspector toggles)

### C) Post-processing / QA cleanup pipeline

* Processing of parquet outputs using:

  * `trafilatura` extraction (HTML → structured JSON with metadata)
  * token count heuristics
  * zero-shot classification to detect error/expired pages and filter them out

### D) Architecture diagrams

* Excalidraw designs covering:

  * pipeline components (config → orchestrator → extraction → processing → storage → monitoring)
  * scheduling ideas (cron / Prefect DAG / pm2)
  * config knobs (regex, UA, proxies, captcha, click/scroll/popup)
  * trade scraping variants (keywords/country/limit products + stealth browser stack)

The goal of the new repo is to **productize** these ideas into a stable, scalable library.

---

## 1) North star principles

1. **Config-first**: adding a source should not require new Python code most of the time.
2. **Engines are plugins**: HTTP / Browser / Hybrid are interchangeable.
3. **Every run is reproducible**: we save raw pages + metadata so issues are replayable.
4. **Observability is not optional**: metrics, logs, run summaries by default.
5. **Testing is mandatory**: golden HTML fixtures + extractor unit tests.
6. **Safe evolution**: configs are versioned; we keep backward compatibility.

---

## 2) Repo design (recommended structure)

```text
scrapping-lib/
  pyproject.toml
  requirements.txt
  README.md

  scrapping/
    cli.py                  # `scrap run` / `scrap validate` / `scrap doctor`
    orchestrator.py         # loads configs, schedules work, aggregates results
    config/
      schema.py             # pydantic models + jsonschema export
      loader.py             # load/merge/validate configs
      migration.py          # config version upgrades

    engines/
      base.py               # Engine interface
      http.py               # requests + retries + rate-limit
      browser.py            # seleniumbase/playwright wrapper
      hybrid.py             # http discovery + browser details

    actions/
      browser_actions.py    # scroll/click/wait/close-popup/type/hover
      human_like.py         # delay, mouse drift, scroll utilities

    extraction/
      link_extractors.py    # regex/css/xpath strategies
      parsers.py            # bs4/lxml/trafilatura helpers
      transforms.py         # normalize fields

    pipeline/
      stages.py             # discover/fetch/parse/validate/dedupe/persist
      validators.py         # schema + business rules
      dedupe.py             # url normalize + fingerprints + state store

    storage/
      writers.py            # parquet/jsonl/db drivers
      layouts.py            # folder structure conventions

    monitoring/
      logging.py            # structured logs
      metrics.py            # prometheus metrics
      reporting.py          # run summary tables

    processing/
      html_to_structured.py # trafilatura extraction
      quality_filters.py    # token filters, error detection
      classifiers.py        # optional HF pipelines

    scheduling/
      prefect_flows.py      # optional, if used
      cron_templates/       # examples

    ai/
      config_agent.py       # auto-config generation (roadmap)
      tests_agent.py        # auto-tests + fixtures (roadmap)

  configs/
    v1/
      job_portals/
      ecommerce/

  tests/
    unit/
    golden/
    fixtures/

  docs/
    ARCHITECTURE.md
    CONFIG_SPEC.md
    ANTI_BOT_PLAYBOOK.md
    RUNBOOK.md
```

### Why this structure

* Keeps core stable modules isolated from changing sources.
* Makes it easy to distribute tasks across developers (engines, extraction, storage, processing, observability).
* Encourages a clean contract: **config → pipeline → output**.

---

## 3) Collaboration model (team workflow)

### Branching + PR rules

* Branch naming: `feature/<topic>`, `fix/<topic>`, `source/<site_id>`
* Every PR must include:

  1. one of: a new source config OR a core feature change
  2. tests (unit or golden)
  3. updated docs if behavior changes

### Code ownership

* `scrapping/engines/**` owned by Runtime subgroup
* `scrapping/extraction/**` owned by Extraction subgroup
* `scrapping/storage/**` owned by Data contract subgroup
* `configs/**` owned by the whole team, but PR review required

### Definition of done (DoD)

For a **new site**:

* Config created + validated
* At least 1 golden HTML fixture committed
* Extractor test passes on fixture
* Dedupe keys chosen and documented
* Storage layout verified
* Run summary shows sane stats

For a **core change**:

* No breaking config change (or add migration)
* Updated schema version
* Regression test added

---

## 4) What we reuse from the current codebase

### A) Job scraping orchestrator patterns

Reuse:

* Multi-threaded detail fetching (ThreadPool)
* Pagination rules from config:

  * sequential pages
  * unsequential pages via `start`/`step_page`
  * optional `rest_of_url`
* Per-site stats tracking and end-of-run reporting
* Parquet outputs (snappy)
* Prometheus integration toggled by CLI

Refactor targets:

* Extract config parsing into pydantic models
* Separate “page fetch” from “detail fetch” stage implementations
* Centralize retry policies, timeouts, ssl behavior

### B) Anti-bot / browser utilities

Reuse:

* Human delay + micro delay
* scroll utilities + “scroll to element”
* mouse move + drift
* browser detection helpers (Brave)

Refactor targets:

* Turn these into reusable `BrowserAction` primitives
* Make actions declarative in config, not code

### C) Post-processing and data QA

Reuse:

* `trafilatura` extraction to build structured JSON
* Token-based filtering to detect low-content pages
* Zero-shot classifier hook to flag error/expired pages

Refactor targets:

* Make processing a **stage** with its own config section
* Avoid hardcoding input/output folders
* Make classifier optional + cached

---

## 5) Pipeline architecture (developer-level)

### 5.1 Stage definitions

We implement stages as pure, testable functions:

1. `discover_pages(source)` → yields listing page URLs
2. `fetch_page(url)` → returns (url, html, headers, status, timings)
3. `extract_links(listing_html)` → yields detail URLs
4. `fetch_details(urls)` → returns detail pages
5. `parse_item(detail_html)` → returns structured dict
6. `validate_item(item)` → passes/fails with reasons
7. `dedupe(items)` → removes duplicates based on config rules
8. `persist(raw_pages, items, run_meta)`
9. `report(metrics, stats)`

Each stage produces artifacts that can be saved for replay.

### 5.2 Engine interface

Define a stable engine interface:

* `get(url, *, headers, cookies, timeout, verify_ssl, proxy, session)`
* `get_rendered(url, *, actions, wait_for, headless, stealth)`
* `close()`

Engines must return:

* `response_text`
* status code / exceptions
* final URL after redirects
* timing info

### 5.3 Concurrency model

* Listing pages: low concurrency, steady pacing.
* Detail pages: high concurrency (bounded) with jitter.
* Browser engine: limited parallelism per machine, pool-based.

We standardize:

* global `max_workers`
* per-source concurrency override
* per-engine concurrency cap

---

## 6) Config specification (dev contract)

### 6.1 Config versioning

All configs include:

* `config_version`: e.g. `1.0`
* `source_id`
* `enabled`

We maintain migrations in `scrapping/config/migration.py`.

### 6.2 Core source keys (based on current config usage)

From existing job configs we already support:

* `base_url`
* `max_pages`
* `pattern` (regex)
* `identifier`
* `robots`
* `recaptcha`
* `timeout`
* `ssl`
* `unsequential` + `step_page`
* `rest_of_url`
* `action_scrolling`, `action_click`, `action_close_popup`
* `show_ui`, `use_inspector`

We should normalize these into sections:

```json
{
  "source_id": "linkedin",
  "config_version": "1.0",
  "schedule": {"frequency": "2h", "priority": 5},
  "entrypoints": [{"url": "...start={page}", "paging": {"mode": "offset", "start": 0, "step": 10, "pages": 20}}],
  "engine": {"type": "http", "timeout_s": 15, "verify_ssl": false},
  "anti_bot": {"recaptcha": true, "robots": false},
  "discovery": {"link_extract": {"method": "regex", "pattern": "jobs/view/..."}},
  "storage": {"items": {"format": "parquet", "compression": "snappy"}}
}
```

### 6.3 Browser action DSL

We encode human-like behavior as declarative actions:

```json
"actions": [
  {"type": "close_popup", "selector": "button.close"},
  {"type": "scroll", "mode": "random", "min_px": 200, "max_px": 450, "repeat": 6},
  {"type": "click", "selector": "button.load-more", "repeat": 2},
  {"type": "wait_for", "selector": ".results", "timeout_s": 10}
]
```

This is where we reuse the current `human_scroll_down`, `human_mouse_drift`, etc.

### 6.4 Storage contract

We standardize outputs:

* `raw_pages`: listing pages (url, html, status, fetched_at, headers, run_id)
* `raw_items`: detail pages (url, html, ...)
* `items`: parsed structured items
* `run_report`: JSON summary (counts, failures, durations)

Preferred formats:

* parquet for large tables
* jsonl for streaming
* optional DB connectors

---

## 7) Observability (built-in)

### Metrics

We keep the proven Prometheus metrics pattern and extend:

* pages attempted/succeeded
* items found/scraped
* errors by type
* average latency by engine
* queue sizes (if any)

### Logging

* JSON logs with `run_id`, `source_id`, `stage`, `url`, `error_type`
* One log file per run + per source

### Run reporting

At end of run:

* summary table like the current statistics printout
* plus:

  * p50/p95 timings
  * top error reasons
  * dedupe counts

---

## 8) Testing (how we stop regressions)

### 8.1 Unit tests

* URL normalization
* regex/link extraction
* config validation and migration
* dedupe fingerprints

### 8.2 Golden tests (recommended default)

* Store minimal HTML samples in `tests/fixtures/<source_id>/...html`
* Test that extraction returns expected links/items

### 8.3 Smoke tests

CI job that runs:

* config validation for all configs
* 1-page dry-run per source (optional / rate-limited)

---

## 9) Performance + stability guidelines

### Rate limiting

* Respect per-source RPS, delays, jitter
* Adaptive backoff on 429/503

### Memory management

Browser scraping is fragile over long runs.
We support:

* checkpointing state (last page, last category)
* browser restart policies (e.g. after N pages or on memory threshold)

### Deduplication and caching

* normalize URLs to avoid duplicates due to tracking params
* persist state store (sqlite/redis) to avoid re-scraping same items

---

## 10) Processing / QA pipeline (from current `analyze.py`)

We treat QA as a first-class optional stage:

* Extract structured content from raw HTML with `trafilatura`
* Compute token counts on extracted text
* Filter suspicious pages (too short, missing title)
* Optionally classify pages (job_posting vs error/expired)

Important design:

* QA must not be “hardcoded paths”. It should operate on a given run output.
* Classifier should be optional (can be slow / requires model download).
* Cache model + allow offline mode.

---

## 11) Scheduling and deployment

We support multiple execution modes:

1. **Local dev**: manual CLI runs
2. **Cron**: simple scheduled runs per config group
3. **Prefect**: DAG orchestration for retries and visibility
4. **pm2**: long-running worker supervisor

We standardize a run entrypoint:

```bash
scrap run --configs configs/v1/job_portals/*.json --output results/
```

And we store `run_meta.json` so downstream pipelines can pick up outputs.

---

## 12) Extending the library

### Add a new extractor strategy

1. implement in `extraction/link_extractors.py`
2. register the strategy name
3. add unit test and fixture

### Add a new storage backend

1. implement writer in `storage/writers.py`
2. support config-driven credentials
3. add contract test (roundtrip)

### Add a new engine capability

* Prefer to add it as optional features (stealth mode, proxy pools, etc.)
* Keep the `Engine` interface stable

---

## 13) AI-assisted config generation (developer roadmap)

We want a **ConfigAgent** that takes a URL/domain and produces:

* draft config
* fixtures
* tests
* a “confidence score”

### Proposed internal flow

1. **Probe**: fetch headers, detect redirects, detect WAF/captcha hints
2. **Discover**: attempt to find listing patterns + pagination
3. **Extract**: sample pages → infer selectors/regex
4. **Validate**: run extraction on 1–2 pages
5. **Write**: save config + fixtures + tests
6. **Iterate**: if test fails, refine patterns

### What agents can realistically automate

* building strong regex patterns for URLs
* generating robust CSS selectors from DOM
* producing initial browser actions sequences
* authoring golden tests based on extracted outputs

### Guardrails

* Never bypass access restrictions that violate legal/robots policy.
* Always store the agent’s assumptions in the generated report.

---

## 14) Runbook (when a site breaks)

1. Check run report: error types + status codes
2. Compare saved raw pages vs last working fixture
3. Try config-only fixes first:

   * selector/regex updates
   * pagination tweak
   * rate limit tweak
4. Upgrade engine only if necessary:

   * HTTP → Hybrid
   * Hybrid → Browser
5. Add/refresh fixtures + tests
6. Post-mortem note in PR description

---

## 15) What we gain as a team

* Faster onboarding: contributors add sources by config, not rewriting scripts.
* Consistent outputs: downstream analytics/ML don’t break per site.
* Reliability: failures are visible (metrics/logs), replayable (raw HTML saved).
* Scalability: concurrency and scheduling are standardized.
* Longevity: when the web changes, we patch configs and action DSL, not entire codebases.

---

## Appendix: recommended contribution checklist

**New source PR checklist**

* [ ] config validated
* [ ] fixture added
* [ ] extractor test added
* [ ] dedupe keys chosen
* [ ] storage paths confirmed
* [ ] run report screenshot / summary in PR

**Core change PR checklist**

* [ ] backward compatible or migration included
* [ ] unit tests updated
* [ ] docs updated
* [ ] version bump if needed
