# src/schemas/event.py
"""
Canonical Event Schema for the Event Intelligence Platform.

This schema normalizes events from heterogeneous sources (Meetup, ra.co, Ticketing APIs, etc.)
into a unified data model. The schema is built around the Human Experience Taxonomy,
capturing multi-dimensional aspects of human activities and experiences.

The schema serves as the source of truth for all downstream analytics, ML, and application logic.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

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
    get_primary_category_id_map,
    get_primary_category_value_to_id_map,
    get_subcategory_by_id,
    validate_subcategory_for_primary,
)


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


# ============================================================================
# ENUMS: Human Experience Taxonomy Dimensions
# ============================================================================

_TAXONOMY_INDEX = build_taxonomy_index()


class PrimaryCategory(str, Enum):
    """
    Primary experience categories from Human Experience Taxonomy.

    Supports both string values and numeric IDs:
    - PrimaryCategory("play_and_fun") - from string value
    - PrimaryCategory.from_id("1") - from numeric ID
    - PrimaryCategory.from_id_or_value("1") or ("play_and_fun") - accepts either
    """

    PLAY_AND_PURE_FUN = "play_and_fun"
    EXPLORATION_AND_ADVENTURE = "exploration_and_adventure"
    CREATION_AND_EXPRESSION = "creation_and_expression"
    LEARNING_AND_INTELLECTUAL = "learning_and_intellectual"
    SOCIAL_CONNECTION = "social_connection"
    BODY_AND_MOVEMENT = "body_and_movement"
    CHALLENGE_AND_ACHIEVEMENT = "challenge_and_achievement"
    RELAXATION_AND_ESCAPISM = "relaxation_and_escapism"
    IDENTITY_AND_MEANING = "identity_and_meaning"
    CONTRIBUTION_AND_IMPACT = "contribution_and_impact"

    @classmethod
    def from_id(cls, category_id: str) -> "PrimaryCategory":
        """
        Get enum from numeric ID ('1' through '10').

        Args:
            category_id: Numeric ID string (e.g., "1", "2", ...)

        Returns:
            PrimaryCategory enum member

        Raises:
            ValueError: If category_id is not valid

        Example:
            >>> PrimaryCategory.from_id("1")
            <PrimaryCategory.PLAY_AND_PURE_FUN: 'play_and_fun'>
        """
        id_map = get_primary_category_id_map()
        if category_id not in id_map:
            raise ValueError(
                f"Invalid category ID '{category_id}'. "
                f"Valid IDs are: {list(id_map.keys())}"
            )
        return cls(id_map[category_id])

    @classmethod
    def from_id_or_value(cls, value: str) -> "PrimaryCategory":
        """
        Accept either numeric ID ('1') or string value ('play_and_fun').

        Tries to interpret the value as a numeric ID first, then as a string value.

        Args:
            value: Either a numeric ID ("1") or string value ("play_and_fun")

        Returns:
            PrimaryCategory enum member

        Raises:
            ValueError: If value is neither a valid ID nor a valid string value

        Example:
            >>> PrimaryCategory.from_id_or_value("1")
            <PrimaryCategory.PLAY_AND_PURE_FUN: 'play_and_fun'>
            >>> PrimaryCategory.from_id_or_value("play_and_fun")
            <PrimaryCategory.PLAY_AND_PURE_FUN: 'play_and_fun'>
        """
        id_map = get_primary_category_id_map()

        # Try as numeric ID first
        if value in id_map:
            return cls(id_map[value])

        # Try as string value
        try:
            return cls(value)
        except ValueError:
            valid_ids = list(id_map.keys())
            valid_values = [e.value for e in cls]
            raise ValueError(
                f"Invalid value '{value}'. "
                f"Valid IDs: {valid_ids}, Valid values: {valid_values}"
            )

    def to_id(self) -> str:
        """
        Get numeric ID for this category.

        Returns:
            Numeric ID string (e.g., "1" for play_and_fun)

        Example:
            >>> PrimaryCategory.PLAY_AND_PURE_FUN.to_id()
            '1'
        """
        value_to_id = get_primary_category_value_to_id_map()
        return value_to_id[self.value]


class Subcategory:
    """
    Subcategories from Human Experience Taxonomy.
    Reads dynamically from the taxonomy file. Use `Subcategory.all_options()` for
    the full list of {id, name, primary_category}; use `Subcategory.all_ids()` to
    validate that a subcategory id is one of the available options; use
    `Subcategory.ids_for_primary(primary_key)` to map category -> subcategory ids.
    """

    _ALL_OPTIONS: Optional[List[Dict[str, Any]]] = None
    _ALL_IDS: Optional[set] = None

    @classmethod
    def all_options(cls) -> List[Dict[str, Any]]:
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
    def get_by_id(cls, subcategory_id: str) -> Optional[Dict[str, Any]]:
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
    """
    Format/medium of the event.
    """

    IN_PERSON = "in_person"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"
    STREAMED = "streamed"


class EventType(str, Enum):
    """
    High-level event type.
    """

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
    primary_category: PrimaryCategory
    subcategory: Optional[str] = Field(
        default=None,
        description="Subcategory id from the taxonomy (e.g. '1.4'). Must be one of Subcategory.all_ids().",
    )
    subcategory_name: Optional[str] = Field(
        default=None,
        description="Human-readable subcategory name (e.g. 'Music & Rhythm Play')",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this taxonomy mapping (0.0-1.0)",
    )
    values: List[str] = Field(default_factory=list)

    # Activity identification
    activity_id: Optional[str] = Field(
        default=None,
        description="UUID of matched activity from taxonomy",
    )
    activity_name: Optional[str] = Field(
        default=None,
        description="Name of matched activity",
    )

    # Activity-level attributes (selected from template options)
    energy_level: Optional[str] = Field(
        default=None,
        description="Energy level: 'low' | 'medium' | 'high'",
    )
    social_intensity: Optional[str] = Field(
        default=None,
        description="Social intensity: 'solo' | 'small_group' | 'large_group'",
    )
    cognitive_load: Optional[str] = Field(
        default=None,
        description="Cognitive load: 'low' | 'medium' | 'high'",
    )
    physical_involvement: Optional[str] = Field(
        default=None,
        description="Physical involvement: 'none' | 'light' | 'moderate'",
    )
    cost_level: Optional[str] = Field(
        default=None,
        description="Cost level: 'free' | 'low' | 'medium' | 'high'",
    )
    time_scale: Optional[str] = Field(
        default=None,
        description="Time scale: 'short' | 'long' | 'recurring'",
    )
    environment: Optional[str] = Field(
        default=None,
        description="Environment: 'indoor' | 'outdoor' | 'digital' | 'mixed'",
    )
    emotional_output: List[str] = Field(
        default_factory=list,
        description="List of emotional outputs (e.g., ['joy', 'connection', 'energy'])",
    )
    risk_level: Optional[str] = Field(
        default=None,
        description="Risk level: 'none' | 'very_low' | 'low' | 'medium'",
    )
    age_accessibility: Optional[str] = Field(
        default=None,
        description="Age accessibility: 'all' | 'teens+' | 'adults'",
    )
    repeatability: Optional[str] = Field(
        default=None,
        description="Repeatability: 'high' | 'medium' | 'low'",
    )

    @field_validator("subcategory")
    @classmethod
    def validate_subcategory_id(cls, v: Optional[str]) -> Optional[str]:
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
            primary_id = self.primary_category.to_id()
            if not Subcategory.validate_for_primary(self.subcategory, primary_id):
                raise ValueError(
                    f"Subcategory '{self.subcategory}' does not belong to "
                    f"primary category '{self.primary_category.value}' (ID: {primary_id}). "
                    f"Subcategory must start with '{primary_id}.'."
                )
        return self


# ============================================================================
# LOCATION & GEOGRAPHIC DATA
# ============================================================================


class Coordinates(BaseModel):
    """
    Geographic coordinates.
    """

    latitude: float
    longitude: float

    @field_validator("latitude")
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v


class LocationInfo(BaseModel):
    """
    Normalized location information.
    """

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

    venue_name: Optional[str] = None
    street_address: Optional[str] = None
    city: str
    state_or_region: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: str = Field(
        default="US", description="ISO 3166-1 alpha-2 country code"
    )
    coordinates: Optional[Coordinates] = None
    timezone: Optional[str] = None  # e.g., 'America/New_York'


# ============================================================================
# PRICING INFORMATION
# ============================================================================


class PriceInfo(BaseModel):
    """
    Pricing details for the event.
    """

    currency: str = Field(default="USD", description="ISO 4217 currency code")
    is_free: bool = False

    minimum_price: Optional[Decimal] = Field(default=None, ge=0)
    maximum_price: Optional[Decimal] = Field(default=None, ge=0)
    early_bird_price: Optional[Decimal] = Field(default=None, ge=0)
    standard_price: Optional[Decimal] = Field(default=None, ge=0)
    vip_price: Optional[Decimal] = Field(default=None, ge=0)

    price_raw_text: Optional[str] = Field(
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
    def serialize_decimal(self, v: Optional[Decimal]) -> Optional[float]:
        """Serialize Decimal to float for JSON compatibility."""
        if v is None:
            return None
        return float(v)


class TicketInfo(BaseModel):
    """
    Ticket availability and link information.
    """

    url: Optional[str] = None
    is_sold_out: bool = False
    ticket_count_available: Optional[int] = None
    early_bird_deadline: Optional[datetime] = None


# ============================================================================
# ORGANIZER & SOURCE INFORMATION
# ============================================================================


class OrganizerInfo(BaseModel):
    """
    Information about the event organizer.
    """

    name: str
    url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    image_url: Optional[str] = None
    follower_count: Optional[int] = None
    verified: bool = False


class SourceInfo(BaseModel):
    """
    Metadata about where the event came from.
    """

    source_name: str = Field(
        description="Name of the source (e.g., 'fever', 'meetup', 'ticketmaster')"
    )
    source_event_id: str = Field(description="Event ID from the original source")
    source_url: str = Field(description="Direct URL to event on source platform")
    compressed_html: Optional[str] = Field(
        default=None,
        description="Parsed HTML or JSON data from source for debugging/validation",
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        description="When we last updated this event from the source",
    )
    ingestion_timestamp: datetime = Field(
        default_factory=_utc_now, description="When we ingested this event"
    )


# ============================================================================
# MEDIA & ENGAGEMENT
# ============================================================================


class MediaAsset(BaseModel):
    """
    Media asset associated with the event.
    TODO: Implement multimodal media handling in the future
    to capture features/insights from various media types.
    Like the image, video, flyer, of last year's event, etc.
    """

    type: str = Field(description="Type of media (image, video, flyer, etc.)")
    url: str
    title: Optional[str] = None
    description: Optional[str] = (
        None  # could be implemented with a model in the future, analyzing image/video content to extract features.
    )
    width: Optional[int] = None
    height: Optional[int] = None


class ArtistInfo(BaseModel):
    """
    Artist information associated with an event.
    Maps to the artists and event_artists SQL tables.
    """

    name: str
    soundcloud_url: Optional[str] = None
    spotify_url: Optional[str] = None
    instagram_url: Optional[str] = None
    genre: Optional[str] = None


class EngagementMetrics(BaseModel):
    """
    Engagement metrics from the source.
    """

    going_count: Optional[int] = None
    interested_count: Optional[int] = None
    views_count: Optional[int] = None
    shares_count: Optional[int] = None
    comments_count: Optional[int] = None
    likes_count: Optional[int] = None
    last_updated: Optional[datetime] = None


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
    event_id: str = Field(
        description="Platform-wide unique event identifier (generated from source_event_id)"
    )
    title: str
    description: Optional[str] = None

    # ---- TAXONOMY & EXPERIENCE DIMENSIONS ----
    primary_category: PrimaryCategory
    taxonomy_dimensions: List[TaxonomyDimension] = Field(
        default_factory=list,
        description="Multi-dimensional taxonomy mappings for this event",
    )

    # ---- TIMING ----
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    is_all_day: bool = False
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # e.g., 'weekly', 'monthly', 'one_time'

    # ---- LOCATION ----
    location: LocationInfo

    # ---- EVENT DETAILS ----
    event_type: EventType = EventType.OTHER
    format: EventFormat = EventFormat.IN_PERSON
    capacity: Optional[int] = None
    age_restriction: Optional[str] = None

    # ---- PRICING & TICKETS ----
    price: PriceInfo = Field(default_factory=lambda: PriceInfo())
    ticket_info: TicketInfo = Field(default_factory=lambda: TicketInfo())

    # ---- ORGANIZER ----
    organizer: OrganizerInfo

    # ---- ARTISTS ----
    artists: List[ArtistInfo] = Field(default_factory=list)

    # ---- MEDIA & VISUAL ----
    image_url: Optional[str] = None
    media_assets: List[MediaAsset] = Field(default_factory=list)

    # ---- SOURCE METADATA ----
    source: SourceInfo

    # ---- ENGAGEMENT & POPULARITY ----
    engagement: Optional[EngagementMetrics] = None

    # ---- QUALITY & NORMALIZATION ----
    data_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Quality assessment of normalized data (0.0-1.0)",
    )
    normalization_errors: List[str] = Field(
        default_factory=list,
        description="Warnings/errors encountered during normalization",
    )

    # ---- ADDITIONAL METADATA ----
    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(
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
    """
    Container for batch operations on multiple events.
    """

    source_name: str
    batch_id: str = Field(description="Unique identifier for this batch")
    events: List[EventSchema]
    ingestion_timestamp: datetime = Field(default_factory=_utc_now)
    total_count: int
    successful_count: int = 0
    failed_count: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
