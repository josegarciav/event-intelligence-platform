# Config Specification

This library is **config-driven**. A config can describe:

* one site (`SourceConfig`)
* or a list of sources (`{"sources": [ ... ]}`)

The orchestrator loads config(s), validates them, then runs the pipeline per source.

---

## 1) Top-level formats

### 1.1 Single source

```json
{
  "source_id": "my_source",
  "engine": { ... },
  "entrypoints": [ ... ],
  "discovery": { ... },
  "parse": { ... },
  "validation": { ... },
  "quality": { ... },
  "storage": { ... }
}
```

### 1.2 Multi-source

```json
{
  "version": "1.0",
  "sources": [
    { "source_id": "source_a", "...": "..." },
    { "source_id": "source_b", "...": "..." }
  ]
}
```

---

## 2) SourceConfig fields (V1)

### 2.1 `source_id` (required)

String identifier used for output folder naming and reporting.

---

## 3) Engine configuration

### 3.1 `engine.type`

* `"http"`: requests-based fetch
* `"browser"`: Playwright render
* `"hybrid"`: mixes http + browser

Example:

```json
"engine": {
  "type": "http",
  "timeout_s": 15,
  "verify_ssl": true,
  "user_agent": "ScrappingBot/1.0"
}
```

### 3.2 Retry policy (recommended)

```json
"engine": {
  "max_retries": 3,
  "backoff_mode": "exp",
  "retry_on_status": [429, 500, 502, 503, 504]
}
```

### 3.3 Rate limiting (strongly recommended)

```json
"engine": {
  "rps": 0.5,
  "burst": 1,
  "min_delay_s": 0.2,
  "jitter_s": 0.3
}
```

---

## 4) Entrypoints & paging

### 4.1 `entrypoints`

List of listing entrypoints. Each entrypoint is a dict.

#### Paging mode: `page`

```json
"entrypoints": [
  {
    "url": "https://example.com/jobs?page={page}",
    "paging": { "mode": "page", "start": 1, "pages": 5, "step": 1 }
  }
]
```

#### Paging mode: `offset`

```json
"entrypoints": [
  {
    "url": "https://example.com/api/list?offset={offset}",
    "paging": { "mode": "offset", "start": 0, "pages": 10, "step": 20 }
  }
]
```

---

## 5) Discovery: extract links

### 5.1 `discovery.link_extract`

Choose an extraction strategy.

#### Regex extraction

```json
"discovery": {
  "link_extract": {
    "method": "regex",
    "pattern": "https://example\\.com/jobs/\\d+",
    "identifier": "/jobs/"
  }
}
```

#### CSS selector extraction

```json
"discovery": {
  "link_extract": {
    "method": "css",
    "selector": "a.job-card::attr(href)",
    "identifier": "/jobs/"
  }
}
```

#### XPath extraction (requires lxml)

```json
"discovery": {
  "link_extract": {
    "method": "xpath",
    "selector": "//a[contains(@class,'job')]/@href",
    "identifier": "/jobs/"
  }
}
```

### 5.2 Dedupe hints

```json
"discovery": {
  "dedupe": {
    "content_fields": ["title", "text"]
  }
}
```

---

## 6) Browser actions (optional)

Used when `engine.type` is `browser` or `hybrid` and you need interactions.

Example:

```json
"actions": [
  {"type": "close_popup", "selector": "button#cookie-accept"},
  {"type": "scroll", "params": {"repeat": 6, "min_px": 250, "max_px": 700}},
  {"type": "click", "selector": "button.load-more", "params": {"repeat": 2}},
  {"type": "wait_for", "selector": ".results"}
]
```

Supported action types (V1):

* `wait_for`, `click`, `hover`, `type`, `close_popup`, `scroll`, `sleep`, `mouse_drift`

---

## 7) Parsing configuration

Optional selectors for known layouts:

```json
"parse": {
  "title_selector": "h1",
  "text_selector": "article"
}
```

If omitted, the system attempts:

* trafilatura extraction (if installed)
* bs4 `get_text()` fallback

---

## 8) Validation

Validation is generic, field-based:

```json
"validation": {
  "url_field": "url",
  "title_field": "title",
  "text_field": "text",
  "min_text_len": 200,
  "require_title": false,
  "require_text": true
}
```

---

## 9) Quality rules (QA gate)

Quality filtering protects you from:

* anti-bot pages
* login walls
* empty pages / placeholder content

Example:

```json
"quality": {
  "min_text_len": 250,
  "max_boilerplate_ratio": 0.75,
  "block_patterns": ["verify you are human", "captcha", "access denied"]
}
```

---

## 10) Storage configuration

V1 default is JSONL outputs in the standard layout.

Example:

```json
"storage": {
  "output_root": "results",
  "items_format": "jsonl"
}
```

Supported `items_format` (V1):

* `jsonl` (always)
* `csv` (requires pandas)
* `parquet` (requires pyarrow or compatible stack)

---

## 11) Minimal end-to-end example

```json
{
  "source_id": "example_jobs",
  "engine": {
    "type": "http",
    "timeout_s": 15,
    "max_retries": 3,
    "backoff_mode": "exp",
    "retry_on_status": [429, 500, 502, 503, 504],
    "rps": 0.5,
    "min_delay_s": 0.2,
    "jitter_s": 0.3
  },
  "entrypoints": [
    {
      "url": "https://example.com/jobs?page={page}",
      "paging": { "mode": "page", "start": 1, "pages": 3 }
    }
  ],
  "discovery": {
    "link_extract": {
      "method": "css",
      "selector": "a.job-card::attr(href)",
      "identifier": "/jobs/"
    }
  },
  "validation": { "min_text_len": 200, "require_text": true },
  "quality": { "min_text_len": 250 }
}
```
