"""
Pydantic models for Instructor-based field extraction.

These models define the structured output schemas for extracting
specific fields from events using the Instructor library.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# =============================================================================
# PRIMARY CATEGORY EXTRACTION
# =============================================================================


class PrimaryCategoryExtraction(BaseModel):
    """Extract primary category from event context."""

    category_id: Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"] = Field(
        description="Primary category ID (1-10) based on event type"
    )
    reasoning: str = Field(description="Brief explanation for classification")
    confidence: float = Field(ge=0, le=1, description="Confidence score")


# =============================================================================
# SUBCATEGORY EXTRACTION
# =============================================================================


class SubcategoryExtraction(BaseModel):
    """Extract subcategory within a primary category."""

    subcategory_id: str = Field(description="Subcategory ID (e.g., '1.4', '5.7')")
    subcategory_name: str = Field(description="Name of the subcategory")
    confidence: float = Field(ge=0, le=1, default=0.7)


# =============================================================================
# EVENT TYPE EXTRACTION
# =============================================================================


class EventTypeExtraction(BaseModel):
    """Extract event type."""

    event_type: Literal[
        "concert",
        "festival",
        "party",
        "workshop",
        "lecture",
        "meetup",
        "sports",
        "exhibition",
        "conference",
        "nightlife",
        "theater",
        "dance",
        "food_beverage",
        "art_show",
        "other",
    ] = Field(description="Type of event")
    confidence: float = Field(ge=0, le=1, default=0.7)


# =============================================================================
# TAXONOMY ATTRIBUTES EXTRACTION
# =============================================================================


class TaxonomyAttributesExtraction(BaseModel):
    """Extract activity-level taxonomy attributes."""

    energy_level: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Energy level: low=calm, medium=moderate, high=intense",
    )
    social_intensity: Literal["solo", "small_group", "large_group"] = Field(
        default="large_group",
        description="Social scale: solo=individual, small_group=2-10, large_group=10+",
    )
    cognitive_load: Literal["low", "medium", "high"] = Field(
        default="low",
        description="Mental effort: low=passive, medium=some focus, high=deep learning",
    )
    physical_involvement: Literal["none", "light", "moderate"] = Field(
        default="light",
        description="Physical activity: none=seated, light=standing, moderate=dancing",
    )
    environment: Literal["indoor", "outdoor", "digital", "mixed"] = Field(
        default="indoor",
        description="Venue type: indoor=clubs, outdoor=festivals, digital=online",
    )
    risk_level: Literal["none", "very_low", "low", "medium"] = Field(
        default="very_low", description="Physical or other risks"
    )
    age_accessibility: Literal["all", "teens+", "adults"] = Field(
        default="adults",
        description="Age appropriateness: all=family, teens+=13+, adults=18+",
    )
    repeatability: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Repeat frequency: high=weekly, medium=monthly, low=unique",
    )
    emotional_output: List[str] = Field(
        default_factory=lambda: ["enjoyment"],
        description="Expected emotional outcomes",
    )


# =============================================================================
# TAGS EXTRACTION
# =============================================================================


class TagsExtraction(BaseModel):
    """Extract tags for an event."""

    tags: List[str] = Field(
        default_factory=list, description="5-10 relevant search tags"
    )


# =============================================================================
# MISSING FIELDS EXTRACTION (BATCH)
# =============================================================================


class MissingFieldsExtraction(BaseModel):
    """
    Batch extraction for multiple missing fields.

    This model is used by fill_missing_fields to extract multiple
    fields in a single LLM call based on the config's fill_missing list.
    """

    event_type: Optional[
        Literal[
            "concert",
            "festival",
            "party",
            "workshop",
            "lecture",
            "meetup",
            "sports",
            "exhibition",
            "conference",
            "nightlife",
            "theater",
            "dance",
            "food_beverage",
            "art_show",
            "other",
        ]
    ] = Field(default=None, description="Type of event")
    tags: List[str] = Field(default_factory=list, description="Search/filter tags")
    energy_level: Optional[Literal["low", "medium", "high"]] = Field(
        default=None, description="Energy level of the event"
    )
    social_intensity: Optional[Literal["solo", "small_group", "large_group"]] = Field(
        default=None, description="Social scale of the event"
    )
    cognitive_load: Optional[Literal["low", "medium", "high"]] = Field(
        default=None, description="Mental effort required"
    )
    physical_involvement: Optional[Literal["none", "light", "moderate"]] = Field(
        default=None, description="Physical activity level"
    )
    environment: Optional[Literal["indoor", "outdoor", "digital", "mixed"]] = Field(
        default=None, description="Primary environment"
    )
    emotional_output: List[str] = Field(
        default_factory=list, description="Expected emotional outcomes"
    )
    risk_level: Optional[Literal["none", "very_low", "low", "medium"]] = Field(
        default=None, description="Risk level"
    )
    age_accessibility: Optional[Literal["all", "teens+", "adults"]] = Field(
        default=None, description="Age appropriateness"
    )
    repeatability: Optional[Literal["high", "medium", "low"]] = Field(
        default=None, description="How often people repeat this"
    )
