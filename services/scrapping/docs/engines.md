# Engines Documentation

The `scrapping` library supports three primary engine types, each optimized for different scraping scenarios.

## 1. HTTP Engine

**Best for**: Static sites, APIs, high-volume scraping.

### Features
- **Session Management**: Reuses HTTP sessions and maintains cookie jars.
- **Connection Pooling**: Efficiently handles multiple concurrent requests.
- **Retry Policy**: Standard exponential backoff on 429 (Too Many Requests) and 5xx (Server Error) status codes.
- **Rate Limiting**: Domain-specific token bucket to ensure compliance with target site limits.

### Options
- `timeout_s`: Total request timeout (default: 15s).
- `verify_ssl`: Whether to enforce SSL certificate validation.
- `pool_connections`: Number of connection pools to cache.
- `pool_maxsize`: Maximum number of connections to keep in the pool.

---

## 2. Browser Engine

**Best for**: JavaScript-heavy sites, Single Page Applications (SPAs), and sites requiring complex user interaction.

### Features
- **JS Rendering**: Executes JavaScript and returns the fully rendered DOM.
- **Action DSL**: Supports sequence of actions like `scroll`, `click`, `wait_for`, `type`, and `hover`.
- **Resource Control**: Ability to block images and fonts to save bandwidth and improve speed.
- **Isolated Contexts**: Resets browser context on errors to ensure clean state.

### Options
- `browser_name`: `chromium`, `firefox`, or `webkit`.
- `headless`: Whether to run without a GUI.
- `nav_timeout_s`: Timeout for the initial page navigation.
- `render_timeout_s`: Timeout for `wait_for` selectors and actions.
- `block_images`: Abort image requests.
- `block_fonts`: Abort font requests.

---

## 3. Hybrid Engine

**Best for**: Large sites where discovery is fast but extraction is complex.

### Features
- **Speed & Accuracy**: Uses HTTP for discovery (listing pages) and Browser for detail pages.
- **Automatic Fallback**: Can be configured to try HTTP first and fallback to Browser if content is missing or blocked.
- **Unified Trace**: Returns results with a complete trace of all attempts across both sub-engines.

### Fallback Policy
- Triggers if HTTP status is non-OK.
- Triggers if block signals are detected in HTTP response.
- Triggers if the extracted text length is below the configured `min_text_len`.

---

## Resilience & Common Features

All engines share a common resilience layer provided by the `scrapping.runtime` modules.

### Rate Limiter
- Configurable Requests Per Second (RPS).
- Support for burst capacity.
- Jittered delays between requests to mimic human behavior.

### Retry & Backoff
- Configurable maximum retries.
- Multiple backoff modes: `exp` (exponential), `fixed`, `none`.
- Jittered retry intervals.

### Block Detection
All engine results are automatically classified for potential blocking signatures:
- `LIKELY_BLOCKED`
- `CAPTCHA_PRESENT`
- `LOGIN_REQUIRED`
- `UNKNOWN` (Default)
