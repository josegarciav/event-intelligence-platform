"""
Scraper Source Adapter.

Adapter for fetching and cleaning individual
event page HTML using the scrapping service engines.
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from .base_adapter import AdapterConfig, BaseSourceAdapter, FetchResult, SourceType

logger = logging.getLogger(__name__)


@dataclass
class ScraperAdapterConfig(AdapterConfig):
    """Configuration for scraper-based adapters."""

    base_url: str = ""
    url_pattern: str = ""
    url_identifier: str = ""
    max_pages: int = 5
    timeout_s: float = 30.0
    min_delay_s: float = 2.0
    headless: bool = True
    city: str = "barcelona"
    country_code: str = "es"

    def __post_init__(self):
        """Set source type to SCRAPER."""
        self.source_type = SourceType.SCRAPER


class ScraperAdapter(BaseSourceAdapter):
    """
    Adapter for web scraping data sources.

    Uses the EventScraper from src.ingestion.pipelines.scrapers to fetch and parse
    web pages. Provides a unified interface that matches the API adapter.
    """

    def __init__(
        self,
        config: ScraperAdapterConfig,
        html_parser: Callable[[str, str], dict] | None = None,
    ):
        """
        Initialize the scraper adapter.

        Args:
            config: ScraperAdapterConfig with scraper settings
            html_parser: Function to parse HTML into event dict
        """
        self.html_parser = html_parser
        self._scraper = None
        super().__init__(config)

    @property
    def scraper_config(self) -> ScraperAdapterConfig:
        """Get typed config."""
        return self.config  # type: ignore[return-value]

    def _validate_config(self) -> None:
        """Validate scraper configuration."""
        if not self.scraper_config.base_url:
            raise ValueError("Scraper adapter requires base_url")

    def _get_scraper(self):
        """Get or create scraper instance."""
        if self._scraper is None:
            from src.ingestion.pipelines.scrapers.base_scraper import (
                EventScraper,
                ScraperConfig,
            )

            scraper_config = ScraperConfig(
                source_id=self.scraper_config.source_id,
                base_url=self.scraper_config.base_url,
                url_pattern=self.scraper_config.url_pattern,
                url_identifier=self.scraper_config.url_identifier,
                max_pages=self.scraper_config.max_pages,
                timeout_s=self.scraper_config.timeout_s,
                min_delay_s=self.scraper_config.min_delay_s,
                headless=self.scraper_config.headless,
                city=self.scraper_config.city,
                country_code=self.scraper_config.country_code,
            )
            self._scraper = EventScraper(scraper_config)
        return self._scraper

    async def fetch(self, **kwargs) -> FetchResult:
        """
        Fetch data via web scraping.

        Args:
            **kwargs: Scraper parameters
                - city: City to scrape
                - country_code: Country code
                - max_pages: Max listing pages
                - max_events: Max events to fetch

        Returns:
            FetchResult with raw data
        """
        fetch_started = datetime.now(UTC)
        all_data = []
        errors = []
        metadata = {
            "pages_fetched": 0,
            "events_fetched": 0,
            "parse_failures": 0,
        }

        city = kwargs.get("city", self.scraper_config.city)
        country_code = kwargs.get("country_code", self.scraper_config.country_code)
        max_pages = kwargs.get("max_pages", self.scraper_config.max_pages)
        max_events = kwargs.get("max_events")

        try:
            scraper = self._get_scraper()

            # Fetch listing pages
            listing_results = await scraper.fetch_listing_pages(
                city=city,
                country_code=country_code,
                max_pages=max_pages,
            )

            # Extract event URLs
            event_urls = []
            for result in listing_results:
                if result.ok and result.html:
                    urls = scraper.extract_event_urls(result.html, result.url)
                    event_urls.extend(urls)
                    metadata["pages_fetched"] += 1

            # Dedupe URLs
            event_urls = list(dict.fromkeys(event_urls))
            logger.info(f"Found {len(event_urls)} unique event URLs")

            # Fetch event detail pages
            event_results = await scraper.fetch_event_pages(event_urls, max_events=max_events)
            metadata["events_fetched"] = len(event_results)

            # Parse each event page
            for result in event_results:
                if result.ok and result.html:
                    try:
                        if self.html_parser:
                            parsed = self.html_parser(result.html, result.url)
                        else:
                            parsed = {"_raw_html": result.html, "_url": result.url}

                        parsed["_source_url"] = result.url
                        parsed["_fetch_url"] = result.final_url
                        all_data.append(parsed)
                    except Exception as e:
                        logger.warning(f"Failed to parse {result.url}: {e}")
                        metadata["parse_failures"] += 1
                        errors.append(f"Parse error for {result.url}: {e}")
                else:
                    errors.append(f"Fetch failed for {result.url}: {result.error}")

        except Exception as e:
            logger.error(f"Scraper fetch failed: {e}")
            errors.append(str(e))

        return FetchResult(
            success=len(all_data) > 0,
            source_type=SourceType.SCRAPER,
            raw_data=all_data,
            total_fetched=len(all_data),
            errors=errors,
            metadata=metadata,
            fetch_started_at=fetch_started,
            fetch_ended_at=datetime.now(UTC),
        )

    async def close(self) -> None:
        """Close scraper and release browser resources."""
        if self._scraper:
            await self._scraper.close()
            self._scraper = None


# ============================================================================
# HTML Enrichment Scraper
# ============================================================================


@dataclass
class HtmlEnrichmentConfig:
    """Configuration for HTML enrichment scraping."""

    enabled: bool = False
    engine_type: str = "hybrid"  # hybrid | http | browser
    rate_limit_per_second: float = 2.0
    timeout_s: float = 15.0
    min_text_len: int = 200
    max_text_length: int = 50_000
    source_name: str | None = None
    generated_config_path: str | None = None
    generated_config_dir: str | None = None
    wait_for: str | None = None
    actions: list[dict] = field(default_factory=list)
    preflight_urls: list[str] = field(default_factory=list)


class HtmlEnrichmentScraper:
    """
    Scraper for fetching and cleaning a single URL's HTML content.

    Uses the scrapping service's engines + html_to_structured + evaluate_quality
    to produce cleaned text for the compressed_html field on SourceInfo.
    """

    def __init__(self, config: HtmlEnrichmentConfig):
        """Initialize with HTML enrichment configuration."""
        self.config = config
        self._engine = None
        self._last_request_time: float = 0.0
        self.logger = logging.getLogger("enrichment.html_scraper")
        self._wait_for = config.wait_for
        self._actions = list(config.actions or [])
        self._preflight_urls = list(config.preflight_urls or [])
        self._preflight_done_hosts: set[str] = set()
        self._load_source_render_hints()

    def _resolve_generated_config_path(self) -> Path | None:
        """Resolve the generated scrapping config path for this source."""
        if self.config.generated_config_path:
            path = Path(self.config.generated_config_path).expanduser().resolve()
            return path if path.exists() else None

        source_name = (self.config.source_name or "").strip()
        if not source_name:
            return None

        if self.config.generated_config_dir:
            base_dir = Path(self.config.generated_config_dir).expanduser().resolve()
        else:
            # repo/services/api/src/ingestion/adapters/scraper_adapter.py
            # -> repo/services/scrapping/generated_configs/sources
            base_dir = Path(__file__).resolve().parents[4] / "scrapping" / "generated_configs" / "sources"

        candidates = [
            base_dir / f"{source_name}.json",
            base_dir / f"{source_name}_scraper_auto.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _load_source_render_hints(self) -> None:
        """
        Load optional browser rendering hints (wait_for/actions) from generated config.

        When no generated config is found, runs SourceDetector inline to pick
        the right engine for this source.
        """
        path = self._resolve_generated_config_path()
        if path is None:
            self._detect_source_inline()
            return

        try:
            with path.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            self.logger.debug(f"Failed to read generated config at {path}: {e}")
            return

        # Prefer explicit runtime config values; fill missing values from source config.
        discovery = cfg.get("discovery", {}) or {}
        if self._wait_for is None:
            self._wait_for = discovery.get("wait_for") or None

        if not self._actions:
            actions = cfg.get("actions")
            if isinstance(actions, list):
                self._actions = [a for a in actions if isinstance(a, dict)]

        if not self._preflight_urls:
            entrypoints = cfg.get("entrypoints") or []
            urls = []
            for entry in entrypoints:
                if isinstance(entry, dict):
                    ep_url = entry.get("url")
                    if isinstance(ep_url, str) and ep_url.startswith(("http://", "https://")):
                        urls.append(ep_url)
            if urls:
                self._preflight_urls = urls

        # If generated config recommends browser/hybrid, do not stay on plain http.
        generated_engine_type = ((cfg.get("engine", {}) or {}).get("type") or "").lower()
        if self.config.engine_type == "http" and generated_engine_type in {
            "browser",
            "hybrid",
        }:
            self.logger.info(
                "Upgrading HTML enrichment engine from http to %s using %s",
                generated_engine_type,
                path,
            )
            self.config.engine_type = generated_engine_type

    def _detect_source_inline(self) -> None:
        """Run SourceDetector when no generated config exists to pick the right engine."""
        # Need at least a preflight URL or source name to derive a seed URL
        seed_url = next(iter(self._preflight_urls), None)
        if not seed_url:
            return

        try:
            from src.ingestion.source_detector import SourceDetector

            detection = SourceDetector(min_text_len=self.config.min_text_len).probe(seed_url)
            if detection.needs_javascript and self.config.engine_type == "http":
                self.logger.info(
                    "SourceDetector recommends '%s' engine for %s (was http)",
                    detection.recommended_engine,
                    seed_url,
                )
                self.config.engine_type = detection.recommended_engine
            if detection.wait_for_selector and self._wait_for is None:
                self._wait_for = detection.wait_for_selector
            if detection.requires_actions and not self._actions:
                self._actions = detection.requires_actions
        except Exception as exc:
            self.logger.debug("Inline source detection failed: %s", exc)

    def _get_url_host(self, url: str) -> str:
        """Extract lowercase host name from URL."""
        try:
            return (urlparse(url).hostname or "").lower()
        except Exception:
            return ""

    def _run_preflight(self, engine, target_url: str) -> None:
        """
        Warm up browser session against listing/base pages before detail fetch.

        This can reduce anti-bot challenge pages for some sources.
        """
        target_host = self._get_url_host(target_url)
        if not target_host or target_host in self._preflight_done_hosts:
            return
        if not hasattr(engine, "get_rendered"):
            return

        preflight_urls = self._preflight_urls or []
        # Fallback to site root when no source-specific entrypoint is available.
        if not preflight_urls:
            preflight_urls = [f"https://{target_host}/"]

        for preflight_url in preflight_urls:
            try:
                engine.get_rendered(preflight_url, actions=None, wait_for=None)
            except Exception as e:
                self.logger.debug(f"Preflight request failed for {preflight_url}: {e}")
        self._preflight_done_hosts.add(target_host)

    def _get_engine(self):
        """Lazy-initialize the scrapping engine."""
        if self._engine is not None:
            return self._engine

        engine_type = self.config.engine_type

        if engine_type == "hybrid":
            from scrapping.engines.http import HttpEngineOptions
            from scrapping.engines.hybrid import HybridEngine, HybridEngineOptions

            http_opts = HttpEngineOptions(
                timeout_s=self.config.timeout_s,
                rps=self.config.rate_limit_per_second,
            )
            options = HybridEngineOptions(
                http=http_opts,
                min_text_len=self.config.min_text_len,
            )
            self._engine = HybridEngine(options=options)
        elif engine_type == "http":
            from scrapping.engines.http import HttpEngine, HttpEngineOptions

            options = HttpEngineOptions(
                timeout_s=self.config.timeout_s,
                rps=self.config.rate_limit_per_second,
            )
            self._engine = HttpEngine(options=options)
        elif engine_type == "browser":
            from scrapping.engines.browser import BrowserEngine, BrowserEngineOptions

            options = BrowserEngineOptions(
                nav_timeout_s=self.config.timeout_s,
            )
            self._engine = BrowserEngine(options=options)
        else:
            raise ValueError(f"Unknown engine_type: {engine_type}")

        return self._engine

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self.config.rate_limit_per_second <= 0:
            return
        min_interval = 1.0 / self.config.rate_limit_per_second
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.monotonic()

    async def fetch_compressed_html(self, url: str) -> str | None:
        """
        Fetch a URL, extract clean text, and return it if quality passes.

        Returns:
            Cleaned text content, or None if fetch/quality fails.
        """
        if not url:
            return None

        try:
            from scrapping.processing.html_to_structured import html_to_structured
            from scrapping.processing.quality_filters import evaluate_quality

            await self._rate_limit()
            engine = self._get_engine()
            needs_render = self.config.engine_type in {"browser", "hybrid"}
            if needs_render and hasattr(engine, "get_rendered"):
                self._run_preflight(engine, url)
                result = engine.get_rendered(
                    url,
                    actions=self._actions or None,
                    wait_for=self._wait_for,
                )
                if result.block_signals:
                    # Retry once after forcing a fresh preflight sequence.
                    target_host = self._get_url_host(url)
                    if target_host:
                        self._preflight_done_hosts.discard(target_host)
                    self._run_preflight(engine, url)
                    result = engine.get_rendered(
                        url,
                        actions=self._actions or None,
                        wait_for=self._wait_for,
                    )
            else:
                result = engine.get(url)

            if not result.text:
                self.logger.debug(f"Fetch failed for {url}: status={result.status_code}")
                return None
            if not result.ok and result.block_signals:
                self.logger.debug(
                    f"Blocked content for {url}: status={result.status_code} "
                    f"signals={[str(s) for s in result.block_signals]}"
                )
                return None

            # Extract structured text from HTML
            doc = html_to_structured(result.text, url=url)

            # Post-extraction fallback: if text is too short and browser
            # rendering is available, retry with rendered content.
            if (
                doc.text
                and len(doc.text) < self.config.min_text_len
                and hasattr(engine, "get_rendered")
                and not needs_render
            ):
                self.logger.debug(
                    "Short text extraction (%d chars) for %s, retrying with browser rendering",
                    len(doc.text),
                    url,
                )
                self._run_preflight(engine, url)
                rendered = engine.get_rendered(
                    url,
                    actions=self._actions or None,
                    wait_for=self._wait_for,
                )
                if rendered.text and len(rendered.text) > len(result.text):
                    doc = html_to_structured(rendered.text, url=url)

            if not doc.ok or not doc.text:
                self.logger.debug(f"No text extracted from {url}")
                return None

            # Quality check
            quality = evaluate_quality(
                {"url": url, "title": doc.title or "", "text": doc.text},
                rules={"min_text_len": self.config.min_text_len},
            )
            if not quality.keep:
                issues = ", ".join(i.message for i in quality.errors())
                # Accept short-text-only failures as a best-effort fallback.
                # Hard failures (captcha/access denied/etc.) still return None.
                hard_errors = [i for i in quality.errors() if i.code != "short_text"]
                if hard_errors:
                    # Last resort: try browser rendering if we haven't already
                    if not needs_render and hasattr(engine, "get_rendered"):
                        self.logger.debug(
                            "Quality hard-fail for %s (%s), retrying with browser",
                            url,
                            issues,
                        )
                        self._run_preflight(engine, url)
                        rendered = engine.get_rendered(
                            url,
                            actions=self._actions or None,
                            wait_for=self._wait_for,
                        )
                        if rendered.text:
                            doc = html_to_structured(rendered.text, url=url)
                            if doc.ok and doc.text:
                                retry_quality = evaluate_quality(
                                    {"url": url, "title": doc.title or "", "text": doc.text},
                                    rules={"min_text_len": self.config.min_text_len},
                                )
                                retry_hard = [i for i in retry_quality.errors() if i.code != "short_text"]
                                if not retry_hard:
                                    text = doc.text
                                    if len(text) > self.config.max_text_length:
                                        text = text[: self.config.max_text_length]
                                    return text
                    self.logger.debug(f"Quality check failed for {url}: {issues}")
                    return None
                self.logger.debug(f"Quality short-text fallback accepted for {url}: {issues}")

            # Truncate if needed
            text = doc.text
            if len(text) > self.config.max_text_length:
                text = text[: self.config.max_text_length]

            return text

        except ImportError as e:
            self.logger.warning(f"Scrapping service not available: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"HTML enrichment failed for {url}: {e}")
            return None

    async def close(self) -> None:
        """Release engine resources."""
        if self._engine is not None:
            try:
                self._engine.close()
            except Exception as e:
                # Notebook/interactive contexts can have thread-loop teardown
                # order issues in browser stacks. Ignore cleanup-only errors.
                self.logger.debug(f"Error while closing HTML enrichment engine: {e}")
            self._engine = None
