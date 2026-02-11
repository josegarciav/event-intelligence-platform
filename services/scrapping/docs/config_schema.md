# Configuration Schema Docs

The `scrapping` library is config-driven. Each scraping source is defined by a JSON configuration.

## Minimal Example

```json
{
  "source_id": "my_source",
  "engine": { "type": "http" },
  "entrypoints": [ { "url": "https://example.com/items" } ],
  "discovery": {
    "link_extract": {
      "method": "regex",
      "pattern": "https://example\\.com/items/\\d+"
    }
  }
}
```

## Important Fields

### `source_id` (string, required)
Unique identifier for the source. Used for directory names and logs. No spaces allowed.

### `engine` (object)
Defines how to fetch pages.
- `type`: `http`, `browser`, or `hybrid`.
- `timeout_s`: Request timeout in seconds (default: 15.0).
- `verify_ssl`: Whether to verify SSL certificates (default: true).
- `retry_policy`: Configuration for retries (max_retries, backoff).

### `entrypoints` (list)
Starting points for discovery.
- `url`: The URL to start from.
- `paging`: Optional pagination config (mode, start, end, step).

### `discovery` (object)
How to find detail pages from entrypoints.
- `link_extract`: Strategy for extracting links.
    - `method`: `regex`, `css`, `xpath`.
    - `pattern` / `selector`: The pattern or selector to use.
- `wait_for`: Optional CSS selector to wait for before extraction (Browser/Hybrid only).

### `quality` (object)
Rules for validating extracted items.
- `min_text_len`: Minimum length of extracted text.
- `required_fields`: List of fields that must be present (e.g., ["title", "text"]).
- `block_patterns`: Regex patterns that indicate a blocked page (e.g., "captcha").

### `storage` (object)
- `items_format`: `jsonl`, `csv`, or `parquet`.

## Common Pitfalls

- **Regex too broad**: If your link extraction regex is too broad, you might crawl the entire internet. Always anchor it to the target domain.
- **Missing pattern**: When using `method: "regex"`, the `pattern` field is mandatory.
- **Blocked pages**: If you see "Access Denied" or "Captcha" in your logs, consider switching to `browser` engine or adding a `proxy_pool`.
- **JS Content**: If the page is empty in `http` mode but shows content in a browser, it likely requires JavaScript. Use `engine: { "type": "browser" }`.
