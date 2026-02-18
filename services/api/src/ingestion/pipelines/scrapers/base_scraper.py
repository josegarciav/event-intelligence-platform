"""
Base Scraper Pipeline and related utilities.

This module provides:
- PageFetchResult: Result of fetching a single page
- ScraperConfig: Configuration for the scraper
- EventScraper: Playwright-based browser automation for web scraping (async)
- BaseScraperPipeline: Abstract base class for scraper-based pipelines
- Config loading utilities for JSON scraper configs
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright

from src.ingestion.adapters import ScraperAdapter, SourceType
from src.ingestion.adapters.scraper_adapter import ScraperAdapterConfig
from src.ingestion.pipelines.base_pipeline import BasePipeline, PipelineConfig

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class PageFetchResult:
    """Result of fetching a single page."""

    ok: bool
    url: str
    final_url: str
    status_code: int | None
    html: str | None
    error: str | None = None
    elapsed_s: float = 0.0


@dataclass
class ScraperConfig:
    """Configuration for the EventScraper."""

    source_id: str
    base_url: str
    url_pattern: str  # Regex pattern for extracting event URLs
    url_identifier: str  # URL fragment to identify event links
    max_pages: int = 5
    timeout_s: float = 30.0
    min_delay_s: float = 2.0
    headless: bool = True
    city: str = "barcelona"
    country_code: str = "es"


# =============================================================================
# CONFIG LOADER
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
SCRAPER_CONFIGS_DIR = PROJECT_ROOT / "scrapping" / "configs" / "sources"


def get_config_path(source_name: str) -> Path:
    """
    Get the path to a scraper config file.

    Args:
        source_name: Name of the source (e.g., "ra_co")

    Returns:
        Path to the config JSON file

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    config_path = SCRAPER_CONFIGS_DIR / f"{source_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Scraper config not found: {config_path}. Available configs: {list_available_configs()}"
        )
    return config_path


def list_available_configs() -> list[str]:
    """List all available scraper config names."""
    if not SCRAPER_CONFIGS_DIR.exists():
        return []
    return [f.stem for f in SCRAPER_CONFIGS_DIR.glob("*.json")]


def load_config_raw(source_name: str) -> dict[str, Any]:
    """
    Load raw config dict from JSON file.

    Args:
        source_name: Name of the source

    Returns:
        Raw config dictionary
    """
    config_path = get_config_path(source_name)
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def load_scraper_config(
    source_name: str,
    *,
    city: str | None = None,
    country_code: str | None = None,
    max_pages: int | None = None,
    headless: bool = True,
    **overrides: Any,
) -> ScraperConfig:
    """
    Load a scraper config from JSON and create a ScraperConfig instance.

    Args:
        source_name: Name of the source (e.g., "ra_co")
        city: City to scrape (e.g., "barcelona")
        country_code: Country code (e.g., "es")
        max_pages: Maximum listing pages to scrape
        headless: Run browser in headless mode
        **overrides: Additional config overrides

    Returns:
        ScraperConfig instance

    Example:
        >>> config = load_scraper_config(
        ...     "ra_co",
        ...     city="barcelona",
        ...     country_code="es",
        ...     max_pages=2
        ... )
    """
    raw_config = load_config_raw(source_name)

    source_id = raw_config.get("source_id", source_name)

    # Get base URL from entrypoints
    entrypoints = raw_config.get("entrypoints", [])
    base_url = "https://ra.co/events"
    if entrypoints:
        url_template = entrypoints[0].get("url", "")
        if "{" in url_template:
            base_url = url_template.split("{")[0].rstrip("/")
        else:
            base_url = url_template

    # Get discovery config
    discovery = raw_config.get("discovery", {})
    link_extract = discovery.get("link_extract", {})
    url_pattern = link_extract.get("pattern", r"/events/\d+")
    url_identifier = link_extract.get("identifier", "/events/")

    # Get engine config
    engine = raw_config.get("engine", {})
    timeout_s = engine.get("timeout_s", 30.0)
    rate_policy = engine.get("rate_limit_policy", {})
    min_delay_s = rate_policy.get("min_delay_s", 2.0)

    # Get default params from entrypoints
    default_params = {}
    if entrypoints:
        default_params = entrypoints[0].get("params", {})

    # Determine paging
    paging = entrypoints[0].get("paging", {}) if entrypoints else {}
    config_max_pages = paging.get("end", 5)

    return ScraperConfig(
        source_id=source_id,
        base_url=base_url,
        url_pattern=url_pattern,
        url_identifier=url_identifier,
        max_pages=max_pages if max_pages is not None else config_max_pages,
        timeout_s=timeout_s,
        min_delay_s=min_delay_s,
        headless=headless,
        city=city or default_params.get("city", "barcelona"),
        country_code=country_code or default_params.get("country_code", "es"),
    )


# Alias for backwards compatibility
load_event_scraper_config = load_scraper_config


# =============================================================================
# EVENT SCRAPER (ASYNC)
# =============================================================================


class EventScraper:
    """
    Event scraper using async Playwright for browser automation.

    Handles:
    - Fetching listing pages with pagination
    - Extracting event URLs from listing pages
    - Fetching individual event detail pages (parallel batches)

    Usage:
        config = ScraperConfig(...)
        async with EventScraper(config) as scraper:
            listing_results = await scraper.fetch_listing_pages()
            event_urls = scraper.extract_event_urls(listing_results[0].html, base_url)
            event_results = await scraper.fetch_event_pages(event_urls)
    """

    def __init__(self, config: ScraperConfig):
        """
        Initialize the event scraper.

        Args:
            config: ScraperConfig instance
        """
        self.config = config
        self._browser: Browser | None = None
        self._playwright: Playwright | None = None

    async def _ensure_browser(self) -> None:
        """Ensure browser is started."""
        if self._browser is not None:
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "playwright is required for scraping. Install it with: pip install playwright && playwright install"
            )

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
        logger.info("Browser started")

    async def close(self) -> None:
        """Close browser and release resources."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self._playwright = None

    async def _fetch_page(self, url: str) -> PageFetchResult:
        """Fetch a single page with stealth settings."""
        await self._ensure_browser()
        assert self._browser is not None  # ensured by _ensure_browser()

        start_time = time.time()
        try:
            # Create context with realistic browser fingerprint
            context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="Europe/Madrid",
                geolocation={"latitude": 41.3851, "longitude": 2.1734},
                permissions=["geolocation"],
            )

            page = await context.new_page()
            page.set_default_timeout(self.config.timeout_s * 1000)

            # Add stealth scripts to avoid detection
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'es'] });
                Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
            """
            )

            response = await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(3000)

            html = await page.content()
            if "captcha" in html.lower() or "datadome" in html.lower():
                logger.warning(f"Captcha detected on {url}, waiting longer...")
                await page.wait_for_timeout(5000)
                html = await page.content()

            # Scroll to load lazy content
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

            html = await page.content()
            status_code = response.status if response else None
            final_url = page.url

            await page.close()
            await context.close()

            elapsed = time.time() - start_time
            is_blocked = "captcha" in html.lower() or status_code == 403

            return PageFetchResult(
                ok=not is_blocked and (status_code is None or (200 <= status_code < 400)),
                url=url,
                final_url=final_url,
                status_code=status_code,
                html=html if not is_blocked else None,
                error="Blocked by anti-bot protection" if is_blocked else None,
                elapsed_s=elapsed,
            )

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Failed to fetch {url}: {e}")
            return PageFetchResult(
                ok=False,
                url=url,
                final_url=url,
                status_code=None,
                html=None,
                error=str(e),
                elapsed_s=elapsed,
            )

    async def fetch_listing_pages(
        self,
        *,
        city: str | None = None,
        country_code: str | None = None,
        max_pages: int | None = None,
    ) -> list[PageFetchResult]:
        """
        Fetch listing pages.

        Args:
            city: City to fetch (overrides config)
            country_code: Country code (overrides config)
            max_pages: Max pages to fetch (overrides config)

        Returns:
            List of PageFetchResult for each listing page
        """
        city = city or self.config.city
        country_code = country_code or self.config.country_code
        max_pages = max_pages if max_pages is not None else self.config.max_pages

        results = []

        for page_num in range(max_pages):
            url = f"{self.config.base_url}/{country_code}/{city}"
            if page_num > 0:
                url = f"{url}?week={page_num}"

            logger.info(f"Fetching listing page: {url}")

            result = await self._fetch_page(url)
            results.append(result)

            if result.ok:
                logger.info(f"Successfully fetched: {url} ({len(result.html or '')} chars)")
            else:
                logger.warning(f"Failed to fetch: {url} - {result.error}")

            await asyncio.sleep(self.config.min_delay_s)

        return results

    def extract_event_urls(self, html: str, base_url: str) -> list[str]:
        """
        Extract event URLs from listing page HTML.

        Args:
            html: HTML content
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute event URLs
        """
        if not html:
            return []

        matches = re.findall(self.config.url_pattern, html)

        urls = []
        seen = set()

        for match in matches:
            url = match.strip()

            if self.config.url_identifier and self.config.url_identifier not in url:
                continue

            parsed = urlparse(url)
            if not parsed.scheme:
                url = urljoin("https://ra.co", url)

            if url not in seen:
                seen.add(url)
                urls.append(url)

        logger.info(f"Extracted {len(urls)} event URLs")
        return urls

    async def fetch_event_pages(
        self,
        urls: list[str],
        *,
        max_events: int | None = None,
        concurrency: int = 5,
    ) -> list[PageFetchResult]:
        """
        Fetch event detail pages in parallel batches.

        Args:
            urls: List of event URLs
            max_events: Maximum events to fetch
            concurrency: Number of concurrent fetches per batch

        Returns:
            List of PageFetchResult for each event page
        """
        if max_events:
            urls = urls[:max_events]

        results = []

        # Process in batches of `concurrency`
        for i in range(0, len(urls), concurrency):
            batch = urls[i : i + concurrency]
            logger.info(f"Fetching event batch {i // concurrency + 1} ({len(batch)} URLs)")

            batch_results = await asyncio.gather(*[self._fetch_page(url) for url in batch])
            results.extend(batch_results)

            ok_count = sum(1 for r in batch_results if r.ok)
            logger.debug(f"Batch complete: {ok_count}/{len(batch)} successful")

            # Delay between batches (not between individual pages)
            if i + concurrency < len(urls):
                await asyncio.sleep(self.config.min_delay_s)

        logger.info(f"Fetched {len(results)} event pages, {sum(1 for r in results if r.ok)} successful")
        return results

    async def __aenter__(self) -> EventScraper:
        """Enter async context manager and return scraper instance."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and close browser."""
        await self.close()


# =============================================================================
# BASE SCRAPER PIPELINE
# =============================================================================


class BaseScraperPipeline(BasePipeline):
    """
    Abstract base class for scraper-based event pipelines.

    Extends BasePipeline with scraper-specific functionality using the
    ScraperAdapter. Subclasses must implement the HTML parsing logic.

    Architecture:
        BaseScraperPipeline -> ScraperAdapter -> EventScraper -> Playwright

    Subclasses must implement:
    - parse_event_html(): Parse HTML to intermediate dict
    - map_to_taxonomy(): Map to Human Experience Taxonomy
    - normalize_to_schema(): Convert to EventSchema
    - validate_event(): Validate event
    - enrich_event(): Add enrichment data

    Example:
        class RaCoScraperPipeline(BaseScraperPipeline):
            def parse_event_html(self, html: str, url: str) -> Dict[str, Any]:
                # Parse ra.co event page HTML
                ...
    """

    def __init__(
        self,
        config: PipelineConfig,
        scraper_config: ScraperConfig,
        html_parser: Callable[[str, str], dict] | None = None,
    ):
        """
        Initialize the scraper pipeline.

        Args:
            config: PipelineConfig for pipeline settings
            scraper_config: ScraperConfig for scraper settings
            html_parser: Optional custom HTML parser function
        """
        # Create ScraperAdapter from ScraperConfig
        adapter_config = ScraperAdapterConfig(
            source_id=scraper_config.source_id,
            source_type=SourceType.SCRAPER,
            base_url=scraper_config.base_url,
            url_pattern=scraper_config.url_pattern,
            url_identifier=scraper_config.url_identifier,
            max_pages=scraper_config.max_pages,
            timeout_s=scraper_config.timeout_s,
            min_delay_s=scraper_config.min_delay_s,
            headless=scraper_config.headless,
            city=scraper_config.city,
            country_code=scraper_config.country_code,
        )

        # Use provided html_parser or default to parse_event_html
        parser = html_parser or self._default_html_parser
        adapter = ScraperAdapter(adapter_config, html_parser=parser)

        super().__init__(config, adapter)
        self.scraper_config = scraper_config

    def _default_html_parser(self, html: str, url: str) -> dict[str, Any]:
        """
        Delegate to parse_event_html for HTML parsing.

        Override parse_event_html in subclasses for custom parsing.
        """
        return self.parse_event_html(html, url)

    @abstractmethod
    def parse_event_html(self, html: str, url: str) -> dict[str, Any]:
        """
        Parse event detail page HTML into intermediate format.

        Args:
            html: Raw HTML content of the event page
            url: URL of the event page

        Returns:
            Dictionary with extracted event fields
        """
        pass

    def parse_raw_event(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        """
        Parse raw event - already parsed by html_parser in adapter.

        Args:
            raw_event: Event dict from adapter (already parsed)

        Returns:
            Same event dict (no additional parsing needed)
        """
        return raw_event


# Backwards compatibility - FetchResult alias
FetchResult = PageFetchResult


__all__ = [
    # Data classes
    "PageFetchResult",
    "FetchResult",  # Alias for backwards compatibility
    "ScraperConfig",
    # Config loading
    "load_scraper_config",
    "load_event_scraper_config",  # Alias
    "get_config_path",
    "list_available_configs",
    "load_config_raw",
    # Scraper
    "EventScraper",
    # Pipeline
    "BaseScraperPipeline",
]
