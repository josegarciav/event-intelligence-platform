"""
Ra.co Scraper Pipeline.

Scraper-based pipeline for ingesting events from ra.co electronic music platform.
"""

from typing import Any, Dict, List, Tuple
from datetime import datetime
import logging

from src.ingestion.base_pipeline import PipelineConfig
from src.ingestion.pipelines.scrapers.base_scraper_pipeline import BaseScraperPipeline
from src.ingestion.scrapers import ScraperConfig
from src.ingestion.parsers.ra_co_parser import RaCoEventParser
from src.normalization.event_schema import (
    EventSchema,
    EventType,
    EventFormat,
    LocationInfo,
    PriceInfo,
    OrganizerInfo,
    SourceInfo,
    TaxonomyDimension,
    PrimaryCategory,
)
from src.normalization.currency import CurrencyParser


logger = logging.getLogger(__name__)


class RaCoScraperPipeline(BaseScraperPipeline):
    """
    Scraper pipeline for ra.co events.

    Uses BeautifulSoup to parse ra.co event pages and extract event data.
    """

    def __init__(
        self,
        config: PipelineConfig,
        scraper_config: ScraperConfig,
    ):
        """
        Initialize the ra.co scraper pipeline.

        Args:
            config: PipelineConfig for pipeline settings
            scraper_config: ScraperConfig for scraper settings
        """
        super().__init__(config, scraper_config)
        self.parser = RaCoEventParser()

    # ========================================================================
    # STEP 1: PARSE EVENT PAGE (scraper-specific)
    # ========================================================================

    def parse_event_page(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse ra.co event page HTML.

        Args:
            html: Raw HTML content
            url: URL of the event page

        Returns:
            Dictionary with extracted event fields
        """
        return self.parser.parse(html, url)

    # ========================================================================
    # STEP 2: TAXONOMY MAPPING
    # ========================================================================

    def map_to_taxonomy(
        self, parsed_event: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Map ra.co event to Human Experience Taxonomy.

        Ra.co events are primarily electronic music events, mapping to:
        - PLAY_AND_FUN → Music & Rhythm Play (1.4)
        - SOCIAL_CONNECTION → Shared Activities (5.7)
        """
        title_lower = (parsed_event.get("title", "") or "").lower()

        primary_category = PrimaryCategory.PLAY_AND_FUN.value

        taxonomy_dimensions = [
            {
                "primary_category": PrimaryCategory.PLAY_AND_FUN.value,
                "subcategory": "1.4",  # Music & Rhythm Play
                "values": ["expression", "energy", "flow", "rhythm"],
                "confidence": 0.95,
            },
            {
                "primary_category": PrimaryCategory.SOCIAL_CONNECTION.value,
                "subcategory": "5.7",  # Shared Activities & Co-Experience
                "values": ["connection", "belonging", "shared joy"],
                "confidence": 0.8,
            },
        ]

        if any(word in title_lower for word in ["festival", "carnival", "outdoor"]):
            taxonomy_dimensions.append({
                "primary_category": PrimaryCategory.EXPLORATION_AND_ADVENTURE.value,
                "subcategory": "2.4",
                "values": ["curiosity", "perspective shift", "discovery"],
                "confidence": 0.65,
            })

        if any(word in title_lower for word in ["workshop", "masterclass", "talk", "lecture"]):
            taxonomy_dimensions.append({
                "primary_category": PrimaryCategory.LEARNING_AND_INTELLECTUAL.value,
                "subcategory": "4.2",
                "values": ["growth", "mastery", "skill development"],
                "confidence": 0.7,
            })

        return primary_category, taxonomy_dimensions

    # ========================================================================
    # STEP 3: NORMALIZE TO SCHEMA
    # ========================================================================

    def normalize_to_schema(
        self,
        parsed_event: Dict[str, Any],
        primary_cat: str,
        taxonomy_dims: List[Dict[str, Any]],
    ) -> EventSchema:
        """
        Normalize parsed event to canonical EventSchema.
        """
        source_event_id = parsed_event.get("source_event_id", "")
        event_id = f"ra_co_{source_event_id}" if source_event_id else f"ra_co_{hash(parsed_event.get('title', ''))}"

        start_dt = self._parse_datetime(parsed_event.get("start_datetime"))
        end_dt = self._parse_datetime(parsed_event.get("end_datetime"))

        location = LocationInfo(
            venue_name=parsed_event.get("venue_name"),
            street_address=parsed_event.get("venue_address"),
            city=parsed_event.get("city") or self.scraper_config.city.title(),
            country_code=parsed_event.get("country_code") or self.scraper_config.country_code.upper(),
            coordinates=None,
        )

        # Parse price
        price_str = parsed_event.get("price", "")
        min_price, max_price, currency = CurrencyParser.parse_price_string(price_str)
        is_free = min_price is None and max_price is None and not price_str.strip()

        if not currency:
            currency = "EUR"

        price = PriceInfo(
            currency=currency,
            is_free=is_free or (price_str.lower() in ["free", "gratis", "entrada libre"]),
            minimum_price=min_price,
            maximum_price=max_price,
            price_raw_text=price_str,
        )

        organizer = OrganizerInfo(
            name=parsed_event.get("venue_name") or "Unknown Venue",
        )

        source_url = parsed_event.get("_source_url") or parsed_event.get("source_url", "")
        source = SourceInfo(
            source_name="ra_co",
            source_event_id=source_event_id,
            source_url=source_url,
            last_updated_from_source=datetime.utcnow(),
        )

        taxonomy_dims_objs = [
            TaxonomyDimension(
                primary_category=dim["primary_category"],
                subcategory=dim.get("subcategory"),
                values=dim.get("values", []),
                confidence=dim.get("confidence", 0.5),
            )
            for dim in taxonomy_dims
        ]

        title_lower = (parsed_event.get("title", "") or "").lower()
        if "festival" in title_lower:
            event_type = EventType.FESTIVAL
        elif "party" in title_lower:
            event_type = EventType.PARTY
        elif "live" in title_lower:
            event_type = EventType.CONCERT
        else:
            event_type = EventType.NIGHTLIFE

        event = EventSchema(
            event_id=event_id,
            title=parsed_event.get("title", "Untitled Event"),
            description=parsed_event.get("description"),
            primary_category=primary_cat,
            taxonomy_dimensions=taxonomy_dims_objs,
            start_datetime=start_dt,
            end_datetime=end_dt,
            location=location,
            event_type=event_type,
            format=EventFormat.IN_PERSON,
            price=price,
            organizer=organizer,
            image_url=parsed_event.get("image_url"),
            source=source,
            tags=parsed_event.get("genres", []),
            custom_fields={
                "artists": parsed_event.get("artists", []),
                "genres": parsed_event.get("genres", []),
            },
        )

        return event

    def _parse_datetime(self, dt_value) -> datetime:
        """Parse datetime from various formats."""
        if not dt_value:
            return datetime.utcnow()

        if isinstance(dt_value, datetime):
            return dt_value

        if isinstance(dt_value, str):
            try:
                if dt_value.endswith("Z"):
                    return datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
                return datetime.fromisoformat(dt_value)
            except (ValueError, AttributeError):
                pass

            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%dT%H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d %b %Y %H:%M",
            ]:
                try:
                    return datetime.strptime(dt_value, fmt)
                except ValueError:
                    continue

        logger.warning(f"Could not parse datetime: {dt_value}")
        return datetime.utcnow()

    # ========================================================================
    # STEP 4: VALIDATION
    # ========================================================================

    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """Validate ra.co event with source-specific rules."""
        errors = []

        if not event.location.city or event.location.city == "Unknown":
            errors.append("Location: City is required")

        if event.start_datetime < datetime.utcnow():
            errors.append("Warning: Event start time is in the past")

        if event.price.minimum_price and event.price.minimum_price < 0:
            errors.append("Minimum price cannot be negative")

        if not event.title or event.title == "Untitled Event":
            errors.append("Title is required")

        is_valid = not any("Error:" in e for e in errors)
        return is_valid, errors

    # ========================================================================
    # STEP 5: ENRICHMENT
    # ========================================================================

    def enrich_event(self, event: EventSchema) -> EventSchema:
        """Enrich event with additional data."""
        if event.end_datetime and event.start_datetime:
            duration = (event.end_datetime - event.start_datetime).total_seconds() / 60
            event.duration_minutes = int(duration)

        city_timezones = {
            "barcelona": "Europe/Madrid",
            "madrid": "Europe/Madrid",
            "london": "Europe/London",
            "berlin": "Europe/Berlin",
            "amsterdam": "Europe/Amsterdam",
            "paris": "Europe/Paris",
            "new york": "America/New_York",
            "los angeles": "America/Los_Angeles",
        }
        city_lower = (event.location.city or "").lower()
        if city_lower in city_timezones:
            event.location.timezone = city_timezones[city_lower]

        return event
