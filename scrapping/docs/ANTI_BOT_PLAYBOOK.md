# Anti-Bot Playbook (Ethical + Practical)

This playbook focuses on reliability while staying compliant with legal/ethical constraints.
The goal is to avoid brittle hacks and prefer stable, defensible tactics.

---

## 1) First principles

1. **Reduce aggressiveness first**

   * Lower concurrency
   * Add rate limits + jitter
   * Add realistic delays in browser actions
2. **Prefer official endpoints if available**

   * Public APIs, feeds, sitemaps, RSS, structured data
3. **Always keep evidence**

   * Save raw HTML responses
   * Store status codes, headers, and error messages
   * Write run reports and per-source logs

---

## 2) Symptom → Likely cause → What to do

### A) Sudden 403 / 401 / 429 spikes

**Cause**

* IP throttled / WAF rules / rate limit policy

**Actions**

* Increase `min_delay_s`, lower `rps`
* Reduce parallelism for that source
* Ensure retries are configured and not hammering
* Add backoff mode `exp` and retry statuses include 429/503

---

### B) HTML contains “verify you are human”, “captcha”, Cloudflare phrases

**Cause**

* Anti-bot challenge page

**Actions**

* Don’t loop blindly: mark as blocked using `quality.block_patterns`
* Switch engine to `browser` or `hybrid`
* Add actions:

  * close cookie banner
  * wait_for real content selector
  * scroll a bit before extracting
* If challenges persist:

  * reduce frequency and concurrency further
  * use session reuse (browser context already helps)
  * consider whether scraping is allowed/appropriate for that source

**Non-goals**

* This project should not include bypassing CAPTCHAs or evading access controls.

---

### C) Page loads but content is empty (JS app shell)

**Cause**

* Client-side rendering; HTTP fetch sees minimal HTML

**Actions**

* Use `engine.type = browser` or `hybrid`
* Use `actions` + `wait_for` on a meaningful selector
* Consider extracting data from network calls (future feature)

---

### D) “Soft blocks” (200 OK but content is wrong)

Examples:

* login wall
* “enable javascript”
* modal overlays
* geo/consent pages

**Actions**

* Add block patterns in quality rules
* Add `close_popup` actions (cookie banners)
* Add `wait_for` the real content selector
* Add region/language handling if the site redirects
* Consider explicit extraction selectors instead of generic extraction

---

## 3) Config knobs that matter

### Rate limiting

* `rps`, `min_delay_s`, `jitter_s`, `burst`

Guideline:

* Start conservative (e.g., `rps=0.3`), then increase only if stable.

### Retry policy

* `max_retries`: 2–3 is usually enough
* `backoff_mode`: exp is safest
* `retry_on_status`: include 429 and 5xx

### Engine choice

* HTTP is fastest and simplest.
* Browser is heavier but necessary for JS-heavy sites.
* Hybrid is good when:

  * listing pages are static
  * detail pages require JS

---

## 4) Browser action patterns that help

Typical robust sequence:

```json
[
  {"type":"close_popup","selector":"button#cookie-accept"},
  {"type":"wait_for","selector":"body"},
  {"type":"scroll","params":{"repeat":4,"min_px":200,"max_px":700}},
  {"type":"wait_for","selector":".results"}
]
```

If the site uses “load more”:

```json
[
  {"type":"scroll","params":{"repeat":3}},
  {"type":"click","selector":"button.load-more","params":{"repeat":3,"pause_s":1.0}}
]
```

Typing into search fields:

```json
[
  {"type":"type","selector":"input[name=q]","params":{"text":"data scientist","clear":true}},
  {"type":"sleep","params":{"preset":"short"}},
  {"type":"click","selector":"button[type=submit]"}
]
```

---

## 5) QA gates to prevent polluted datasets

Always enable quality filters:

* `min_text_len` (drop tiny pages)
* `block_patterns` (drop block pages)
* `max_boilerplate_ratio` (drop shells/placeholders)

Store dropped items with reasons:

* keep a `items_dropped.jsonl` that contains `_quality_issues` or `_validation_errors`

---

## 6) Debug workflow (recommended)

1. Run the source alone with low concurrency.
2. Inspect:

   * raw listing HTML
   * extracted links
   * raw detail HTML
   * items_dropped + reason codes
3. Tune:

   * extraction method (regex → css/xpath)
   * add wait_for selectors
   * lower rps and increase delays
4. Re-run and compare run report diffs.

---

## 7) What we intentionally don’t do

* CAPTCHA solving / bypassing access controls
* credential stuffing / login automation without explicit permission
* techniques that violate site terms or legal boundaries
