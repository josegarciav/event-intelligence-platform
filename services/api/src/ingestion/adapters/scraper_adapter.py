"""
Scraper Source Adapter.

Adapter for fetching and cleaning individual
event page HTML using the scrapping service engines.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

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
        html_parser: Optional[Callable[[str, str], Dict]] = None,
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

    def fetch(self, **kwargs) -> FetchResult:
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
        fetch_started = datetime.now(timezone.utc)
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
            listing_results = scraper.fetch_listing_pages(
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
            event_results = scraper.fetch_event_pages(event_urls, max_events=max_events)
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
            fetch_ended_at=datetime.now(timezone.utc),
        )

    def close(self) -> None:
        """Close scraper and release browser resources."""
        if self._scraper:
            self._scraper.close()
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

    def _get_engine(self):
        """Lazy-initialize the scrapping engine."""
        if self._engine is not None:
            return self._engine

        engine_type = self.config.engine_type

        if engine_type == "hybrid":
            from scrapping.engines.hybrid import HybridEngine, HybridEngineOptions
            from scrapping.engines.http import HttpEngineOptions

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
                nav_timeout_ms=int(self.config.timeout_s * 1000),
            )
            self._engine = BrowserEngine(options=options)
        else:
            raise ValueError(f"Unknown engine_type: {engine_type}")

        return self._engine

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self.config.rate_limit_per_second <= 0:
            return
        min_interval = 1.0 / self.config.rate_limit_per_second
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.monotonic()

    def fetch_compressed_html(self, url: str) -> Optional[str]:
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

            self._rate_limit()
            engine = self._get_engine()
            result = engine.get(url)

            if not result.ok or not result.text:
                self.logger.debug(
                    f"Fetch failed for {url}: status={result.status_code}"
                )
                return None

            # Extract structured text from HTML
            doc = html_to_structured(result.text, url=url)
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
                self.logger.debug(f"Quality check failed for {url}: {issues}")
                return None

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

    def close(self) -> None:
        """Release engine resources."""
        if self._engine is not None:
            self._engine.close()
            self._engine = None
