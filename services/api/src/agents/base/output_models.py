"""
Pydantic extraction schemas for structured LLM outputs.

Consolidated from the former extraction_models.py.
Used by enrichment agents via Instructor or Anthropic SDK structured output.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# PRIMARY CATEGORY
# =============================================================================


class PrimaryCategoryExtraction(BaseModel):
    """Extract primary category from event context."""

    category_id: str = Field(description="Primary category ID (0-10). '0' = Other.")
    reasoning: str = Field(description="Brief explanation for classification")
    confidence: float = Field(ge=0, le=1, description="Confidence score")

    @field_validator("category_id")
    @classmethod
    def validate_category_id(cls, v: str) -> str:
        from src.schemas.taxonomy import get_primary_category_id_map

        valid_ids = get_primary_category_id_map()
        if v not in valid_ids:
            return "0"
        return v


# =============================================================================
# SUBCATEGORY
# =============================================================================


class SubcategoryExtraction(BaseModel):
    """Extract subcategory within a primary category."""

    subcategory_id: str = Field(description="Subcategory ID (e.g., '1.4', '5.7')")
    subcategory_name: str = Field(description="Name of the subcategory")
    confidence: float = Field(ge=0, le=1, default=0.7)


# =============================================================================
# TAXONOMY ATTRIBUTES
# =============================================================================


class TaxonomyAttributesExtraction(BaseModel):
    """Activity-level taxonomy attributes for the experience pulse."""

    energy_level: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Physical intensity: low=calm, medium=moderate, high=intense",
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
        description="Physical activity: none=seated, light=standing, moderate=dancing/moving",
    )
    repeatability: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Repeat frequency: high=weekly, medium=monthly, low=unique/annual",
    )

    # Unconstrained taxonomy (taxonomy gap detection)
    unconstrained_primary_category: str | None = Field(
        default=None,
        description=(
            "Free-form primary category label to use if none of the predefined "
            "categories is a good fit. Null when the predefined taxonomy fits well."
        ),
    )
    unconstrained_subcategory: str | None = Field(
        default=None,
        description=(
            "Free-form subcategory label to use if none of the predefined "
            "subcategories is a good fit. Null when the predefined taxonomy fits well."
        ),
    )
    unconstrained_activity: str | None = Field(
        default=None,
        description=(
            "Free-form activity name to use if no predefined activity matches. "
            "Null when the predefined taxonomy fits well."
        ),
    )


# =============================================================================
# MISSING FIELDS BATCH EXTRACTION
# =============================================================================


class MissingFieldsExtraction(BaseModel):
    """
    Batch extraction for multiple missing fields (core_metadata prompt).

    Used by FeatureAlignmentAgent to fill event_type, tags, event_format.
    """

    event_type: (
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
        | None
    ) = Field(default=None, description="Type of event")
    event_format: Literal["in_person", "virtual", "hybrid", "streamed"] | None = Field(
        default=None, description="Event delivery format"
    )
    tags: list[str] = Field(
        default_factory=list, description="5-8 relevant search/filter tags"
    )


# =============================================================================
# DATA QUALITY AUDIT
# =============================================================================


class DataQualityAudit(BaseModel):
    """Output from the DataQualityAgent."""

    quality_score: float = Field(
        ge=0,
        le=1,
        description="Overall data quality score (0=unusable, 1=complete)",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Fields that are None or empty but should have values",
    )
    normalization_errors: list[str] = Field(
        default_factory=list,
        description="Detected normalization issues",
    )
    confidence_flags: dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence scores where uncertain",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Human-readable remediation suggestions",
    )


# =============================================================================
# BATCH WRAPPERS
# Each "Item" adds source_event_id so results can be matched back to events.
# Each "Batch" wraps a list of Items — one per event in the chunk.
# =============================================================================


class MissingFieldsExtractionItem(MissingFieldsExtraction):
    """Single-event result inside a batch, keyed by source_event_id."""

    source_event_id: str = Field(
        default="", description="Must match the source_event_id from the input"
    )


class MissingFieldsExtractionBatch(BaseModel):
    """Batch output from feature_alignment agent (one item per input event)."""

    items: list[MissingFieldsExtractionItem] = Field(default_factory=list)


class TaxonomyAttributesExtractionItem(TaxonomyAttributesExtraction):
    """Single-event result inside a batch, keyed by source_event_id."""

    source_event_id: str = Field(
        default="", description="Must match the source_event_id from the input"
    )


class TaxonomyAttributesExtractionBatch(BaseModel):
    """Batch output from taxonomy_classifier agent (one item per input event)."""

    items: list[TaxonomyAttributesExtractionItem] = Field(default_factory=list)


class DataQualityAuditItem(DataQualityAudit):
    """Single-event result inside a batch, keyed by source_event_id."""

    source_event_id: str = Field(
        default="", description="Must match the source_event_id from the input"
    )


class DataQualityAuditBatch(BaseModel):
    """Batch output from data_quality agent (one item per input event)."""

    items: list[DataQualityAuditItem] = Field(default_factory=list)
