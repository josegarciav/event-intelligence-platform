"""
Unit tests for the extraction_models module.

Tests for Instructor-based extraction model schemas.
"""

import pytest
from pydantic import ValidationError
from src.ingestion.normalization.extraction_models import (
    EventTypeExtraction,
    MissingFieldsExtraction,
    PrimaryCategoryExtraction,
    SubcategoryExtraction,
    TagsExtraction,
    TaxonomyAttributesExtraction,
)


class TestPrimaryCategoryExtraction:
    """Tests for PrimaryCategoryExtraction model."""

    def test_valid_extraction(self):
        """Valid primary category extraction."""
        extraction = PrimaryCategoryExtraction(
            category_id="1",
            reasoning="This is a music event",
            confidence=0.85,
        )
        assert extraction.category_id == "1"
        assert extraction.confidence == 0.85

    def test_all_category_ids_valid(self):
        """All category IDs 1-10 should be valid."""
        for i in range(1, 11):
            extraction = PrimaryCategoryExtraction(
                category_id=str(i),
                reasoning="Test",
                confidence=0.7,
            )
            assert extraction.category_id == str(i)

    def test_invalid_category_id(self):
        """Invalid category ID should raise."""
        with pytest.raises(ValidationError):
            PrimaryCategoryExtraction(
                category_id="11",  # Invalid
                reasoning="Test",
                confidence=0.7,
            )

        with pytest.raises(ValidationError):
            PrimaryCategoryExtraction(
                category_id="0",  # Invalid
                reasoning="Test",
                confidence=0.7,
            )

    def test_confidence_bounds(self):
        """Confidence must be 0-1."""
        with pytest.raises(ValidationError):
            PrimaryCategoryExtraction(
                category_id="1",
                reasoning="Test",
                confidence=1.5,
            )

        with pytest.raises(ValidationError):
            PrimaryCategoryExtraction(
                category_id="1",
                reasoning="Test",
                confidence=-0.1,
            )


class TestSubcategoryExtraction:
    """Tests for SubcategoryExtraction model."""

    def test_valid_extraction(self):
        """Valid subcategory extraction."""
        extraction = SubcategoryExtraction(
            subcategory_id="1.4",
            subcategory_name="Music & Rhythm Play",
            confidence=0.8,
        )
        assert extraction.subcategory_id == "1.4"
        assert extraction.subcategory_name == "Music & Rhythm Play"

    def test_default_confidence(self):
        """Default confidence should be 0.7."""
        extraction = SubcategoryExtraction(
            subcategory_id="1.4",
            subcategory_name="Music & Rhythm Play",
        )
        assert extraction.confidence == 0.7


class TestEventTypeExtraction:
    """Tests for EventTypeExtraction model."""

    def test_valid_event_types(self):
        """All valid event types should work."""
        valid_types = [
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
        for event_type in valid_types:
            extraction = EventTypeExtraction(event_type=event_type)
            assert extraction.event_type == event_type

    def test_invalid_event_type(self):
        """Invalid event type should raise."""
        with pytest.raises(ValidationError):
            EventTypeExtraction(event_type="invalid_type")

    def test_default_confidence(self):
        """Default confidence should be 0.7."""
        extraction = EventTypeExtraction(event_type="concert")
        assert extraction.confidence == 0.7


class TestTaxonomyAttributesExtraction:
    """Tests for TaxonomyAttributesExtraction model."""

    def test_valid_attributes(self):
        """Valid attribute extraction."""
        extraction = TaxonomyAttributesExtraction(
            energy_level="high",
            social_intensity="large_group",
            cognitive_load="low",
            physical_involvement="moderate",
            environment="indoor",
            risk_level="very_low",
            age_accessibility="adults",
            repeatability="medium",
            emotional_output=["joy", "excitement"],
        )
        assert extraction.energy_level == "high"
        assert extraction.social_intensity == "large_group"

    def test_default_values(self):
        """Default values should be set."""
        extraction = TaxonomyAttributesExtraction()
        assert extraction.energy_level == "medium"
        assert extraction.social_intensity == "large_group"
        assert extraction.cognitive_load == "low"
        assert extraction.physical_involvement == "light"
        assert extraction.environment == "indoor"
        assert extraction.risk_level == "very_low"
        assert extraction.age_accessibility == "adults"
        assert extraction.repeatability == "medium"
        assert extraction.emotional_output == ["enjoyment"]

    def test_invalid_energy_level(self):
        """Invalid energy level should raise."""
        with pytest.raises(ValidationError):
            TaxonomyAttributesExtraction(energy_level="extreme")

    def test_invalid_social_intensity(self):
        """Invalid social intensity should raise."""
        with pytest.raises(ValidationError):
            TaxonomyAttributesExtraction(social_intensity="massive")

    def test_emotional_output_list(self):
        """Emotional output should accept list of strings."""
        extraction = TaxonomyAttributesExtraction(emotional_output=["joy", "connection", "energy", "fulfillment"])
        assert len(extraction.emotional_output) == 4


class TestTagsExtraction:
    """Tests for TagsExtraction model."""

    def test_valid_tags(self):
        """Valid tags extraction."""
        extraction = TagsExtraction(tags=["electronic", "techno", "nightlife", "dance"])
        assert len(extraction.tags) == 4
        assert "electronic" in extraction.tags

    def test_empty_tags_default(self):
        """Default should be empty list."""
        extraction = TagsExtraction()
        assert extraction.tags == []


class TestMissingFieldsExtraction:
    """Tests for MissingFieldsExtraction batch model."""

    def test_all_fields_optional(self):
        """All fields should be optional."""
        extraction = MissingFieldsExtraction()
        assert extraction.event_type is None
        assert extraction.tags == []
        assert extraction.energy_level is None

    def test_partial_extraction(self):
        """Partial field extraction."""
        extraction = MissingFieldsExtraction(
            event_type="concert",
            tags=["music", "live"],
            energy_level="high",
        )
        assert extraction.event_type == "concert"
        assert extraction.energy_level == "high"
        assert extraction.social_intensity is None  # Not set

    def test_full_extraction(self):
        """Full field extraction."""
        extraction = MissingFieldsExtraction(
            event_type="party",
            tags=["nightlife", "electronic"],
            energy_level="high",
            social_intensity="large_group",
            cognitive_load="low",
            physical_involvement="moderate",
            environment="indoor",
            emotional_output=["joy", "energy"],
            risk_level="very_low",
            age_accessibility="adults",
            repeatability="high",
        )
        assert extraction.event_type == "party"
        assert extraction.repeatability == "high"

    def test_valid_event_types(self):
        """Event type must be valid Literal."""
        extraction = MissingFieldsExtraction(event_type="festival")
        assert extraction.event_type == "festival"

        with pytest.raises(ValidationError):
            MissingFieldsExtraction(event_type="invalid_type")
