# Logic for the specific features
"""
Pydantic models for LLM-based feature extraction.

These models define the structured output schemas that LangChain uses
to enforce valid responses from the LLM.
"""

from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# TAXONOMY ATTRIBUTE MODELS
# =============================================================================


class TaxonomyAttributesOutput(BaseModel):
    """
    Structured output for taxonomy attribute selection.

    The LLM selects ONE option for each attribute based on event context.
    """

    energy_level: Literal["low", "medium", "high"] = Field(
        description="Energy level of the activity. "
        "'low' = calm, relaxed; 'medium' = moderate engagement; 'high' = intense, active"
    )
    social_intensity: Literal["solo", "small_group", "large_group"] = Field(
        description="Social scale of the activity. "
        "'solo' = individual; 'small_group' = 2-10 people; 'large_group' = 10+ people"
    )
    cognitive_load: Literal["low", "medium", "high"] = Field(
        description="Mental effort required. "
        "'low' = passive enjoyment; 'medium' = some focus; 'high' = active thinking/learning"
    )
    physical_involvement: Literal["none", "light", "moderate"] = Field(
        description="Physical activity level. "
        "'none' = sedentary; 'light' = standing/walking; 'moderate' = dancing/active movement"
    )
    environment: Literal["indoor", "outdoor", "digital", "mixed"] = Field(
        description="Primary environment. "
        "'indoor' = clubs/venues; 'outdoor' = festivals/parks; 'digital' = online; 'mixed' = hybrid"
    )
    risk_level: Literal["none", "very_low", "low", "medium"] = Field(
        description="Risk level of the activity. Most events are 'very_low' or 'low'"
    )
    age_accessibility: Literal["all", "teens+", "adults"] = Field(
        description="Age appropriateness. " "'all' = family-friendly; 'teens+' = 13+; 'adults' = 18+/21+ (clubs, bars)"
    )
    repeatability: Literal["high", "medium", "low"] = Field(
        description="How often people typically repeat this experience. "
        "'high' = weekly/regular; 'medium' = monthly; 'low' = rare/unique experience"
    )


class ActivityMatchOutput(BaseModel):
    """
    Structured output for activity matching.

    The LLM selects the best matching activity from the taxonomy.
    """

    activity_id: str | None = Field(
        default=None,
        description="UUID of the best matching activity from the taxonomy, or null if no good match",
    )
    activity_name: str | None = Field(default=None, description="Name of the matched activity")
    match_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in the match (0.0-1.0)",
    )
    reasoning: str | None = Field(default=None, description="Brief explanation of why this activity was chosen")


class SubcategoryMatchOutput(BaseModel):
    """
    Structured output for subcategory classification.

    The LLM determines the best subcategory within a primary category.
    """

    subcategory_id: str = Field(description="Subcategory ID (e.g., '1.4' for Music & Rhythm Play)")
    subcategory_name: str = Field(description="Name of the subcategory")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Confidence in classification")
    reasoning: str | None = Field(default=None, description="Brief explanation of the classification")


class PrimaryCategoryOutput(BaseModel):
    """
    Structured output for primary category classification.

    The LLM determines which primary category best fits the event.
    """

    category_id: str = Field(
        description="Primary category ID ('1' through '10')",
    )
    category_name: str = Field(description="Name of the category (e.g., 'PLAY & PURE FUN')")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Confidence in classification")


class EmotionalOutputExtraction(BaseModel):
    """
    Structured output for emotional output extraction.

    The LLM identifies likely emotional outcomes from the event.
    """

    emotions: list[str] = Field(
        default_factory=list,
        description="List of expected emotional outputs (e.g., ['joy', 'excitement', 'connection'])",
    )


class FullTaxonomyEnrichmentOutput(BaseModel):
    """
    Complete structured output for taxonomy dimension enrichment.

    Combines all attribute selections into a single model.
    """

    # Activity matching
    activity_id: str | None = Field(default=None, description="UUID of matched activity")
    activity_name: str | None = Field(default=None, description="Name of matched activity")

    # Attribute selections
    energy_level: Literal["low", "medium", "high"] = Field(default="medium")
    social_intensity: Literal["solo", "small_group", "large_group"] = Field(default="large_group")
    cognitive_load: Literal["low", "medium", "high"] = Field(default="low")
    physical_involvement: Literal["none", "light", "moderate"] = Field(default="light")
    cost_level: Literal["free", "low", "medium", "high"] = Field(default="medium")
    time_scale: Literal["short", "long", "recurring"] = Field(default="long")
    environment: Literal["indoor", "outdoor", "digital", "mixed"] = Field(default="indoor")
    risk_level: Literal["none", "very_low", "low", "medium"] = Field(default="very_low")
    age_accessibility: Literal["all", "teens+", "adults"] = Field(default="adults")
    repeatability: Literal["high", "medium", "low"] = Field(default="medium")

    # Emotional output
    emotional_output: list[str] = Field(default_factory=lambda: ["enjoyment", "connection"])


# =============================================================================
# EVENT CLASSIFICATION MODELS
# =============================================================================


class EventTypeOutput(BaseModel):
    """Structured output for event type classification."""

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
    confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Confidence in classification")


class MusicGenresOutput(BaseModel):
    """Structured output for music genre extraction."""

    genres: list[str] = Field(
        default_factory=list,
        description="List of music genres (e.g., ['electronic', 'techno', 'house'])",
    )
    is_music_event: bool = Field(default=True, description="Whether this is a music-related event")


class TagsOutput(BaseModel):
    """Structured output for tag generation."""

    tags: list[str] = Field(
        default_factory=list,
        description="List of relevant tags for search/filtering",
    )


# =============================================================================
# COMPLETE EVENT ENRICHMENT
# =============================================================================


class EventEnrichmentOutput(BaseModel):
    """
    Complete structured output for full event enrichment.

    This model is used when enriching all fields at once.
    """

    # Classification
    event_type: str | None = Field(default=None)
    music_genres: list[str] = Field(default_factory=list)

    # Tags
    tags: list[str] = Field(default_factory=list)

    # Primary taxonomy (for main dimension)
    primary_category_id: str | None = Field(default=None)
    subcategory_id: str | None = Field(default=None)

    # Activity-level attributes
    activity_id: str | None = Field(default=None)
    activity_name: str | None = Field(default=None)
    energy_level: str | None = Field(default=None)
    social_intensity: str | None = Field(default=None)
    cognitive_load: str | None = Field(default=None)
    physical_involvement: str | None = Field(default=None)
    cost_level: str | None = Field(default=None)
    time_scale: str | None = Field(default=None)
    environment: str | None = Field(default=None)
    emotional_output: list[str] = Field(default_factory=list)
    risk_level: str | None = Field(default=None)
    age_accessibility: str | None = Field(default=None)
    repeatability: str | None = Field(default=None)
