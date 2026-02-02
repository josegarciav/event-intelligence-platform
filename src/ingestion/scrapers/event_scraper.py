"""
Event scraper.

Standalone scraper for fetching event pages using Playwright browser automation.
"""

from __future__ import annotations

import re
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of a page fetch."""
    ok: bool
    url: str
    final_url: str
    status_code: Optional[int]
    html: Optional[str]
    error: Optional[str] = None
    elapsed_s: float = 0.0


@dataclass
class ScraperConfig:
    """Configuration for the scraper."""
    source_id: str
    base_url: str
    url_pattern: str  # Regex pattern for extracting event URLs
    url_identifier: str  # URL fragment to identify event links
    max_pages: int = 5
    timeout_s: float = 30.0
    min_delay_s: float = 2.0
    headless: bool = True

    # URL template parameters
    city: str = "barcelona"
    country_code: str = "es"


class EventScraper:
    """
    Event scraper using Playwright for browser automation.

    Handles:
    - Fetching listing pages with pagination
    - Extracting event URLs from listing pages
    - Fetching individual event detail pages
    """

    def __init__(self, config: ScraperConfig):
        """
        Initialize the event scraper.

        Args:
            config: ScraperConfig instance
        """
        self.config = config
        self._browser = None
        self._playwright = None

    def _ensure_browser(self) -> None:
        """Ensure browser is started."""
        if self._browser is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "playwright is required for scraping. "
                "Install it with: pip install playwright && playwright install"
            )

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.config.headless)
        logger.info("Browser started")

    def close(self) -> None:
        """Close browser and release resources."""
        if self._browser:
            try:
                self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self._playwright = None

    def _fetch_page(self, url: str) -> FetchResult:
        """Fetch a single page."""
        self._ensure_browser()

        start_time = time.time()
        try:
            context = self._browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = context.new_page()
            page.set_default_timeout(self.config.timeout_s * 1000)

            response = page.goto(url, wait_until="domcontentloaded")

            # Wait a bit for dynamic content
            page.wait_for_timeout(2000)

            # Scroll to load lazy content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

            html = page.content()
            status_code = response.status if response else None
            final_url = page.url

            page.close()
            context.close()

            elapsed = time.time() - start_time

            return FetchResult(
                ok=status_code is None or (200 <= status_code < 400),
                url=url,
                final_url=final_url,
                status_code=status_code,
                html=html,
                elapsed_s=elapsed,
            )

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Failed to fetch {url}: {e}")
            return FetchResult(
                ok=False,
                url=url,
                final_url=url,
                status_code=None,
                html=None,
                error=str(e),
                elapsed_s=elapsed,
            )

    def fetch_listing_pages(
        self,
        *,
        city: Optional[str] = None,
        country_code: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> List[FetchResult]:
        """
        Fetch listing pages.

        Args:
            city: City to fetch (overrides config)
            country_code: Country code (overrides config)
            max_pages: Max pages to fetch (overrides config)

        Returns:
            List of FetchResult for each listing page
        """
        city = city or self.config.city
        country_code = country_code or self.config.country_code
        max_pages = max_pages if max_pages is not None else self.config.max_pages

        results = []

        for page_num in range(max_pages):
            # Build URL - ra.co uses week parameter
            url = f"{self.config.base_url}/{country_code}/{city}"
            if page_num > 0:
                url = f"{url}?week={page_num}"

            logger.info(f"Fetching listing page: {url}")

            result = self._fetch_page(url)
            results.append(result)

            if result.ok:
                logger.info(f"Successfully fetched: {url} ({len(result.html or '')} chars)")
            else:
                logger.warning(f"Failed to fetch: {url} - {result.error}")

            # Rate limiting
            time.sleep(self.config.min_delay_s)

        return results

    def extract_event_urls(self, html: str, base_url: str) -> List[str]:
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

        # Extract URLs using regex
        matches = re.findall(self.config.url_pattern, html)

        # Convert to absolute and dedupe
        urls = []
        seen = set()

        for match in matches:
            url = match.strip()

            # Skip if doesn't contain identifier
            if self.config.url_identifier and self.config.url_identifier not in url:
                continue

            # Convert relative to absolute
            parsed = urlparse(url)
            if not parsed.scheme:
                # Use ra.co as base
                url = urljoin("https://ra.co", url)

            if url not in seen:
                seen.add(url)
                urls.append(url)

        logger.info(f"Extracted {len(urls)} event URLs")
        return urls

    def fetch_event_pages(
        self,
        urls: List[str],
        *,
        max_events: Optional[int] = None,
    ) -> List[FetchResult]:
        """
        Fetch event detail pages.

        Args:
            urls: List of event URLs
            max_events: Maximum events to fetch

        Returns:
            List of FetchResult for each event page
        """
        if max_events:
            urls = urls[:max_events]

        results = []

        for url in urls:
            logger.info(f"Fetching event: {url}")

            result = self._fetch_page(url)
            results.append(result)

            if result.ok:
                logger.debug(f"Successfully fetched event: {url}")
            else:
                logger.warning(f"Failed to fetch event: {url} - {result.error}")

            # Rate limiting
            time.sleep(self.config.min_delay_s)

        logger.info(f"Fetched {len(results)} event pages, {sum(1 for r in results if r.ok)} successful")
        return results

    def __enter__(self) -> "EventScraper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
