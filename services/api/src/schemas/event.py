# src/schemas/event.py
"""
Canonical Event Schema for the Event Intelligence Platform.

This schema normalizes events from heterogeneous sources (Meetup, ra.co, Ticketing APIs, etc.)
into a unified data model. The schema is built around the Human Experience Taxonomy,
capturing multi-dimensional aspects of human activities and experiences.

The schema serves as the source of truth for all downstream analytics, ML, and application logic.
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from src.schemas.taxonomy import (
    build_taxonomy_index,
    get_all_subcategory_ids,
    get_all_subcategory_options,
    get_subcategory_by_id,
    primary_category_to_id,
    resolve_primary_category,
    validate_subcategory_for_primary,
)


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


# ============================================================================
# ENUMS: Human Experience Taxonomy Dimensions
# ============================================================================

_TAXONOMY_INDEX = build_taxonomy_index()


class Subcategory:
    """
    Subcategories from Human Experience Taxonomy.

    Reads dynamically from the taxonomy file. Use `Subcategory.all_options()` for
    the full list of {id, name, primary_category}; use `Subcategory.all_ids()` to
    validate that a subcategory id is one of the available options; use
    `Subcategory.ids_for_primary(primary_key)` to map category -> subcategory ids.
    """

    _ALL_OPTIONS: list[dict[str, Any]] | None = None
    _ALL_IDS: set | None = None

    @classmethod
    def all_options(cls) -> list[dict[str, Any]]:
        """List of all subcategory options: {id, name, primary_category}."""
        if cls._ALL_OPTIONS is None:
            cls._ALL_OPTIONS = get_all_subcategory_options()
        return cls._ALL_OPTIONS

    @classmethod
    def all_ids(cls) -> set:
        """Set of all valid subcategory ids (all available options)."""
        if cls._ALL_IDS is None:
            cls._ALL_IDS = get_all_subcategory_ids()
        return cls._ALL_IDS

    @classmethod
    def ids_for_primary(cls, primary_key: str) -> set:
        """Set of subcategory ids valid for the given taxonomy primary key."""
        return _TAXONOMY_INDEX.get(primary_key, set())

    @classmethod
    def get_by_id(cls, subcategory_id: str) -> dict[str, Any] | None:
        """
        Get full subcategory data by ID.

        Args:
            subcategory_id: Subcategory ID (e.g., "1.4")

        Returns:
            Full subcategory dict with all fields including:
            - id, name, values, activities
            - _primary_category, _primary_category_name
            Returns None if not found.

        Example:
            >>> sub = Subcategory.get_by_id("1.4")
            >>> print(sub["name"])  # "Music & Rhythm Play"
        """
        return get_subcategory_by_id(subcategory_id)

    @classmethod
    def validate_for_primary(cls, subcategory_id: str, primary_id: str) -> bool:
        """
        Validate subcategory belongs to primary category.

        Args:
            subcategory_id: Subcategory ID (e.g., "1.4")
            primary_id: Primary category ID ("1") or value ("play_and_fun")

        Returns:
            True if subcategory belongs to primary category, False otherwise.

        Example:
            >>> Subcategory.validate_for_primary("1.4", "1")
            True
            >>> Subcategory.validate_for_primary("2.1", "1")
            False
            >>> Subcategory.validate_for_primary("1.4", "play_and_fun")
            True
        """
        return validate_subcategory_for_primary(subcategory_id, primary_id)


class EventFormat(str, Enum):
    """Format/medium of the event."""

    IN_PERSON = "in_person"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"
    STREAMED = "streamed"


class EventType(str, Enum):
    """High-level event type."""

    CONCERT = "concert"  # music related
    ART_SHOW = "art_show"
    FESTIVAL = "festival"  # music related
    WORKSHOP = "workshop"
    LECTURE = "lecture"
    MEETUP = "meetup"
    PARTY = "party"  # music related
    SPORTS = "sports"
    EXHIBITION = "exhibition"
    CONFERENCE = "conference"
    NIGHTLIFE = "nightlife"
    THEATER = "theater"
    DANCE = "dance"  # music related
    FOOD_BEVERAGE = "food_beverage"
    OTHER = "other"


# ============================================================================
# VALUE DIMENSIONS (from Taxonomy)
# ============================================================================


class TaxonomyDimension(BaseModel):
    """
    Represents a value dimension from the Human Experience Taxonomy.

    Contains both basic category/subcategory info and detailed activity-level
    attributes populated from the taxonomy or inferred by FeatureExtractor.
    """

    # Core taxonomy fields
    primary_category: str = Field(
        description="Normalized primary category value (e.g. 'play_&_pure_fun', 'other')",
    )
    subcategory: str | None = Field(
        default=None,
        description="Subcategory id from the taxonomy (e.g. '1.4'). Must be one of Subcategory.all_ids().",
    )
    subcategory_name: str | None = Field(
        default=None,
        description="Human-readable subcategory name (e.g. 'Music & Rhythm Play')",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this taxonomy mapping (0.0-1.0)",
    )
    values: list[str] = Field(default_factory=list)

    # Activity identification
    activity_id: str | None = Field(
        default=None,
        description="UUID of matched activity from taxonomy",
    )
    activity_name: str | None = Field(
        default=None,
        description="Name of matched activity",
    )

    # Activity-level attributes (selected from template options)
    energy_level: str | None = Field(
        default=None,
        description="Energy level: 'low' | 'medium' | 'high'",
    )
    social_intensity: str | None = Field(
        default=None,
        description="Social intensity: 'solo' | 'small_group' | 'large_group'",
    )
    cognitive_load: str | None = Field(
        default=None,
        description="Cognitive load: 'low' | 'medium' | 'high'",
    )
    physical_involvement: str | None = Field(
        default=None,
        description="Physical involvement: 'none' | 'light' | 'moderate'",
    )
    cost_level: str | None = Field(
        default=None,
        description="Cost level: 'free' | 'low' | 'medium' | 'high'",
    )
    time_scale: str | None = Field(
        default=None,
        description="Time scale: 'short' | 'long' | 'recurring'",
    )
    environment: str | None = Field(
        default=None,
        description="Environment: 'indoor' | 'outdoor' | 'digital' | 'mixed'",
    )
    emotional_output: list[str] = Field(
        default_factory=list,
        description="List of emotional outputs (e.g., ['joy', 'connection', 'energy'])",
    )
    risk_level: str | None = Field(
        default=None,
        description="Risk level: 'none' | 'very_low' | 'low' | 'medium'",
    )
    age_accessibility: str | None = Field(
        default=None,
        description="Age accessibility: 'all' | 'teens+' | 'adults'",
    )
    repeatability: str | None = Field(
        default=None,
        description="Repeatability: 'high' | 'medium' | 'low'",
    )

    @field_validator("primary_category", mode="before")
    @classmethod
    def normalize_primary_category(cls, v: str) -> str:
        """Resolve any primary category representation to its normalized value."""
        return resolve_primary_category(str(v))

    @field_validator("subcategory")
    @classmethod
    def validate_subcategory_id(cls, v: str | None) -> str | None:
        """Validate that subcategory ID exists in taxonomy."""
        if v is None or v == "":
            return None
        allowed = Subcategory.all_ids()
        if v not in allowed:
            raise ValueError(
                f"Subcategory '{v}' is not a valid taxonomy id. "
                f"Use Subcategory.all_options() or Subcategory.all_ids() for available options."
            )
        return v

    @model_validator(mode="after")
    def validate_subcategory_primary_match(self) -> "TaxonomyDimension":
        """Ensure subcategory belongs to the specified primary category."""
        if self.subcategory is not None:
            pid = primary_category_to_id(self.primary_category)
            if not Subcategory.validate_for_primary(self.subcategory, pid):
                raise ValueError(
                    f"Subcategory '{self.subcategory}' does not belong to "
                    f"primary category '{self.primary_category}' (ID: {pid}). "
                    f"Subcategory must start with '{pid}.'."
                )
        return self


# ============================================================================
# LOCATION & GEOGRAPHIC DATA
# ============================================================================


class Coordinates(BaseModel):
    """Geographic coordinates."""

    latitude: float
    longitude: float

    @field_validator("latitude")
    def validate_latitude(cls, v):
        """Validate latitude is within range and has sufficient precision."""
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        decimal_str = str(v).split(".")[-1] if "." in str(v) else ""
        if len(decimal_str) < 4:
            raise ValueError(f"Latitude {v} has insufficient precision (min 4 decimals, ~11m accuracy)")
        return v

    @field_validator("longitude")
    def validate_longitude(cls, v):
        """Validate longitude is within range and has sufficient precision."""
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        decimal_str = str(v).split(".")[-1] if "." in str(v) else ""
        if len(decimal_str) < 4:
            raise ValueError(f"Longitude {v} has insufficient precision (min 4 decimals, ~11m accuracy)")
        return v


class LocationInfo(BaseModel):
    """Normalized location information."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "venue_name": "Electric Zoo Festival",
                "street_address": "Pier 97",
                "city": "New York",
                "state_or_region": "NY",
                "postal_code": "10069",
                "country_code": "US",
                "coordinates": {"latitude": 40.7695, "longitude": -73.9965},
                "timezone": "America/New_York",
            }
        }
    )

    venue_name: str | None = None
    street_address: str | None = None
    city: str
    state_or_region: str | None = None
    postal_code: str | None = None
    country_code: str = Field(default="US", description="ISO 3166-1 alpha-2 country code")
    coordinates: Coordinates | None = None
    timezone: str | None = None  # e.g., 'America/New_York'


# ============================================================================
# PRICING INFORMATION
# ============================================================================


class PriceInfo(BaseModel):
    """Pricing details for the event."""

    currency: str = Field(default="USD", description="ISO 4217 currency code")
    is_free: bool = False

    minimum_price: Decimal | None = Field(default=None, ge=0)
    maximum_price: Decimal | None = Field(default=None, ge=0)
    early_bird_price: Decimal | None = Field(default=None, ge=0)
    standard_price: Decimal | None = Field(default=None, ge=0)
    vip_price: Decimal | None = Field(default=None, ge=0)

    price_raw_text: str | None = Field(
        default=None,
        description="Original price text from source (for debugging/validation)",
    )

    @field_validator(
        "minimum_price",
        "maximum_price",
        "early_bird_price",
        "standard_price",
        "vip_price",
        mode="before",
    )
    @classmethod
    def coerce_to_decimal(cls, v):
        """Coerce float/int to Decimal for price fields."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @model_validator(mode="after")
    def validate_price_range(self):
        """Validate that maximum price is not less than minimum price."""
        if (
            self.minimum_price is not None
            and self.maximum_price is not None
            and self.maximum_price < self.minimum_price
        ):
            raise ValueError("maximum_price cannot be less than minimum_price")
        return self

    @field_serializer(
        "minimum_price",
        "maximum_price",
        "early_bird_price",
        "standard_price",
        "vip_price",
    )
    def serialize_decimal(self, v: Decimal | None) -> float | None:
        """Serialize Decimal to float for JSON compatibility."""
        if v is None:
            return None
        return float(v)


class TicketInfo(BaseModel):
    """Ticket availability and link information."""

    url: str | None = None
    is_sold_out: bool = False
    ticket_count_available: int | None = None
    early_bird_deadline: datetime | None = None


# ============================================================================
# ORGANIZER & SOURCE INFORMATION
# ============================================================================


class OrganizerInfo(BaseModel):
    """Information about the event organizer."""

    name: str
    url: str | None = None
    email: str | None = None
    phone: str | None = None
    image_url: str | None = None
    follower_count: int | None = None
    verified: bool = False


class SourceInfo(BaseModel):
    """Metadata about where the event came from."""

    source_name: str = Field(description="Name of the source (e.g., 'fever', 'meetup', 'ticketmaster')")
    source_event_id: str = Field(description="Event ID from the original source")
    source_url: str = Field(description="Direct URL to event on source platform")
    compressed_html: str | None = Field(
        default=None,
        description="Parsed HTML or JSON data from source for debugging/validation",
    )
    source_updated_at: datetime | None = Field(
        default=None,
        description="Timestamp of last update at the source platform (None = unknown)",
    )
    ingestion_timestamp: datetime = Field(default_factory=_utc_now, description="When we ingested this event")


# ============================================================================
# MEDIA & ENGAGEMENT
# ============================================================================


class MediaAsset(BaseModel):
    """
    Media asset associated with the event (image, video, flyer, etc.).

    The description field is intentionally open-ended to support future
    multimodal analysis (e.g., extracting features from event flyers or
    recap videos via a vision model).
    """

    type: str = Field(description="Type of media (image, video, flyer, etc.)")
    url: str
    title: str | None = None
    description: str | None = (
        None  # could be implemented with a model in the future, analyzing image/video content to extract features.
    )
    width: int | None = None
    height: int | None = None


class ArtistInfo(BaseModel):
    """
    Artist information associated with an event.

    Maps to the artists and event_artists SQL tables.
    """

    name: str
    soundcloud_url: str | None = None
    spotify_url: str | None = None
    instagram_url: str | None = None
    genre: str | None = None


class EngagementMetrics(BaseModel):
    """Engagement metrics from the source."""

    going_count: int | None = None
    interested_count: int | None = None
    views_count: int | None = None
    shares_count: int | None = None
    comments_count: int | None = None
    likes_count: int | None = None
    updated_at: datetime | None = None


class NormalizationSeverity(str, Enum):
    """Severity level for normalization messages."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class NormalizationError(BaseModel):
    """Structured normalization error/info message."""

    message: str
    severity: NormalizationSeverity = NormalizationSeverity.ERROR


# ============================================================================
# MAIN EVENT SCHEMA
# ============================================================================


class EventSchema(BaseModel):
    """
    Canonical Event Schema for the Event Intelligence Platform.

    This is the unified, normalized representation of events from all sources.
    It captures the multi-dimensional nature of human experiences through the
    Human Experience Taxonomy while accommodating source-specific metadata.
    """

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Floating Points DJ Set",
                "description": "Electronic music performance",
                "start_datetime": "2026-03-15T23:00:00Z",
                "end_datetime": "2026-03-16T06:00:00Z",
                "location": {
                    "venue_name": "Printworks",
                    "city": "London",
                    "country_code": "GB",
                },
                "event_type": "concert",
                "price": {"currency": "GBP", "minimum_price": 35.0, "is_free": False},
                "source": {
                    "source_name": "ra_co",
                    "source_event_id": "12345",
                    "source_url": "https://ra.co/events/12345",
                },
            }
        },
    )

    # ---- CORE EVENT INFORMATION ----
    event_id: str = Field(description="Platform-wide unique event identifier (generated from source_event_id)")
    title: str
    description: str | None = None

    # ---- TAXONOMY & EXPERIENCE DIMENSIONS ----
    taxonomy_dimension: TaxonomyDimension | None = Field(
        default=None,
        description="Taxonomy dimension mapping for this event",
    )

    # ---- TIMING ----
    start_datetime: datetime
    end_datetime: datetime | None = None
    duration_minutes: int | None = None
    is_all_day: bool = False
    is_recurring: bool = False
    recurrence_pattern: str | None = None  # e.g., 'weekly', 'monthly', 'one_time'

    # ---- LOCATION ----
    location: LocationInfo

    # ---- EVENT DETAILS ----
    event_type: EventType = EventType.OTHER
    format: EventFormat = EventFormat.IN_PERSON
    capacity: int | None = None
    age_restriction: str | None = None

    # ---- PRICING & TICKETS ----
    price: PriceInfo = Field(default_factory=lambda: PriceInfo())
    ticket_info: TicketInfo = Field(default_factory=lambda: TicketInfo())

    # ---- ORGANIZER ----
    organizer: OrganizerInfo

    # ---- ARTISTS ----
    artists: list[ArtistInfo] = Field(default_factory=list)

    # ---- MEDIA & VISUAL ----
    media_assets: list[MediaAsset] = Field(default_factory=list)

    # ---- SOURCE METADATA ----
    source: SourceInfo

    # ---- ENGAGEMENT & POPULARITY ----
    engagement: EngagementMetrics | None = None

    # ---- QUALITY & NORMALIZATION ----
    data_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Quality assessment of normalized data (0.0-1.0)",
    )
    normalization_errors: list[NormalizationError] = Field(
        default_factory=list,
        description="Warnings/errors encountered during normalization",
    )

    # ---- ADDITIONAL METADATA ----
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific fields that don't fit standard schema",
    )

    # ---- PLATFORM TIMESTAMPS ----
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


# ============================================================================
# EVENT BATCH (for bulk operations)
# ============================================================================


class EventBatch(BaseModel):
    """Container for batch operations on multiple events."""

    source_name: str
    batch_id: str = Field(description="Unique identifier for this batch")
    events: list[EventSchema]
    ingestion_timestamp: datetime = Field(default_factory=_utc_now)
    total_count: int
    successful_count: int = 0
    failed_count: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
