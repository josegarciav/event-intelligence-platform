
# Runbook — Operating the Scrapping Library

This runbook explains how to run scrapes safely, troubleshoot issues, and interpret outputs.

---

## 1) Running locally

### Basic run
- Use the CLI `scrap run` with a config JSON (single source or multi-source).
- Output is written to `results/run_<run_id>/` by default.

Expected outputs:
- `run.log`
- `run_meta.json`
- `run_report.json`
- `sources/<source_id>/*`

### Validating config
Use `scrap validate` to:
- check schema correctness
- ensure required fields exist
- detect unknown keys (optional future strict mode)

### Doctor
Use `scrap doctor` to:
- confirm optional dependencies available (playwright, lxml, trafilatura, pandas/pyarrow)
- confirm browser installation if using Playwright

---

## 2) Understanding output folders

### Run-level
`results/run_<run_id>/`
- `run.log`: global logs
- `run_meta.json`: config snapshot + environment info (recommended)
- `run_report.json`: per-source stats, errors, metrics

### Source-level
`results/run_<run_id>/sources/<source_id>/`
- `source.log`: per-source logs
- `raw_pages/listing/*.jsonl`: listing fetches
- `raw_pages/detail/*.jsonl`: detail fetches
- `links/extracted_links.jsonl`: extracted URLs
- `items/items.jsonl`: parsed items
- `items/items_valid.jsonl`: after validation + dedupe
- `items/items_dropped.jsonl`: invalid/blocked/duplicates with reasons

---

## 3) Common incidents and how to respond

### A) No links extracted
Check:
1. `raw_pages/listing/*.jsonl` — does HTML contain links?
2. `discovery.link_extract` config:
   - regex pattern wrong?
   - css selector wrong?
   - missing base_url join?

Fixes:
- Switch from regex to css/xpath (often more stable)
- Add identifier filter to reduce noise
- Add actions + browser engine if listing is JS-heavy

---

### B) Many dropped items, few valid
Likely causes:
- blocked pages
- login walls / consent pages
- very short text extraction

What to inspect:
- `items/items_dropped.jsonl` reasons
- raw detail HTML for a few samples
- quality rules might be too strict

Fixes:
- add block patterns
- switch to browser/hybrid
- add wait_for + close_popup actions
- tune `min_text_len` thresholds

---

### C) Runs get slower / hang
Likely causes:
- too much browser concurrency
- leaked browser processes (mis-handled teardown)
- site became heavier

Fixes:
- lower `parallelism` for that source
- prefer HTTP for listing pages
- confirm browser engine closes contexts (ensure `engine.close()` called)
- enable per-source logs and look for repeated retries

---

### D) 429 / rate limit
Fixes:
- lower `rps`, increase `min_delay_s`
- enable exponential backoff
- reduce paging depth and run more frequently instead of deep paging

---

## 4) Monitoring and reporting

### Logs
- Use `run.log` for global visibility
- Use `sources/<source_id>/source.log` for deep debugging

### Metrics
- timers: per-source run duration, fetch durations (as added)
- counters: pages fetched, errors, items parsed, valid, dropped

### Run report
`run_report.json` includes:
- per-source status and summary stats
- error list (if captured)
- metrics registry export

---

## 5) Safe operating guidelines (team defaults)

- Always start conservative:
  - low concurrency
  - low rps
  - strict QA filters
- Prefer incremental scraping:
  - fewer pages per run, more frequent runs
- Never silently drop:
  - always write dropped items with reason codes
- Keep configs versioned:
  - when a site changes, commit config update + a short note in PR

---

## 6) On-call checklist (quick)

1. Identify source(s) failing in `run_report.json`
2. Open `sources/<source_id>/source.log`
3. Inspect:
   - listing raw pages
   - extracted links file
   - detail raw pages
   - dropped items reasons
4. Apply minimal fix:
   - extraction selector/pattern
   - engine switch (http → hybrid/browser)
   - rate limit reduction
   - add wait_for + close_popup
5. Re-run source only and confirm recovery
