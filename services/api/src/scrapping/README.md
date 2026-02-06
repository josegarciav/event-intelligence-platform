# Scrapping Library (config-driven, team-friendly)

A collaborative, **config-first** Python scraping library built by the Data Science team.

## Why this repo

Websites evolve. HTML changes, anti-bot gets stricter, endpoints move, and “one script per site” becomes unmaintainable. This project standardizes **how we scrape** so we can:

* Add new sources fast (drop a config, reuse the same engine)
* Switch tactics when a site hardens (requests → browser → stealth → proxy)
* Run reliably at scale (scheduling, retries, checkpointing, observability)
* Keep outputs consistent (storage formats, schemas, dedupe)

The core idea: **the pipeline is code; each website is configuration**.

---

## Core concepts

### 1) A “Source” is a config

A source can be **one URL** or **a family of URLs** (pagination, categories, query templates). Sources live in `configs/` and are validated at runtime.

### 2) Pluggable engines

We choose the best technique per site:

* **HTTP**: `requests` + parsing (fast, cheap)
* **Browser**: SeleniumBase / Playwright (dynamic sites, heavy JS)
* **Hybrid**: HTTP discovery + browser for detail pages

### 3) Pipeline stages

Most sources map to some subset of these stages:

1. **Discover** listing pages
2. **Extract links** (jobs/products/articles)
3. **Fetch details** pages
4. **Parse & normalize** into a canonical schema
5. **Validate** (schema + quality rules)
6. **Dedupe** (within run + across runs)
7. **Persist** (Parquet/JSONL/DB + raw HTML for replay)
8. **Monitor** (metrics, logs, alerts)

---

## Repository layout (recommended)

```text
scrapping-lib/
  README.md
  pyproject.toml
  requirements.txt

  scrapping/
    __init__.py

    cli.py                 # `scrap run ...` entrypoint
    orchestrator.py        # loads configs, runs pipelines

    engines/
      http_engine.py       # requests, retries, rate limit
      browser_engine.py    # seleniumbase/playwright wrappers
      hybrid_engine.py

    extraction/
      link_extractor.py    # regex/css/xpath strategies
      parser_html.py       # bs4/lxml helpers
      validators.py        # schema + business rules

    storage/
      writer_parquet.py
      writer_jsonl.py
      writer_s3.py
      writer_fs.py

    dedupe/
      fingerprints.py      # url normalization, content hashes
      store.py             # sqlite/redis/local cache

    observability/
      metrics.py           # prometheus
      logging.py

    scheduling/
      prefect_flow.py      # optional
      cron_examples/       # optional

    ai/
      config_agent.py      # auto-config generation (idea)
      tests_agent.py       # auto-test generation (idea)

  configs/
    job_portals/
      maroc_jobs.json
    ecommerce/
      alibaba_l3.json

  tests/
    test_config_validation.py
    test_link_extractors.py
    fixtures/

  examples/
    quickstart_configs/
    notebooks/

  docs/
    architecture.md
    anti_bot_playbook.md
    data_contracts.md
```

---

## Quickstart

### 1) Install

```bash
python -m venv .venv
source .venv/bin/activate  # windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Run a config

```bash
python -m scrapping.cli run --config configs/job_portals/maroc_jobs.json
```

### 3) Run many configs

```bash
python -m scrapping.cli run --configs configs/job_portals/*.json --parallel 32
```

---

## The config format (V1)

A config file can contain **one source** or **an array of sources**.

### Minimal example (single source)

```json
{
  "source_id": "emplois_ma",
  "enabled": true,
  "kind": "job_portal",
  "entrypoints": [
    {"url": "https://www.emplois.co/page/{page}", "page_start": 1, "page_end": 5}
  ],
  "engine": {
    "type": "http",
    "timeout_s": 15,
    "verify_ssl": true
  },
  "discovery": {
    "link_extract": {
      "method": "regex",
      "pattern": "https://www\\.emplois\\.co/[^\"&]*",
      "identifier": "emplois.co/"
    },
    "dedupe": {"keys": ["normalized_url"]}
  },
  "storage": {
    "raw_pages": {"enabled": true, "format": "parquet"},
    "items": {"enabled": true, "format": "parquet"}
  }
}
```

### Multi-source file (array)

```json
[
  {"source_id": "rekrute", "...": "..."},
  {"source_id": "indeed",  "...": "..."}
]
```

---

## Config schema (extended)

This is the **expanded** schema to cover most real-world needs.

### A) Source metadata

* `source_id` (string, required): unique id
* `enabled` (bool): can be disabled without deleting
* `owner` (string): team owner
* `kind` (enum): job_portal, ecommerce, news, gov, etc.
* `tags` (list): region, language, priority group
* `data_rights_status` (enum): allowed, restricted, unknown
* `robots_policy` (enum): respect, ignore, unknown

### B) Scheduling

* `schedule`:

  * `frequency` (e.g. "15m", "2h", "daily")
  * `timezone`
  * `window` (optional): run only within certain hours
  * `priority` (int)
  * `polling_strategy` (enum): fixed, backoff, adaptive

### C) Entry points

* `entrypoints[]`:

  * `url` (supports `{page}`, `{query}`, etc.)
  * `page_start`, `page_end`, `page_step`
  * `unsequential` (bool) + `page_param` (for start offsets)
  * `rest_of_url` (suffix)
  * `params`, `headers`, `cookies` (optional)

### D) Engine selection

* `engine.type`: `http` | `browser` | `hybrid`
* `engine.browser`: `seleniumbase` | `playwright`
* `engine.headless`: bool
* `engine.user_agent`: fixed or random
* `engine.proxy_pool`: named pool
* `engine.rate_limit_policy`:

  * `rps`, `burst`, `min_delay_s`, `jitter_s`
* `engine.retry_policy`:

  * `max_retries`, `backoff`, `retry_on_status`
* `engine.captcha`:

  * `expected`: none|possible|likely
  * `handler`: manual|2captcha|solve-service|skip

### E) Page actions (browser)

* `actions[]` in order:

  * `scroll`, `click`, `wait_for`, `close_popup`, `type`, `hover`
  * Each action supports selectors and timeouts

### F) Extraction

* `discovery.link_extract.method`: regex | css | xpath | js
* `discovery.link_extract.pattern` / `selector`
* `detail.extract`:

  * `fields`: list of outputs with selectors & transforms
  * `pagination_next_selector` (optional)

### G) Normalization & validation

* `normalize`:

  * canonical URL rules
  * text cleanup rules
  * language detection (optional)
* `validate`:

  * schema name
  * min fields
  * quality thresholds

### H) Dedupe

* `dedupe_keys`: e.g. url, normalized_url, (title+company+date)
* `fingerprint`: content hash strategy
* `state_store`: local sqlite / redis / s3

### I) Storage

* `storage`:

  * `raw_pages`: {enabled, format, path}
  * `items`: {enabled, format, path}
  * `metadata`: run_id, timestamps
* Supported: Parquet, JSONL, CSV, DB connectors (optional)

---

## Examples mapped to current work

### Job portals (regex discovery → fetch detail pages)

Most job portals work well with:

* listing pages pagination
* regex link extraction
* concurrent fetches of detail pages
* save **both** page HTML and item HTML for replay

### Alibaba (human-like browser flow + resume)

Alibaba-style sources often require:

* browser engine
* human-like behavior (scrolling, delays)
* extracting filters and categories via JS
* checkpointing + resume for stability

---

## Observability

We support Prometheus-style metrics:

* pages attempted/succeeded
* items found/scraped
* success rate per site
* scrape duration, retries, errors (by type)

Logs:

* one log per run + per source
* structured JSON logs recommended (easy ingestion)

---

## Testing strategy

Scraping breaks. Tests are not optional.

**Unit tests**

* config validation
* URL normalization + dedupe fingerprints
* link extractor strategies

**Golden-file tests**

* store HTML fixtures and assert extraction still works

**Smoke tests**

* run each source on 1 page daily in CI

---

## How to add a new site

1. Create a config in `configs/<domain>/my_site.json`
2. Choose engine (`http` first; upgrade if needed)
3. Define entrypoint pagination
4. Implement link extraction (regex/css/xpath)
5. Add a minimal parser for detail pages if needed
6. Run locally, check outputs
7. Add a golden HTML fixture + test
8. Open PR

---

## Anti-bot playbook (quick)

* Add jittered delays + cap concurrency
* Rotate user agents
* Use cookies + consistent sessions when needed
* Prefer API endpoints if available
* Browser only for what requires JS
* Proxy pools when rate-limited
* Checkpoint & resume for long runs

---

## AI-assisted config generation (roadmap)

We can automate **"create the adequate config"** per URL using AI agents + tests.

### Agent idea: `ConfigAgent`

Input: a URL (or domain)

Output:

* a draft config file
* a test suite (fixtures + extract assertions)
* a small report on anti-bot risk + recommended engine

How it works (high-level):

1. **Probe** the site (HEAD/GET, headers, robots, redirects)
2. **Detect** if it’s SSR/CSR (JS-heavy)
3. **Find patterns** (pagination params, stable URL identifiers)
4. **Infer extractors** (regex from sampled links, css selectors from DOM)
5. **Generate a draft config**
6. **Run a test scrape** (1–2 pages) and validate results
7. **Iterate**: adjust pattern/selectors until tests pass
8. Save config + fixtures + a “confidence score”

### Where AI helps most

* turning messy HTML into stable selectors
* generating robust regex patterns
* proposing fallback strategies (alternate endpoints)
* writing golden tests automatically

---

## Governance (team collaboration)

* Every new source requires:

  * config file
  * at least 1 golden fixture
  * a short note on legal/robots posture
* Breakages should be handled via:

  * config patch when possible
  * engine upgrade only when needed

---

## Notes

This repo intentionally separates:

* **framework code** (stable)
* **source configs** (changes often)

That’s how we stay fast when the web changes.
