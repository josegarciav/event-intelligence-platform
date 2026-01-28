"""
Canonical Event Schema for the Event Intelligence Platform.

This schema normalizes events from heterogeneous sources (Meetup, ra.co, Ticketing APIs, etc.)
into a unified data model. The schema is built around the Human Experience Taxonomy,
capturing multi-dimensional aspects of human activities and experiences.

The schema serves as the source of truth for all downstream analytics, ML, and application logic.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal
from normalization.taxonomy import build_taxonomy_index


# ============================================================================
# ENUMS: Human Experience Taxonomy Dimensions
# ============================================================================

_TAXONOMY_INDEX = build_taxonomy_index()

class PrimaryCategory(str, Enum):
    """
    Primary experience categories from Human Experience Taxonomy:
    """
    PLAY_AND_FUN = "play_and_fun"
    EXPLORATION_AND_ADVENTURE = "exploration_and_adventure"
    CREATION_AND_EXPRESSION = "creation_and_expression"
    LEARNING_AND_INTELLECTUAL = "learning_and_intellectual"
    SOCIAL_CONNECTION = "social_connection"
    BODY_AND_MOVEMENT = "body_and_movement"
    CHALLENGE_AND_ACHIEVEMENT = "challenge_and_achievement"
    RELAXATION_AND_ESCAPISM = "relaxation_and_escapism"
    IDENTITY_AND_MEANING = "identity_and_meaning"
    CONTRIBUTION_AND_IMPACT = "contribution_and_impact"


class SubcategoryExamples(str, Enum):
    """
    ILLUSTRATIVE - TO BE DEFINED DYNAMICALLY:
    Subcategories from the taxonomy (examples; can be dynamically extended).
    """
    # Play & Pure Fun
    GAMES_AND_PLAY = "games_and_play_systems"
    HUMOR_AND_LAUGHTER = "humor_and_laughter"
    SENSORY_STIMULATION = "sensory_stimulation_and_novelty"
    MUSIC_AND_RHYTHM = "music_and_rhythm_play"
    SOCIAL_FUN = "social_fun_and_playful_interaction"
    
    # Exploration & Adventure
    MICRO_EXPLORATION = "micro_exploration"
    NATURE_EXPLORATION = "nature_exploration"
    TRAVEL_AND_TRIPS = "travel_and_trip_adventures"
    CULTURAL_DISCOVERY = "cultural_discovery"
    FOOD_AND_TASTE = "food_and_taste_exploration"
    WATER_ADVENTURES = "water_adventures"
    ALTITUDE_AND_SKY = "altitude_and_sky_thrills"
    URBAN_ADVENTURE = "urban_adventure_and_night_exploration"
    
    # Creation & Expression
    VISUAL_ART = "visual_art_2d"
    CRAFTS_AND_HANDMADE = "crafts_and_handmade"
    MAKING_AND_BUILDING = "making_and_building"
    WRITING_AND_STORYTELLING = "writing_and_storytelling"
    MUSIC_CREATION = "music_creation"
    PERFORMANCE = "performance_and_embodied_expression"
    PHOTOGRAPHY_AND_VIDEO = "photography_and_video"
    DIGITAL_CREATION = "digital_creation"
    COOKING_CREATIVE = "cooking_as_creative_expression"
    PERSONAL_STYLE = "personal_style_and_aesthetic_creation"
    
    # Learning & Intellectual Pleasure
    READING_FOR_PLEASURE = "reading_for_curiosity_and_pleasure"
    LEARNING_NEW_SKILLS = "learning_new_skills_intellectual"
    COURSES_AND_LEARNING = "courses_and_structured_learning"
    RESEARCH_AND_DEEP_DIVES = "research_and_deep_dives"
    THINKING_AND_REASONING = "thinking_reasoning_and_mental_play"
    KNOWLEDGE_CONSUMPTION = "knowledge_consumption_audio_visual"
    
    # Social Connection & Belonging
    CASUAL_SOCIALIZING = "casual_socializing"
    DEEP_CONVERSATIONS = "deep_conversations_and_emotional_bonding"
    FRIENDSHIP_MAINTENANCE = "friendship_maintenance_and_rituals"
    ROMANCE_AND_INTIMACY = "romance_and_intimate_connection"
    FAMILY_CONNECTION = "family_connection"
    COMMUNITY_AND_GROUP = "community_and_group_belonging"
    SHARED_ACTIVITIES = "shared_activities_and_co_experience"
    ONLINE_SOCIAL = "online_social_interaction"
    
    # Body & Movement
    EVERYDAY_MOVEMENT = "everyday_movement_and_light_activity"
    FITNESS_AND_STRENGTH = "fitness_and_strength_training"
    CARDIO_AND_ENDURANCE = "cardio_and_endurance"
    MIND_BODY_PRACTICES = "mind_body_practices"
    DANCE_AND_RHYTHM = "dance_and_rhythmic_movement"
    SPORTS_AND_COMPETITIVE = "sports_and_competitive_physical_play"
    OUTDOOR_PHYSICAL = "outdoor_physical_experience"
    BODY_CARE_AND_RECOVERY = "body_care_recovery_and_sensory_regulation"
    
    # Challenge & Achievement
    MENTAL_CHALLENGES = "mental_challenges_and_problem_solving"
    SKILL_MASTERY = "skill_mastery_and_deliberate_practice"
    PHYSICAL_CHALLENGES = "physical_challenges_and_feats"
    COMPETITIVE_ACTIVITIES = "competitive_activities"
    GOAL_SETTING = "goal_setting_and_achievement_systems"
    PERFORMANCE_UNDER_PRESSURE = "performance_under_pressure"
    
    # Relaxation & Escapism
    PASSIVE_RELAXATION = "passive_relaxation"
    MENTAL_ESCAPE = "mental_escape_and_immersion"
    SLOW_LIVING = "slow_living_and_doing_nothing"
    SENSORY_COMFORT = "sensory_comfort_and_soothing"
    NATURE_BASED_RELAXATION = "nature_based_relaxation"
    DIGITAL_ESCAPISM = "digital_escapism_and_light_distraction"
    
    # Identity & Meaning
    SELF_REFLECTION = "self_reflection_and_inner_inquiry"
    VALUES_CLARIFICATION = "values_and_belief_clarification"
    SPIRITUALITY = "spirituality_and_transcendence"
    IDENTITY_EXPRESSION = "identity_expression_and_authenticity"
    LIFE_DESIGN = "life_design_and_direction"
    
    # Contribution & Impact
    HELPING_INDIVIDUALS = "helping_individuals_directly"
    EDUCATION_AND_SHARING = "education_and_knowledge_sharing"
    COMMUNITY_BUILDING = "community_building_and_social_good"
    VOLUNTEERING_AND_SERVICE = "volunteering_and_service"
    ACTIVISM_AND_ADVOCACY = "activism_and_advocacy"
    ENVIRONMENTAL_IMPACT = "environmental_and_sustainability_impact"


class Subcategory(BaseModel):
    """
    Reference to a subcategory defined in the Human Experience Taxonomy.
    """
    
    id: str = Field(
        description="Subcategory ID from the Human Experience Taxonomy (e.g., '1.1')"
    )
    name: Optional[str] = Field(
        default=None,
        description="Optional human-readable name (for debugging / UI)"
    )

    @field_validator("id")
    def validate_subcategory_exists(cls, v, info):
        primary = info.data.get("primary_category")
        if not primary:
            return v  # validated later

        allowed = _TAXONOMY_INDEX.get(primary)
        if not allowed or v not in allowed:
            raise ValueError(
                f"Subcategory '{v}' not valid for primary category '{primary}'"
            )
        return v


class EventFormat(str, Enum):
    """
    Format/medium of the event.
    """
    IN_PERSON = "in_person"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"
    STREAMED = "streamed"


class DayOfWeek(str, Enum):
    """
    Days of the week.
    """
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class EventType(str, Enum):
    """
    High-level event type.
    """
    CONCERT = "concert"
    FESTIVAL = "festival"
    WORKSHOP = "workshop"
    LECTURE = "lecture"
    MEETUP = "meetup"
    PARTY = "party"
    SPORTS = "sports"
    EXHIBITION = "exhibition"
    CONFERENCE = "conference"
    NIGHTLIFE = "nightlife"
    THEATER = "theater"
    DANCE = "dance"
    FOOD_BEVERAGE = "food_beverage"
    OTHER = "other"


# ============================================================================
# VALUE DIMENSIONS (from Taxonomy)
# ============================================================================

class TaxonomyDimension(BaseModel):
    """
    Represents a value dimension from the Human Experience Taxonomy.
    """
    primary_category: PrimaryCategory
    subcategory: Optional[Subcategory] = None
    values: List[str] = Field(default_factory=list)
    confidence: float = Field(0.5, ge=0.0, le=1.0)


# ============================================================================
# LOCATION & GEOGRAPHIC DATA
# ============================================================================

class Coordinates(BaseModel):
    """
    Geographic coordinates.
    """
    latitude: float
    longitude: float
    
    @field_validator('latitude')
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v
    
    @field_validator('longitude')
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v


class LocationInfo(BaseModel):
    """
    Normalized location information.
    """
    venue_name: Optional[str] = None
    street_address: Optional[str] = None
    city: str
    state_or_region: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: str = Field(default="US", description="ISO 3166-1 alpha-2 country code")
    coordinates: Optional[Coordinates] = None
    timezone: Optional[str] = None  # e.g., 'America/New_York'
    
    class Config:
        json_schema_extra = {
            "example": {
                "venue_name": "Electric Zoo Festival",
                "street_address": "Pier 97",
                "city": "New York",
                "state_or_region": "NY",
                "postal_code": "10069",
                "country_code": "US",
                "coordinates": {"latitude": 40.7695, "longitude": -73.9965},
                "timezone": "America/New_York"
            }
        }


# ============================================================================
# PRICING INFORMATION
# ============================================================================

class PriceInfo(BaseModel):
    """
    Pricing details for the event.
    """

    currency: str = Field(default="USD", description="ISO 4217 currency code")
    is_free: bool = False

    minimum_price: Optional[Decimal] = Field(None, ge=0)
    maximum_price: Optional[Decimal] = Field(None, ge=0)
    early_bird_price: Optional[Decimal] = Field(None, ge=0)
    standard_price: Optional[Decimal] = Field(None, ge=0)
    vip_price: Optional[Decimal] = Field(None, ge=0)

    price_raw_text: Optional[str] = Field(
        None,
        description="Original price text from source (for debugging/validation)"
    )

    @model_validator(mode="after")
    def validate_price_range(self):
        if (
            self.minimum_price is not None
            and self.maximum_price is not None
            and self.maximum_price < self.minimum_price
        ):
            raise ValueError(
                "maximum_price cannot be less than minimum_price"
            )
        return self


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
        description="Name of the source (e.g., 'ra_co', 'meetup', 'ticketmaster')"
    )
    source_event_id: str = Field(
        description="Event ID from the original source"
    )
    source_url: str = Field(
        description="Direct URL to event on source platform"
    )
    last_updated_from_source: datetime
    ingestion_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When we ingested this event"
    )
    data_freshness_hours: Optional[int] = None


# ============================================================================
# MEDIA & ENGAGEMENT
# ============================================================================

class MediaAsset(BaseModel):
    """
    Media asset associated with the event.
    """
    type: str = Field(description="Type of media (image, video, flyer, etc.)")
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


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
    
    # ---- CORE EVENT INFORMATION ----
    event_id: str = Field(
        description="Platform-wide unique event identifier (generated from source_event_id)"
    )
    title: str
    description: Optional[str] = None
    long_description: Optional[str] = None
    
    # ---- TAXONOMY & EXPERIENCE DIMENSIONS ----
    primary_category: PrimaryCategory
    taxonomy_dimensions: List[TaxonomyDimension] = Field(
        default_factory=list,
        description="Multi-dimensional taxonomy mappings for this event"
    )
    
    # ---- TIMING ----
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    is_all_day: bool = False
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # e.g., 'weekly', 'monthly'
    
    # ---- LOCATION ----
    location: LocationInfo
    
    # ---- EVENT DETAILS ----
    event_type: EventType = EventType.OTHER
    format: EventFormat
    capacity: Optional[int] = None
    age_restriction: Optional[str] = None
    
    # ---- PRICING & TICKETS ----
    price: PriceInfo = Field(default_factory=PriceInfo)
    ticket_info: Optional[TicketInfo] = None
    
    # ---- ORGANIZER ----
    organizer: OrganizerInfo
    
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
        description="Quality assessment of normalized data (0.0-1.0)"
    )
    normalization_errors: List[str] = Field(
        default_factory=list,
        description="Warnings/errors encountered during normalization"
    )
    
    # ---- ADDITIONAL METADATA ----
    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific fields that don't fit standard schema"
    )
    
    # ---- PLATFORM TIMESTAMPS ----
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v),
        }
        use_enum_values = True
        schema_extra = {
            "example": {
                "event_id": "ra_co_12345_2026-03-15",
                "title": "Floating Points DJ Set",
                "description": "Electronic music performance",
                "primary_category": "play_and_fun",
                "taxonomy_dimensions": [
                    {
                        "primary_category": "play_and_fun",
                        "subcategory": "music_and_rhythm_play",
                        "values": ["expression", "energy", "flow"],
                        "confidence": 0.95
                    },
                    {
                        "primary_category": "social_connection",
                        "subcategory": "shared_activities",
                        "values": ["belonging", "shared joy"],
                        "confidence": 0.8
                    }
                ],
                "start_datetime": "2026-03-15T23:00:00Z",
                "end_datetime": "2026-03-16T06:00:00Z",
                "location": {
                    "venue_name": "Printworks",
                    "city": "London",
                    "country_code": "GB",
                    "coordinates": {"latitude": 51.5074, "longitude": -0.0759},
                    "timezone": "Europe/London"
                },
                "event_type": "concert",
                "format": "in_person",
                "price": {"currency": "GBP", "minimum_price": 35.0, "maximum_price": 50.0},
                "organizer": {"name": "Printworks Events"},
                "source": {
                    "source_name": "ra_co",
                    "source_event_id": "12345",
                    "source_url": "https://ra.co/events/12345",
                    "last_updated_from_source": "2026-01-27T10:00:00Z"
                }
            }
        }


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
    ingestion_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_count: int
    successful_count: int = 0
    failed_count: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
