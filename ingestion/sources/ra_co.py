"""
Ra.co Event Pipeline Implementation.

Ra.co is a premier electronic music platform providing data on DJ sets, live performances,
and electronic music events. This pipeline integrates ra.co's GraphQL API to ingest
events and normalize them into the canonical event schema.

Ra.co events typically map to:
- Primary Category: PLAY_AND_FUN (music & entertainment) + SOCIAL_CONNECTION
- Subcategories: MUSIC_AND_RHYTHM_PLAY, SOCIAL_FUN, URBAN_ADVENTURE (club venues)
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import requests
from decimal import Decimal

from ingestion.base_pipeline import BasePipeline, PipelineConfig
from normalization.event_schema import (
    EventSchema,
    EventType,
    LocationInfo,
    Coordinates,
    PriceInfo,
    TicketInfo,
    OrganizerInfo,
    SourceInfo,
    MediaAsset,
    EngagementMetrics,
    TaxonomyDimension,
    PrimaryCategory,
    Subcategory,
    EventFormat,
)


class RaCoEventPipeline(BasePipeline):
    """
    Pipeline for ingesting events from ra.co (electronic music platform).

    Ra.co provides a GraphQL API for querying electronic music events,
    venues, artists, and related metadata.
    """

    # GraphQL query templates
    # Note: Ra.co API uses EventQueryType enum (PICKS, TODAY, FROMDATE, LATEST, PREVIOUS, ARCHIVE)
    # and returns Event objects directly, not wrapped in edges/pageInfo structure
    EVENTS_QUERY = """
    query GetEvents($type: EventQueryType!, $limit: Int!) {
        events(type: $type, limit: $limit) {
            id
            title
            date
            startTime
            endTime
            cost
            artists {
                id
                name
            }
            venue {
                id
                name
                address
                area {
                    name
                }
                country {
                    name
                    urlCode
                }
            }
            genres {
                id
                name
            }
            attending
            isInterested
            flyerFront
            content
            minimumAge
            isTicketed
            isMultiDayEvent
            isFestival
            images {
                id
            }
        }
    }
    """

    def __init__(self, config: PipelineConfig):
        """Initialize Ra.co pipeline with config."""
        super().__init__(config)
        self.base_url = config.base_url or "https://ra.co/graphql"
        self.session = requests.Session()
        # Ra.co requires User-Agent header and Content-Type
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            }
        )
        self.event_type = "PICKS"  # Default event type: PICKS, TODAY, FROMDATE, LATEST, PREVIOUS, ARCHIVE
        self.limit = 100  # Events per request

    # ========================================================================
    # STEP 1: FETCH
    # ========================================================================

    def fetch_raw_data(
        self, cities: Optional[List[str]] = None, days_ahead: int = 90, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch events from ra.co GraphQL API.

        Args:
            cities: List of cities to filter by (optional, not supported by ra.co API)
            days_ahead: Number of days into the future (optional)
            **kwargs: Additional parameters

        Returns:
            List of raw event data from ra.co
        """
        all_events = []

        try:
            # Ra.co API requires type parameter (PICKS, TODAY, FROMDATE, LATEST, PREVIOUS, ARCHIVE)
            variables = {"type": self.event_type, "limit": self.limit}

            response = self._graphql_request(self.EVENTS_QUERY, variables)

            if response.get("errors"):
                self.logger.error(f"GraphQL error: {response['errors']}")
                return all_events

            events_data = response.get("data", {}).get("events", [])

            # Ra.co returns events as a direct list, not wrapped in edges
            all_events = events_data if isinstance(events_data, list) else []

            self.logger.info(f"Fetched {len(all_events)} events from ra.co")

        except Exception as e:
            self.logger.error(f"Failed to fetch data from ra.co: {e}", exc_info=True)
            raise

        return all_events

    def _graphql_request(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute GraphQL request to ra.co API."""
        payload = {"query": query, "variables": variables}

        retry_count = 0
        while retry_count < self.config.max_retries:
            try:
                response = self.session.post(
                    self.base_url, json=payload, timeout=self.config.request_timeout
                )
                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                if not self.handle_api_error(e, retry_count):
                    raise
                retry_count += 1

        raise Exception("Max retries exceeded for GraphQL request")

    # ========================================================================
    # STEP 2: PARSE
    # ========================================================================

    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw ra.co event into intermediate structured format.

        Extracts and cleans all relevant fields from the raw event response.
        """
        try:
            venue = raw_event.get("venue", {}) or {}
            artists = []

            # Parse artists - ra.co returns artists as direct list, not wrapped in edges
            for artist in raw_event.get("artists", []):
                if artist and artist.get("name"):
                    artists.append(
                        {
                            "name": artist["name"],
                            "id": artist.get("id"),
                        }
                    )

            # Parse genres
            genres = []
            for genre in raw_event.get("genres", []):
                if genre and genre.get("name"):
                    genres.append(genre["name"])

            # Parse images - ra.co returns images as direct list
            image_url = None
            if raw_event.get("images"):
                for img in raw_event["images"]:
                    if img.get("url"):
                        image_url = img["url"]
                        break

            # Fall back to flyerFront if available
            if not image_url:
                image_url = raw_event.get("flyerFront")

            parsed = {
                "source_event_id": raw_event.get("id"),
                "title": raw_event.get("title", "").strip(),
                "description": raw_event.get("content", "").strip(),
                "source_url": f"https://ra.co/en/events/{raw_event.get('id')}",
                # Timing
                "start_datetime": raw_event.get("startTime"),
                "end_datetime": raw_event.get("endTime"),
                "date": raw_event.get("date"),
                # Location
                "venue_name": venue.get("name"),
                "venue_id": venue.get("id"),
                "area": (
                    venue.get("area", {}).get("name") if venue.get("area") else None
                ),
                "country": (
                    venue.get("country", {}).get("name")
                    if venue.get("country")
                    else None
                ),
                "country_code": (
                    venue.get("country", {}).get("urlCode")
                    if venue.get("country")
                    else "GB"
                ),
                "address": venue.get("address"),
                # Pricing & Details
                "cost": raw_event.get("cost"),
                "minimum_age": raw_event.get("minimumAge"),
                "is_ticketed": raw_event.get("isTicketed", False),
                "is_festival": raw_event.get("isFestival", False),
                "is_multi_day": raw_event.get("isMultiDayEvent", False),
                # Media
                "image_url": image_url,
                # Content
                "artists": artists,
                "genres": genres,
                # Engagement
                "attending": raw_event.get("attending", 0),
                "interested": raw_event.get("isInterested", False),
            }

            return parsed

        except Exception as e:
            self.logger.error(f"Failed to parse event: {e}", exc_info=True)
            raise ValueError(f"Failed to parse ra.co event: {e}")

    # ========================================================================
    # STEP 3: TAXONOMY MAPPING
    # ========================================================================

    def map_to_taxonomy(
        self, parsed_event: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Map ra.co event to Human Experience Taxonomy.

        Ra.co events typically involve:
        - Music listening/dancing (PLAY_AND_FUN → MUSIC_AND_RHYTHM)
        - Social interaction (SOCIAL_CONNECTION → SHARED_ACTIVITIES)
        - Urban exploration (optional, for venue discovery)
        """
        # Analyze event content
        title_lower = (parsed_event.get("title", "") or "").lower()
        artists = parsed_event.get("artists", [])

        primary_category = PrimaryCategory.PLAY_AND_FUN.value

        taxonomy_dimensions = [
            {
                "primary_category": PrimaryCategory.PLAY_AND_FUN.value,
                "subcategory": Subcategory.MUSIC_AND_RHYTHM.value,
                "values": ["expression", "energy", "flow", "rhythm"],
                "confidence": 0.95,  # Very high confidence for music events
            },
            {
                "primary_category": PrimaryCategory.SOCIAL_CONNECTION.value,
                "subcategory": Subcategory.SHARED_ACTIVITIES.value,
                "values": ["connection", "belonging", "shared joy"],
                "confidence": 0.8,
            },
        ]

        # Additional taxonomy if content suggests certain types
        if any(word in title_lower for word in ["festival", "carnival", "exhibition"]):
            taxonomy_dimensions.append(
                {
                    "primary_category": PrimaryCategory.EXPLORATION_AND_ADVENTURE.value,
                    "subcategory": Subcategory.CULTURAL_DISCOVERY.value,
                    "values": ["curiosity", "perspective shift"],
                    "confidence": 0.65,
                }
            )

        if any(word in title_lower for word in ["workshop", "masterclass", "talk"]):
            taxonomy_dimensions.append(
                {
                    "primary_category": PrimaryCategory.LEARNING_AND_INTELLECTUAL.value,
                    "subcategory": Subcategory.LEARNING_NEW_SKILLS.value,
                    "values": ["growth", "mastery"],
                    "confidence": 0.7,
                }
            )

        return primary_category, taxonomy_dimensions

    # ========================================================================
    # STEP 4: NORMALIZE TO SCHEMA
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
        # Generate unique event ID
        event_id = f"ra_co_{parsed_event['source_event_id']}"

        # Parse datetime
        start_dt = self._parse_datetime(parsed_event.get("start_datetime"))
        end_dt = self._parse_datetime(parsed_event.get("end_datetime"))

        # Build location
        coords = None
        # Ra.co API doesn't return coordinates for venues, we could add geocoding later
        if parsed_event.get("latitude") and parsed_event.get("longitude"):
            try:
                coords = Coordinates(
                    latitude=float(parsed_event["latitude"]),
                    longitude=float(parsed_event["longitude"]),
                )
            except (ValueError, TypeError):
                pass

        location = LocationInfo(
            venue_name=parsed_event.get("venue_name"),
            street_address=parsed_event.get("address"),
            city=parsed_event.get("area") or "Unknown",
            country_code=parsed_event.get("country_code", "GB"),
            coordinates=coords,
        )

        # Build price info
        # Ra.co provides cost as a string like "£10-15" or "Free"
        cost_str = (
            parsed_event.get("cost", "").strip() if parsed_event.get("cost") else ""
        )
        is_free = cost_str.lower() in ["free", "complimentary", ""]

        price = PriceInfo(
            currency="USD",  # Ra.co is UK-focused
            is_free=is_free,
            minimum_price=Decimal("0") if is_free else None,
            maximum_price=None,
            early_bird_price=(
                self._parse_price(cost_str.split("-")[0])
                if not is_free and "-" in cost_str
                else None
            ),
            standard_price=(
                self._parse_price(cost_str.split("-")[-1]) if not is_free else None
            ),
            vip_price=None,
            price_raw_text=cost_str,
        )

        # Build organizer (venue as organizer)
        organizer = OrganizerInfo(
            name=parsed_event.get("venue_name", "Unknown Venue"),
        )

        # Build source metadata
        source = SourceInfo(
            source_name="ra_co",
            source_event_id=parsed_event["source_event_id"],
            source_url=parsed_event.get("source_url", ""),
            last_updated_from_source=datetime.utcnow(),
        )

        # Build taxonomy dimensions
        taxonomy_dims_objs = [
            TaxonomyDimension(
                primary_category=dim["primary_category"],
                subcategory=dim.get("subcategory"),
                values=dim.get("values", []),
                confidence=dim.get("confidence", 0.5),
            )
            for dim in taxonomy_dims
        ]

        # Build media assets
        media_assets = []
        if parsed_event.get("image_url"):
            media_assets.append(
                MediaAsset(
                    type="image",
                    url=parsed_event["image_url"],
                    width=parsed_event.get("image_width"),
                    height=parsed_event.get("image_height"),
                )
            )

        # Build engagement metrics
        engagement = None
        if parsed_event.get("attendee_count"):
            engagement = EngagementMetrics(
                going_count=parsed_event["attendee_count"],
            )

        # Create EventSchema
        event = EventSchema(
            event_id=event_id,
            title=parsed_event.get("title", "Untitled Event"),
            description=parsed_event.get("description"),
            primary_category=primary_cat,
            taxonomy_dimensions=taxonomy_dims_objs,
            start_datetime=start_dt,
            end_datetime=end_dt,
            location=location,
            event_type=EventType.CONCERT,
            format=EventFormat.IN_PERSON,
            capacity=parsed_event.get("capacity"),
            price=price,
            organizer=organizer,
            image_url=parsed_event.get("image_url"),
            media_assets=media_assets,
            source=source,
            engagement=engagement,
            tags=parsed_event.get("tags", []),
        )

        return event

    def _parse_datetime(self, dt_string: Optional[str]) -> datetime:
        """
        Parse ISO datetime string.
        """
        if not dt_string:
            return datetime.utcnow()

        try:
            # Handle ISO 8601 format
            if dt_string.endswith("Z"):
                return datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
            return datetime.fromisoformat(dt_string)
        except (ValueError, AttributeError):
            self.logger.warning(f"Could not parse datetime: {dt_string}")
            return datetime.utcnow()

    def _parse_price(self, price_value: Optional[Any]) -> Optional[Decimal]:
        """
        Parse price value to Decimal.
        """
        if price_value is None:
            return None

        try:
            return Decimal(str(price_value))
        except (ValueError, TypeError):
            self.logger.warning(f"Could not parse price: {price_value}")
            return None

    # ========================================================================
    # STEP 5: VALIDATION
    # ========================================================================

    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """
        Validate ra.co event with source-specific rules. Still needs implementation.
        """
        errors = []

        # Location validation
        if not event.location.city:
            errors.append("Location: City is required")

        # if event.location.coordinates:
        #     # Rough check: London-ish coordinates
        #     lat, lng = event.location.coordinates.latitude, event.location.coordinates.longitude
        #     if not (50 <= lat <= 60 and -5 <= lng <= 5):
        #         # Only warn if we're not in expected region
        #         pass

        # Time validation
        if event.start_datetime < datetime.utcnow():
            errors.append("Event start time is in the past")

        # Price validation
        if event.price.minimum_price and event.price.minimum_price < 0:
            errors.append("Minimum price cannot be negative")

        # Organizer validation
        if not event.organizer.name:
            errors.append("Organizer name is required")

        is_valid = len(errors) == 0
        return is_valid, errors

    # ========================================================================
    # STEP 6: ENRICHMENT
    # ========================================================================

    def enrich_event(self, event: EventSchema) -> EventSchema:
        """
        Enrich event with additional data.
        """
        # Calculate duration if end_datetime exists
        if event.end_datetime and event.start_datetime:
            duration = (event.end_datetime - event.start_datetime).total_seconds() / 60
            event.duration_minutes = int(duration)

        # Attempt to infer timezone from location (future enhancement)
        if event.location.city == "London":
            event.location.timezone = "Europe/London"
        elif event.location.city == "Berlin":
            event.location.timezone = "Europe/Berlin"

        # - Geocode venue if coordinates missing
        # - Fetch artist images and metadata
        # - Calculate event popularity score
        # - Validate image URLs
        # - Capacity estimation based on venue type
        # - Event popularity prediction model?

        return event
