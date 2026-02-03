"""
Scraper Source Adapter.

Adapter for fetching data from web scraping sources using Playwright.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import logging

from .base_adapter import BaseSourceAdapter, AdapterConfig, FetchResult, SourceType


logger = logging.getLogger(__name__)


@dataclass
class ScraperAdapterConfig(AdapterConfig):
    """
    Configuration for scraper-based adapters.
    """
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
        return self.config

    def _validate_config(self) -> None:
        """Validate scraper configuration."""
        if not self.scraper_config.base_url:
            raise ValueError("Scraper adapter requires base_url")

    def _get_scraper(self):
        """Get or create scraper instance."""
        if self._scraper is None:
            from src.ingestion.pipelines.scrapers import EventScraper, ScraperConfig

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
        fetch_started = datetime.utcnow()
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
            fetch_ended_at=datetime.utcnow(),
        )

    def close(self) -> None:
        """Close scraper and release browser resources."""
        if self._scraper:
            self._scraper.close()
            self._scraper = None
