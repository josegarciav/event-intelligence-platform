# Scrapping Library — Architecture

This repo is a config-driven scraping library designed to be:
- **Extensible**: new sites and new scraping challenges should require config changes and small plug-ins, not rewrites.
- **Reliable**: robust retries, rate-limits, validation, dedupe, QA, and reporting.
- **Collaborative**: predictable repo structure + conventions so a whole team can contribute without stepping on each other.

---

## 1) High-level concept

The system is built around this loop:

1. **Load config** (one source or a list of sources).
2. **Schedule** each source run (frequency/policy is config-driven).
3. **Run pipeline**:
   - build listing URLs (entrypoints + paging)
   - fetch listing pages (HTTP or browser)
   - extract links
   - fetch detail pages
   - convert HTML → structured text
   - apply QA rules + validators
   - dedupe
4. **Persist outputs** (raw pages, links, items, reports).
5. **Emit monitoring artifacts** (logs, metrics, run reports).

Everything above is deterministic and auditable:
- raw pages are saved
- extracted links are saved
- valid + dropped items are saved
- run report summarizes what happened

---

## 2) Repository modules

### Config
`scrapping/config/`
- `schema.py`: typed schema / validation model for configs.
- `loader.py`: read JSON (single or list), validate, normalize defaults.
- `migration.py`: migrate older config versions to current.

### Engines (fetchers)
`scrapping/engines/`
- `base.py`: common response types + rate limit + retry helpers.
- `http.py`: requests-based engine.
- `browser.py`: Playwright-based rendering engine + action DSL execution.
- `hybrid.py`: combination (e.g., list via HTTP, details via browser).

### Actions (browser interaction)
`scrapping/actions/`
- `human_like.py`: pacing utilities (scroll, delay, typing, drift).
- `browser_actions.py`: declarative action runner (click/scroll/wait/type/etc.).

### Extraction
`scrapping/extraction/`
- `link_extractors.py`: extract links using regex / CSS / XPath, normalize URLs.
- `parsers.py`: HTML → text primitives (bs4/lxml) + optional trafilatura support.
- `transforms.py`: normalization utilities (canonical URL, casting, date parsing hooks).

### Pipeline
`scrapping/pipeline/`
- `stages.py`: discover → fetch → extract → parse → validate → dedupe pipeline.
- `validators.py`: field-level validation rules (errors vs warnings).
- `dedupe.py`: URL and content fingerprint dedupe with a store interface.

### Storage
`scrapping/storage/`
- `layouts.py`: stable output folder layout and naming conventions.
- `writers.py`: write JSON/JSONL/CSV/Parquet (optional deps), save raw artifacts.

### Monitoring
`scrapping/monitoring/`
- `logging.py`: structured logs + per-run/per-source log files.
- `metrics.py`: counters/gauges/timers registry.
- `reporting.py`: build run reports from pipeline results + metrics.

### Processing (QA)
`scrapping/processing/`
- `html_to_structured.py`: HTML → structured doc (title/text/meta).
- `quality_filters.py`: rule-based quality gate (block pages, short text, etc.).
- `classifiers.py`: lightweight classification interfaces (keyword baseline + optional sklearn).

---

## 3) Runtime data flow

### 3.1 Pipeline sequence (typical source)
1. `discover_listing_urls()` builds listing URLs from config entrypoints/paging
2. `fetch_pages(listing_urls)` → save raw listing pages
3. `extract_links(listing_html)` → save extracted links
4. `fetch_pages(detail_urls)` → save raw detail pages
5. `html_to_structured()` → structured doc
6. `evaluate_quality()` → keep/drop with reasons
7. `validate_item()` → ensure required fields
8. `dedupe_items()` → stable dedupe (URL + content hash)
9. `write_items()` → items.jsonl + items_valid.jsonl + items_dropped.jsonl

### 3.2 Outputs per run
A run produces an auditable folder:

`results/run_<run_id>/`
- `run.log` (and optional JSON logs)
- `run_meta.json` (run config summary)
- `run_report.json` (sources summary + metrics)
- `sources/<source_id>/...` (raw pages, links, items, source.log)

---

## 4) Extension points

### Add a new site
- Prefer config-only if possible:
  - define entrypoints + paging
  - define discovery.link_extract method (regex/css/xpath)
  - define actions for rendering/clicking load-more
  - define parse selectors if needed
  - define validation + quality rules
- If config-only is insufficient:
  - add a custom extractor or parser function (keep it pure)
  - optionally add a custom “plugin stage” later (v2 goal)

### New anti-bot tactic
- Prefer **legal & ethical** tactics first:
  - rate limiting, retry/backoff, session reuse
  - realistic browsing actions (scroll, pauses)
  - reduce concurrency
- Add site-specific policies to config (engine + actions + quality filters)
- Use diagnostics and raw page dumps to confirm what’s happening.

### New storage backend
- Keep writers API stable:
  - write raw pages, links, items, report
- Implement a new writer in `scrapping/storage/` (e.g., S3 writer, DB writer)
- Keep layout stable for local debugging even if you also upload.

---

## 5) Collaboration conventions

- **One module = one responsibility** (no mega files)
- Prefer **pure functions** for extraction/QA transforms (easy tests)
- Any “site-specific hack” should be encoded as:
  1) config change, or
  2) a small extractor/plugin with tests and docs
- Every source config must include:
  - dedupe strategy
  - rate limit policy
  - quality rules (block patterns, min text length)
- PR checklist:
  - adds/updates config
  - includes a local run sample output (small)
  - includes tests or at least a reproducible HTML fixture

---

## 6) Roadmap (practical)
- V1: JSON configs → run pipeline → save artifacts + report
- V1.1: engine factory + orchestrator wiring + CLI
- V1.2: per-source scheduling + state store (seen links, last run)
- V2: “AI agent config builder” + automated tests per site + regression signals
