# Scrapping Library (config-driven, team-friendly)

A collaborative, **config-first** Python scraping library built by the Data Science team.

## Why this repo

Websites evolve. HTML changes, anti-bot gets stricter, and “one script per site” becomes unmaintainable. This project standardizes **how we scrape** so we can:

* Add new sources fast (drop a config, reuse the same engine)
* Switch tactics when a site hardens (requests → browser → stealth → proxy)
* Run reliably at scale (scheduling, retries, observability)
* Keep outputs consistent (storage formats, schemas, dedupe)

---

## Quickstart

### 1) Install

Install the core library and all dependencies:

```bash
# Core + All optional engines/formats
pip install -e ".[all]"

# For Browser engine and Notebooks specifically:
pip install -e ".[browser,notebooks,dev]"
playwright install

# Development dependencies (testing, linting)
pip install -e ".[dev]"
```

#### Linux/Colab Playwright Dependencies
If you are running on Linux (including Google Colab) and encounter errors about missing shared libraries (e.g., `libatk-1.0.so.0`), you need to install the system dependencies:
```bash
# Preferred (installs OS deps automatically)
playwright install --with-deps chromium

# Alternative (just the dependencies)
playwright install-deps chromium
```

### 2) Check environment

```bash
python cli.py doctor
```

### 3) Validate a config

```bash
python cli.py validate --config examples/configs/example_http_jobs.json
```

### 4) Run a scrape

```bash
python cli.py run --config examples/configs/example_http_jobs.json --results results
```

---

## Core commands

* `scrap doctor`: Checks if dependencies (like Playwright) are installed correctly.
* `scrap validate`: Checks if your config JSON follows the schema and passes sanity checks.
* `scrap run`: Executes the scraping pipeline for the given config.
    * `--only source_id`: Run only specific sources from a multi-source config.
    * `--dry-run`: Validate and plan without making network calls.
    * `--items-format jsonl`: Override output format (jsonl, csv, parquet).

---

## Results layout

Results are saved by default in `results/run_<timestamp>_<id>/`:

* `run_report.json`: Overall summary of the run.
* `run_meta.json`: Host and environment info.
* `sources/<source_id>/`:
    * `meta.json`: The config used for this source.
    * `raw_pages/`: HTML/content of listing and detail pages.
    * `links/`: All discovered detail URLs.
    * `items/`: Extracted data in requested format.
    * `source.log`: Detailed logs for this specific source.

---

## When to use HTTP vs Browser vs Hybrid

| Engine | Best for | Pros | Cons |
| :--- | :--- | :--- | :--- |
| **HTTP** | Static sites, APIs, high volume | Extremely fast, low resource use | No JS execution, easily blocked |
| **Browser** | Heavy JS, SPAs, Login walls | Renders anything a human sees | Slow, resource intensive |
| **Hybrid** | Large JS-heavy sites | Fast discovery (HTTP) + Accurate extraction (Browser) | Complexity in config |

---

## Adding a new source

1. Look at `examples/configs/` for inspiration.
2. Create your config JSON.
3. Test with `--dry-run`.
4. Run locally and verify artifacts in the `results` folder.
5. Add a unit test if special parsing logic is added.

---

## Documentation Hub

Visit our **[Documentation Hub](./docs/README.md)** for a complete guide to the library, including:
* [Config Schema Reference](./docs/config_schema.md)
* [Full Notebook Series](./notebooks/README.md)
* [End-to-End Walkthrough](./notebooks/01_end_to_end_walkthrough_example_multi_sources.ipynb)
* Troubleshooting and Best Practices

---

## Testing & Regression

The library promotes an **offline-first** development workflow.

### 1) Run unit tests
```bash
PYTHONPATH=. python -m pytest
```

### 2) Notebook smoke tests
To ensure our tutorial notebooks remain runnable (offline mode), run the smoke test script:
```bash
PYTHONPATH=. python scripts/smoke_notebooks.py
```

### 3) Capture new fixtures
Use the CLI to capture a site's HTML for offline testing:
```bash
scrap capture-fixture --url "https://example.com" --out tests/fixtures/html/my_site.html
```

---

## Repository layout

```text
scrapping/
  cli.py                 # CLI interface
  orchestrator.py        # Lifecycle management
  engines/               # HTTP, Browser, Hybrid engines
  pipeline/              # Multi-stage pipeline logic
  storage/               # Layouts and writers
  config/                # Pydantic schema and validation
```
