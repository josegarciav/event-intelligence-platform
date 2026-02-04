"""
Unit tests for the feature_models module.

Tests for LangChain-based feature extraction model schemas.
"""

import pytest
from pydantic import ValidationError

from src.ingestion.normalization.feature_models import (
    ActivityMatchOutput,
    EmotionalOutputExtraction,
    EventEnrichmentOutput,
    EventTypeOutput,
    FullTaxonomyEnrichmentOutput,
    MusicGenresOutput,
    PrimaryCategoryOutput,
    SubcategoryMatchOutput,
    TagsOutput,
    TaxonomyAttributesOutput,
)


class TestTaxonomyAttributesOutput:
    """Tests for TaxonomyAttributesOutput model."""

    def test_valid_attributes(self):
        """Valid taxonomy attributes."""
        output = TaxonomyAttributesOutput(
            energy_level="high",
            social_intensity="large_group",
            cognitive_load="low",
            physical_involvement="moderate",
            environment="indoor",
            risk_level="very_low",
            age_accessibility="adults",
            repeatability="medium",
        )
        assert output.energy_level == "high"
        assert output.repeatability == "medium"

    def test_all_energy_levels(self):
        """All energy levels should be valid."""
        for level in ["low", "medium", "high"]:
            output = TaxonomyAttributesOutput(
                energy_level=level,
                social_intensity="large_group",
                cognitive_load="low",
                physical_involvement="none",
                environment="indoor",
                risk_level="none",
                age_accessibility="all",
                repeatability="high",
            )
            assert output.energy_level == level

    def test_all_social_intensities(self):
        """All social intensities should be valid."""
        for intensity in ["solo", "small_group", "large_group"]:
            output = TaxonomyAttributesOutput(
                energy_level="medium",
                social_intensity=intensity,
                cognitive_load="low",
                physical_involvement="none",
                environment="indoor",
                risk_level="none",
                age_accessibility="all",
                repeatability="high",
            )
            assert output.social_intensity == intensity

    def test_all_environments(self):
        """All environments should be valid."""
        for env in ["indoor", "outdoor", "digital", "mixed"]:
            output = TaxonomyAttributesOutput(
                energy_level="medium",
                social_intensity="large_group",
                cognitive_load="low",
                physical_involvement="none",
                environment=env,
                risk_level="none",
                age_accessibility="all",
                repeatability="high",
            )
            assert output.environment == env

    def test_invalid_energy_level(self):
        """Invalid energy level should raise."""
        with pytest.raises(ValidationError):
            TaxonomyAttributesOutput(
                energy_level="extreme",  # Invalid
                social_intensity="large_group",
                cognitive_load="low",
                physical_involvement="none",
                environment="indoor",
                risk_level="none",
                age_accessibility="all",
                repeatability="high",
            )


class TestActivityMatchOutput:
    """Tests for ActivityMatchOutput model."""

    def test_valid_match(self):
        """Valid activity match."""
        output = ActivityMatchOutput(
            activity_id="123e4567-e89b-12d3-a456-426614174000",
            activity_name="Live Music Performance",
            match_confidence=0.9,
            reasoning="Event features live DJ set",
        )
        assert output.activity_id is not None
        assert output.match_confidence == 0.9

    def test_no_match(self):
        """No match returns None activity."""
        output = ActivityMatchOutput(
            activity_id=None,
            activity_name=None,
            match_confidence=0.3,
        )
        assert output.activity_id is None

    def test_default_confidence(self):
        """Default confidence should be 0.5."""
        output = ActivityMatchOutput()
        assert output.match_confidence == 0.5

    def test_confidence_bounds(self):
        """Confidence must be 0-1."""
        with pytest.raises(ValidationError):
            ActivityMatchOutput(match_confidence=1.5)

        with pytest.raises(ValidationError):
            ActivityMatchOutput(match_confidence=-0.1)


class TestSubcategoryMatchOutput:
    """Tests for SubcategoryMatchOutput model."""

    def test_valid_match(self):
        """Valid subcategory match."""
        output = SubcategoryMatchOutput(
            subcategory_id="1.4",
            subcategory_name="Music & Rhythm Play",
            confidence=0.85,
            reasoning="Event is music-focused",
        )
        assert output.subcategory_id == "1.4"
        assert output.confidence == 0.85

    def test_default_confidence(self):
        """Default confidence should be 0.7."""
        output = SubcategoryMatchOutput(
            subcategory_id="1.4",
            subcategory_name="Music & Rhythm Play",
        )
        assert output.confidence == 0.7


class TestPrimaryCategoryOutput:
    """Tests for PrimaryCategoryOutput model."""

    def test_valid_output(self):
        """Valid primary category output."""
        output = PrimaryCategoryOutput(
            category_id="1",
            category_name="PLAY & PURE FUN",
            confidence=0.9,
        )
        assert output.category_id == "1"
        assert output.category_name == "PLAY & PURE FUN"

    def test_default_confidence(self):
        """Default confidence should be 0.7."""
        output = PrimaryCategoryOutput(
            category_id="5",
            category_name="SOCIAL CONNECTION",
        )
        assert output.confidence == 0.7


class TestEmotionalOutputExtraction:
    """Tests for EmotionalOutputExtraction model."""

    def test_valid_emotions(self):
        """Valid emotional output."""
        output = EmotionalOutputExtraction(
            emotions=["joy", "excitement", "connection", "energy"]
        )
        assert len(output.emotions) == 4
        assert "joy" in output.emotions

    def test_empty_default(self):
        """Default should be empty list."""
        output = EmotionalOutputExtraction()
        assert output.emotions == []


class TestFullTaxonomyEnrichmentOutput:
    """Tests for FullTaxonomyEnrichmentOutput model."""

    def test_valid_full_enrichment(self):
        """Valid full enrichment output."""
        output = FullTaxonomyEnrichmentOutput(
            activity_id="uuid-123",
            activity_name="DJ Set",
            energy_level="high",
            social_intensity="large_group",
            cognitive_load="low",
            physical_involvement="moderate",
            cost_level="medium",
            time_scale="long",
            environment="indoor",
            risk_level="very_low",
            age_accessibility="adults",
            repeatability="high",
            emotional_output=["energy", "joy"],
        )
        assert output.activity_name == "DJ Set"
        assert output.cost_level == "medium"

    def test_default_values(self):
        """Default values should be set."""
        output = FullTaxonomyEnrichmentOutput()
        assert output.energy_level == "medium"
        assert output.social_intensity == "large_group"
        assert output.cognitive_load == "low"
        assert output.physical_involvement == "light"
        assert output.cost_level == "medium"
        assert output.time_scale == "long"
        assert output.environment == "indoor"
        assert output.risk_level == "very_low"
        assert output.age_accessibility == "adults"
        assert output.repeatability == "medium"
        assert output.emotional_output == ["enjoyment", "connection"]

    def test_all_cost_levels(self):
        """All cost levels should be valid."""
        for level in ["free", "low", "medium", "high"]:
            output = FullTaxonomyEnrichmentOutput(cost_level=level)
            assert output.cost_level == level

    def test_all_time_scales(self):
        """All time scales should be valid."""
        for scale in ["short", "long", "recurring"]:
            output = FullTaxonomyEnrichmentOutput(time_scale=scale)
            assert output.time_scale == scale


class TestEventTypeOutput:
    """Tests for EventTypeOutput model."""

    def test_valid_event_types(self):
        """All valid event types should work."""
        valid_types = [
            "concert", "festival", "party", "workshop", "lecture",
            "meetup", "sports", "exhibition", "conference", "nightlife",
            "theater", "dance", "food_beverage", "art_show", "other",
        ]
        for event_type in valid_types:
            output = EventTypeOutput(event_type=event_type)
            assert output.event_type == event_type

    def test_default_confidence(self):
        """Default confidence should be 0.7."""
        output = EventTypeOutput(event_type="concert")
        assert output.confidence == 0.7

    def test_invalid_event_type(self):
        """Invalid event type should raise."""
        with pytest.raises(ValidationError):
            EventTypeOutput(event_type="invalid")


class TestMusicGenresOutput:
    """Tests for MusicGenresOutput model."""

    def test_valid_genres(self):
        """Valid music genres."""
        output = MusicGenresOutput(
            genres=["electronic", "techno", "house"],
            is_music_event=True,
        )
        assert len(output.genres) == 3
        assert output.is_music_event is True

    def test_default_values(self):
        """Default values."""
        output = MusicGenresOutput()
        assert output.genres == []
        assert output.is_music_event is True

    def test_non_music_event(self):
        """Non-music event."""
        output = MusicGenresOutput(
            genres=[],
            is_music_event=False,
        )
        assert output.is_music_event is False


class TestTagsOutput:
    """Tests for TagsOutput model."""

    def test_valid_tags(self):
        """Valid tags output."""
        output = TagsOutput(
            tags=["electronic", "nightlife", "dance", "barcelona"]
        )
        assert len(output.tags) == 4

    def test_empty_default(self):
        """Default should be empty list."""
        output = TagsOutput()
        assert output.tags == []


class TestEventEnrichmentOutput:
    """Tests for EventEnrichmentOutput model."""

    def test_valid_enrichment(self):
        """Valid event enrichment."""
        output = EventEnrichmentOutput(
            event_type="concert",
            music_genres=["electronic", "techno"],
            tags=["music", "live", "nightlife"],
            primary_category_id="1",
            subcategory_id="1.4",
            activity_id="uuid-123",
            activity_name="Live Performance",
            energy_level="high",
            social_intensity="large_group",
        )
        assert output.event_type == "concert"
        assert len(output.music_genres) == 2

    def test_all_optional(self):
        """All fields should be optional."""
        output = EventEnrichmentOutput()
        assert output.event_type is None
        assert output.music_genres == []
        assert output.tags == []
        assert output.primary_category_id is None
        assert output.energy_level is None
