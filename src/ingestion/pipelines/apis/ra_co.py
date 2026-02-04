"""
Ra.co Event Pipeline.

API-based pipeline for ingesting events from ra.co using their GraphQL API.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import logging
import uuid

from src.ingestion.base_pipeline import BasePipeline, PipelineConfig
from src.ingestion.adapters import APIAdapter, SourceType, FetchResult
from src.ingestion.adapters.api_adapter import APIAdapterConfig
from src.schemas.event import (
    EventSchema,
    EventType,
    EventFormat,
    LocationInfo,
    PriceInfo,
    TicketInfo,
    OrganizerInfo,
    SourceInfo,
    TaxonomyDimension,
    PrimaryCategory,
    Subcategory,
)
from src.ingestion.normalization.currency import CurrencyParser
from src.ingestion.normalization.feature_extractor import (
    FeatureExtractor,
    create_feature_extractor_from_config,
)

logger = logging.getLogger(__name__)


# GraphQL query for fetching events with pagination
EVENTS_QUERY = """
query GetEvents($filters: FilterInputDtoInput, $pageSize: Int, $page: Int) {
  eventListings(filters: $filters, pageSize: $pageSize, page: $page) {
    data {
      id
      event {
        id
        title
        content
        date
        startTime
        endTime
        venue {
          name
          address
          area {
            name
            country {
              name
              urlCode
            }
          }
        }
        artists {
          name
        }
        images {
          filename
        }
        cost
        contentUrl
      }
    }
    totalResults
  }
}
"""


class RaCoAdapter(APIAdapter):
    """
    Custom adapter for ra.co GraphQL API.

    Handles query building and response parsing specific to ra.co.
    """

    def __init__(self, config: APIAdapterConfig):
        super().__init__(
            config,
            query_builder=self._build_query,
            response_parser=self._parse_response,
        )

    def _build_query(
        self,
        area_id: int = 20,
        page_size: int = 50,
        page: int = 1,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Build GraphQL query for ra.co events."""
        if date_from is None:
            date_from = datetime.now().strftime("%Y-%m-%d")
        if date_to is None:
            date_to = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        return {
            "query": EVENTS_QUERY,
            "variables": {
                "filters": {
                    "areas": {"eq": area_id},
                    "listingDate": {
                        "gte": date_from,
                        "lte": date_to,
                    },
                },
                "pageSize": page_size,
                "page": page,
            },
        }

    def fetch(self, **kwargs) -> FetchResult:
        """
        Fetch data from ra.co API with pagination.

        Loops through pages until no more results or max_pages reached.

        Args:
            **kwargs: Parameters passed to query_builder
                - area_id: Ra.co area ID (default 20 = Barcelona)
                - page_size: Events per page (default 50, max 100)
                - max_pages: Maximum pages to fetch (default 10)
                - date_from: Start date filter
                - date_to: End date filter

        Returns:
            FetchResult with all events from all pages
        """
        all_events = []
        page = 1
        max_pages = kwargs.pop("max_pages", 10)
        page_size = kwargs.get("page_size", 50)
        errors = []
        total_results = 0

        fetch_started = datetime.now(timezone.utc)

        while page <= max_pages:
            logger.info(f"Fetching page {page}/{max_pages}...")

            # Fetch single page using parent class
            result = super().fetch(page=page, **kwargs)

            if not result.success or not result.raw_data:
                if result.errors:
                    errors.extend(result.errors)
                break

            all_events.extend(result.raw_data)

            # Get total results from metadata
            if result.metadata.get("total_available"):
                total_results = result.metadata["total_available"]

            # Check if we've fetched all available events
            if len(result.raw_data) < page_size:
                logger.info(
                    f"Received {len(result.raw_data)} events (less than page_size), stopping pagination"
                )
                break

            # Check if we've reached total available
            if total_results > 0 and len(all_events) >= total_results:
                logger.info(f"Fetched all {total_results} available events")
                break

            page += 1

        logger.info(
            f"Pagination complete: fetched {len(all_events)} total events across {page} pages"
        )

        return FetchResult(
            success=len(all_events) > 0,
            source_type=SourceType.API,
            raw_data=all_events,
            total_fetched=len(all_events),
            errors=errors,
            metadata={
                "pages_fetched": page,
                "total_available": total_results,
                "max_pages": max_pages,
            },
            fetch_started_at=fetch_started,
            fetch_ended_at=datetime.now(timezone.utc),
        )

    def _parse_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse ra.co GraphQL response to event list."""
        if "errors" in response:
            logger.error(f"GraphQL errors: {response['errors']}")
            return []

        try:
            listings = response.get("data", {}).get("eventListings", {})
            data = listings.get("data", [])

            events = []
            for listing in data:
                event = listing.get("event", {})
                if event:
                    event["_listing_id"] = listing.get("id")
                    events.append(event)

            logger.info(f"Parsed {len(events)} events from response")
            return events

        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return []


class RaCoPipeline(BasePipeline):
    """
    Pipeline for ra.co events.

    Uses GraphQL API to fetch electronic music events.
    Serves as a reference implementation for custom pipelines.
    """

    def __init__(
        self,
        config: PipelineConfig,
        adapter: RaCoAdapter,
        feature_extractor: Optional[FeatureExtractor] = None,
    ):
        super().__init__(config, adapter)
        self.feature_extractor = feature_extractor

    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw GraphQL event to intermediate format."""
        venue = raw_event.get("venue", {}) or {}
        area = venue.get("area", {}) or {}
        country = area.get("country", {}) or {}

        artists = raw_event.get("artists", []) or []
        artist_names = [a.get("name") for a in artists if a.get("name")]

        images = raw_event.get("images", []) or []
        image_url = None
        if images:
            filename = images[0].get("filename")
            if filename:
                image_url = f"https://ra.co/images/events/flyer/{filename}"

        # Extract description from content field (may contain HTML)
        description = raw_event.get("content")
        if description:
            # Clean basic HTML tags if present
            import re

            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()

        return {
            "source_event_id": raw_event.get("id"),
            "title": raw_event.get("title"),
            "description": description,
            "date": raw_event.get("date"),
            "start_time": raw_event.get("startTime"),
            "end_time": raw_event.get("endTime"),
            "venue_name": venue.get("name"),
            "venue_address": venue.get("address"),
            "city": area.get("name"),
            "country_name": country.get("name"),
            "country_code": country.get("urlCode"),
            "artists": artist_names,
            "cost": raw_event.get("cost"),
            "content_url": raw_event.get("contentUrl"),
            "image_url": image_url,
        }

    def map_to_taxonomy(
        self, parsed_event: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Map ra.co event to Human Experience Taxonomy.

        Ra.co events are electronic music events, mapping to:
        - PLAY_AND_FUN (ID: 1) -> Music & Rhythm Play (1.4)
        - SOCIAL_CONNECTION (ID: 5) -> Shared Activities (5.7)

        Uses numeric ID format for primary categories.
        """
        title_lower = (parsed_event.get("title") or "").lower()

        # Use numeric ID format - PrimaryCategory.from_id("1") = play_and_fun
        primary_category = PrimaryCategory.from_id("1").value

        # Get subcategory names for richer output
        sub_1_4 = Subcategory.get_by_id("1.4")
        sub_5_7 = Subcategory.get_by_id("5.7")

        taxonomy_dimensions = [
            {
                "primary_category": PrimaryCategory.from_id("1").value,  # play_and_fun
                "subcategory": "1.4",  # Music & Rhythm Play
                "subcategory_name": sub_1_4.get("name") if sub_1_4 else None,
                "values": ["expression", "energy", "flow", "rhythm"],
                "confidence": 0.95,
            },
            {
                "primary_category": PrimaryCategory.from_id(
                    "5"
                ).value,  # social_connection
                "subcategory": "5.7",  # Shared Activities
                "subcategory_name": sub_5_7.get("name") if sub_5_7 else None,
                "values": ["connection", "belonging", "shared joy"],
                "confidence": 0.8,
            },
        ]

        # Add exploration dimension for festivals
        if any(word in title_lower for word in ["festival", "carnival", "outdoor"]):
            sub_2_4 = Subcategory.get_by_id("2.4")
            taxonomy_dimensions.append(
                {
                    "primary_category": PrimaryCategory.from_id(
                        "2"
                    ).value,  # exploration_and_adventure
                    "subcategory": "2.4",
                    "subcategory_name": sub_2_4.get("name") if sub_2_4 else None,
                    "values": ["curiosity", "discovery"],
                    "confidence": 0.65,
                }
            )

        # Add learning dimension for workshops
        if any(word in title_lower for word in ["workshop", "masterclass", "talk"]):
            sub_4_2 = Subcategory.get_by_id("4.2")
            taxonomy_dimensions.append(
                {
                    "primary_category": PrimaryCategory.from_id(
                        "4"
                    ).value,  # learning_and_intellectual
                    "subcategory": "4.2",
                    "subcategory_name": sub_4_2.get("name") if sub_4_2 else None,
                    "values": ["growth", "mastery"],
                    "confidence": 0.7,
                }
            )

        return primary_category, taxonomy_dimensions

    def normalize_to_schema(
        self,
        parsed_event: Dict[str, Any],
        primary_cat: str,
        taxonomy_dims: List[Dict[str, Any]],
    ) -> EventSchema:
        """Normalize parsed event to EventSchema."""
        source_event_id = str(parsed_event.get("source_event_id", ""))

        # Generate platform UUID for event_id (source ID lives in source_event_id)
        event_id = str(uuid.uuid4())

        # Parse dates
        start_dt = self._parse_datetime(
            parsed_event.get("start_time") or parsed_event.get("date")
        )
        end_dt = self._parse_datetime(parsed_event.get("end_time"))

        # Location
        location = LocationInfo(
            venue_name=parsed_event.get("venue_name"),
            street_address=parsed_event.get("venue_address"),
            city=parsed_event.get("city", "Barcelona"),
            country_code=parsed_event.get("country_code", "ES"),
            coordinates=None,
        )

        # Price
        price_str = parsed_event.get("cost") or ""
        min_price, max_price, currency = CurrencyParser.parse_price_string(
            str(price_str)
        )

        is_free = (min_price is None and max_price is None) or str(
            price_str
        ).lower() in ["free", "0", "gratis"]

        price = PriceInfo(
            currency=currency or "EUR",
            is_free=is_free,
            minimum_price=min_price,
            maximum_price=max_price,
            price_raw_text=str(price_str),
        )

        # Organizer
        organizer = OrganizerInfo(
            name=parsed_event.get("venue_name") or "Unknown Venue",
        )

        # Source
        content_url = parsed_event.get("content_url", "")
        source_url = f"https://ra.co{content_url}" if content_url else ""
        source = SourceInfo(
            source_name="ra_co",
            source_event_id=source_event_id,
            source_url=source_url,
            last_updated_from_source=datetime.now(timezone.utc),
        )

        # Ticket info - ra.co events link to their event page for tickets
        ticket_info = TicketInfo(
            url=f"{source_url}/tickets" if source_url else None,
            is_sold_out=False,  # Not available from ra.co API
        )

        # Taxonomy dimensions with expanded fields
        taxonomy_objs = [
            TaxonomyDimension(
                primary_category=dim["primary_category"],
                subcategory=dim.get("subcategory"),
                subcategory_name=dim.get("subcategory_name"),
                values=dim.get("values", []),
                confidence=dim.get("confidence", 0.5),
            )
            for dim in taxonomy_dims
        ]

        # Enrich taxonomy dimensions with activity-level fields using FeatureExtractor
        if self.feature_extractor:
            enriched_dims = []
            for dim in taxonomy_objs:
                try:
                    enriched = self.feature_extractor.enrich_taxonomy_dimension(
                        dim, parsed_event
                    )
                    enriched_dims.append(enriched)
                except Exception as e:
                    logger.warning(f"Failed to enrich taxonomy dimension: {e}")
                    enriched_dims.append(dim)
            taxonomy_objs = enriched_dims

        # Event type
        title_lower = (parsed_event.get("title") or "").lower()
        if "festival" in title_lower:
            event_type = EventType.FESTIVAL
        elif "party" in title_lower:
            event_type = EventType.PARTY
        elif "live" in title_lower:
            event_type = EventType.CONCERT
        else:
            event_type = EventType.NIGHTLIFE

        return EventSchema(
            event_id=event_id,
            title=parsed_event.get("title", "Untitled Event"),
            description=parsed_event.get("description"),
            primary_category=PrimaryCategory(primary_cat),
            taxonomy_dimensions=taxonomy_objs,
            start_datetime=start_dt,
            end_datetime=end_dt,
            location=location,
            event_type=event_type,
            format=EventFormat.IN_PERSON,
            price=price,
            ticket_info=ticket_info,
            organizer=organizer,
            image_url=parsed_event.get("image_url"),
            source=source,
            tags=[],
            custom_fields={
                "artists": parsed_event.get("artists", []),
            },
        )

    def _parse_datetime(self, dt_value: Any) -> datetime:
        """Parse datetime from various formats. Always returns timezone-aware datetime."""
        if not dt_value:
            return datetime.now(timezone.utc)

        if isinstance(dt_value, datetime):
            # Ensure timezone-aware
            if dt_value.tzinfo is None:
                return dt_value.replace(tzinfo=timezone.utc)
            return dt_value

        if isinstance(dt_value, str):
            # Handle ISO format with T separator
            try:
                if "T" in dt_value:
                    # Remove milliseconds and timezone
                    clean = dt_value.split(".")[0]
                    parsed = datetime.fromisoformat(clean)
                    return (
                        parsed.replace(tzinfo=timezone.utc)
                        if parsed.tzinfo is None
                        else parsed
                    )
                parsed = datetime.fromisoformat(dt_value)
                return (
                    parsed.replace(tzinfo=timezone.utc)
                    if parsed.tzinfo is None
                    else parsed
                )
            except ValueError:
                pass

            # Try common formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                try:
                    parsed = datetime.strptime(dt_value, fmt)
                    return parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

        logger.warning(f"Could not parse datetime: {dt_value}")
        return datetime.now(timezone.utc)

    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """Validate ra.co event."""
        errors = []

        if not event.title or event.title == "Untitled Event":
            errors.append("Title is required")

        if not event.location.city:
            errors.append("City is required")

        if event.start_datetime < datetime.now(timezone.utc):
            errors.append("Warning: Event start time is in the past")

        if event.price.minimum_price and event.price.minimum_price < 0:
            errors.append("Minimum price cannot be negative")

        is_valid = not any("Error:" in e for e in errors)
        return is_valid, errors

    def enrich_event(self, event: EventSchema) -> EventSchema:
        """Enrich event with additional data."""
        # Calculate duration
        if event.end_datetime and event.start_datetime:
            duration = (event.end_datetime - event.start_datetime).total_seconds() / 60
            event.duration_minutes = int(duration)

        # Set timezone based on city
        city_timezones = {
            "barcelona": "Europe/Madrid",
            "madrid": "Europe/Madrid",
            "london": "Europe/London",
            "berlin": "Europe/Berlin",
            "amsterdam": "Europe/Amsterdam",
            "paris": "Europe/Paris",
        }
        city_lower = (event.location.city or "").lower()
        if city_lower in city_timezones:
            event.location.timezone = city_timezones[city_lower]

        return event


def create_ra_co_pipeline(
    pipeline_config: PipelineConfig, source_config: Dict[str, Any]
) -> RaCoPipeline:
    """
    Factory function to create a configured ra.co pipeline.

    Args:
        pipeline_config: Pipeline configuration
        source_config: Source-specific configuration from YAML

    Returns:
        Configured RaCoPipeline instance
    """
    adapter_config = APIAdapterConfig(
        source_id="ra_co",
        source_type=SourceType.API,
        request_timeout=source_config.get("request_timeout", 30),
        max_retries=source_config.get("max_retries", 3),
        rate_limit_per_second=source_config.get("rate_limit_per_second", 1.0),
        graphql_endpoint=source_config.get("graphql_endpoint", "https://ra.co/graphql"),
    )

    adapter = RaCoAdapter(adapter_config)

    # Create feature extractor if enabled in config
    feature_extractor = None
    feature_extraction_config = source_config.get("feature_extraction", {})
    if feature_extraction_config.get("enabled"):
        feature_extractor = create_feature_extractor_from_config(
            feature_extraction_config
        )

    return RaCoPipeline(pipeline_config, adapter, feature_extractor)
