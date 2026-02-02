"""
Base Scraper Pipeline.

Abstract base class for all scraper-based event pipelines, extending BasePipeline
with scraper-specific functionality.
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import logging

from src.ingestion.base_pipeline import BasePipeline, PipelineConfig
from src.ingestion.scrapers import EventScraper, ScraperConfig, FetchResult
from src.normalization.event_schema import EventSchema


logger = logging.getLogger(__name__)


class BaseScraperPipeline(BasePipeline):
    """
    Abstract base class for scraper-based event pipelines.

    Extends BasePipeline with scraper-specific functionality:
    - Manages EventScraper instance
    - Implements fetch_raw_data using scraper
    - Provides hooks for site-specific HTML parsing

    Subclasses must implement:
    - parse_event_page(): Parse HTML to intermediate dict
    - map_to_taxonomy(): Map to Human Experience Taxonomy
    - normalize_to_schema(): Convert to EventSchema
    - validate_event(): Validate event
    - enrich_event(): Add enrichment data
    """

    def __init__(
        self,
        config: PipelineConfig,
        scraper_config: ScraperConfig,
    ):
        """
        Initialize the scraper pipeline.

        Args:
            config: PipelineConfig for pipeline settings
            scraper_config: ScraperConfig for scraper settings
        """
        super().__init__(config)
        self.scraper_config = scraper_config
        self.scraper: Optional[EventScraper] = None

    def _init_scraper(self) -> None:
        """Initialize the scraper if not already done."""
        if self.scraper is None:
            self.scraper = EventScraper(self.scraper_config)

    def _close_scraper(self) -> None:
        """Close the scraper and release resources."""
        if self.scraper:
            self.scraper.close()
            self.scraper = None

    # ========================================================================
    # ABSTRACT METHODS - Must be implemented by subclasses
    # ========================================================================

    @abstractmethod
    def parse_event_page(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse event detail page HTML into intermediate format.

        Args:
            html: Raw HTML content of the event page
            url: URL of the event page

        Returns:
            Dictionary with extracted event fields
        """
        pass

    # ========================================================================
    # IMPLEMENTED METHODS - BasePipeline interface
    # ========================================================================

    def fetch_raw_data(
        self,
        *,
        city: Optional[str] = None,
        country_code: Optional[str] = None,
        max_pages: Optional[int] = None,
        max_events: Optional[int] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Fetch raw event data using the scraper.

        Workflow:
        1. Fetch listing pages
        2. Extract event URLs from listing pages
        3. Fetch event detail pages
        4. Parse each detail page to intermediate dict

        Args:
            city: City to filter events (e.g., "barcelona")
            country_code: Country code (e.g., "es")
            max_pages: Maximum listing pages to fetch
            max_events: Maximum events to return
            **kwargs: Additional parameters (unused)

        Returns:
            List of parsed event dictionaries
        """
        self._init_scraper()

        try:
            # Step 1: Fetch listing pages
            self.logger.info(f"Fetching listing pages (city={city}, country={country_code})")
            listing_results = self.scraper.fetch_listing_pages(
                city=city,
                country_code=country_code,
                max_pages=max_pages,
            )

            # Step 2: Extract event URLs from all listing pages
            all_event_urls = []
            for result in listing_results:
                if result.ok and result.html:
                    urls = self.scraper.extract_event_urls(result.html, result.url)
                    all_event_urls.extend(urls)

            # Dedupe URLs
            unique_urls = list(dict.fromkeys(all_event_urls))
            self.logger.info(f"Found {len(unique_urls)} unique event URLs")

            if max_events:
                unique_urls = unique_urls[:max_events]

            # Step 3: Fetch event detail pages
            event_results = self.scraper.fetch_event_pages(unique_urls, max_events=max_events)

            # Step 4: Parse each detail page
            parsed_events = []
            for result in event_results:
                if result.ok and result.html:
                    try:
                        parsed = self.parse_event_page(result.html, result.url)
                        parsed["_source_url"] = result.url
                        parsed["_fetch_url"] = result.final_url
                        parsed_events.append(parsed)
                    except Exception as e:
                        self.logger.warning(f"Failed to parse event {result.url}: {e}")
                else:
                    self.logger.warning(f"Failed to fetch event {result.url}: {result.error}")

            self.logger.info(f"Successfully parsed {len(parsed_events)} events")
            return parsed_events

        finally:
            self._close_scraper()

    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw event - for scrapers, this is already done in fetch_raw_data.

        Args:
            raw_event: Event dict from fetch_raw_data (already parsed)

        Returns:
            Same event dict (no additional parsing needed)
        """
        return raw_event

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def to_dataframe(self, events: List[EventSchema]):
        """
        Convert list of EventSchema to pandas DataFrame.

        Args:
            events: List of EventSchema instances

        Returns:
            pandas DataFrame with event data
        """
        import pandas as pd
        import json

        rows = []
        for event in events:
            # Get artists from custom_fields if available
            artists_list = event.custom_fields.get("artists", [])
            artists_str = ", ".join(
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in artists_list
            )

            # Format taxonomy dimensions as JSON
            taxonomy_json = json.dumps([
                {
                    "primary_category": dim.primary_category,
                    "subcategory": dim.subcategory,
                    "confidence": dim.confidence,
                }
                for dim in event.taxonomy_dimensions
            ])

            row = {
                "event_id": event.event_id,
                "title": event.title,
                "start_datetime": event.start_datetime,
                "end_datetime": event.end_datetime,
                "city": event.location.city,
                "country_code": event.location.country_code,
                "venue_name": event.location.venue_name,
                "artists": artists_str,
                "primary_category": event.primary_category,
                "taxonomy": taxonomy_json,
                "format": event.format.value if event.format else None,
                "is_free": event.price.is_free if event.price else None,
                "min_price": float(event.price.minimum_price) if event.price and event.price.minimum_price else None,
                "max_price": float(event.price.maximum_price) if event.price and event.price.maximum_price else None,
                "currency_code": event.price.currency if event.price else None,
                "organizer": event.organizer.name if event.organizer else None,
                "source_url": event.source.source_url if event.source else None,
                "data_quality_score": event.data_quality_score,
            }
            rows.append(row)

        return pd.DataFrame(rows)
