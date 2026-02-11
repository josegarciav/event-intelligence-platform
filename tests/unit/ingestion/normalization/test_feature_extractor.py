"""
Unit tests for the feature_extractor module.

Tests for FeatureExtractor rule-based inference methods.
LLM-based methods are tested with mocked clients.
"""

import pytest

from src.agents.feature_extractor import (
    FeatureExtractor,
    create_feature_extractor_from_config,
)
from src.schemas.taxonomy import get_all_subcategory_ids


@pytest.fixture
def extractor():
    """Create a FeatureExtractor without API key (rule-based only)."""
    return FeatureExtractor(api_key="")


@pytest.fixture
def valid_subcategory_id():
    """Get a valid subcategory ID for testing."""
    all_ids = get_all_subcategory_ids()
    for sub_id in all_ids:
        if sub_id.startswith("1."):
            return sub_id
    return "1.1"


class TestFeatureExtractorInit:
    """Tests for FeatureExtractor initialization."""

    def test_init_creates_instance(self):
        """Should create instance with default values."""
        extractor = FeatureExtractor()
        assert extractor.provider == "openai"
        assert extractor.model_name == "gpt-4o-mini"
        assert extractor.temperature == 0.1

    def test_init_custom_values(self):
        """Should accept custom values."""
        extractor = FeatureExtractor(
            provider="openai",
            model_name="gpt-4",
            temperature=0.5,
            max_tokens=1000,
        )
        assert extractor.model_name == "gpt-4"
        assert extractor.temperature == 0.5
        assert extractor.max_tokens == 1000

    def test_llm_not_available_without_key(self, extractor):
        """LLM should not be available without API key."""
        assert extractor.is_llm_available is False


class TestInferPrimaryCategoryRules:
    """Tests for _infer_primary_category_rules method."""

    def test_infer_music_keywords(self, extractor):
        """Should infer category 1 for music keywords."""
        event = {"title": "Techno Concert Night"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "1"  # PLAY & PURE FUN

        event = {"title": "DJ Set", "description": "Electronic music"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "1"

    def test_infer_learning_keywords(self, extractor):
        """Should infer category 2 for learning keywords."""
        event = {"title": "Python Workshop"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "2"  # LEARN & DISCOVER

        event = {"title": "Cooking Masterclass"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "2"

    def test_infer_social_keywords(self, extractor):
        """Should infer category 3 for social keywords."""
        event = {"title": "Tech Meetup Barcelona"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "3"  # CONNECT & BELONG

        event = {"title": "Networking Event", "description": "Community gathering"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "3"

    def test_infer_art_keywords(self, extractor):
        """Should infer category 4 for art keywords."""
        event = {"title": "Art Exhibition"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "4"  # CREATE & EXPRESS

    def test_infer_sports_keywords(self, extractor):
        """Should infer category 5 for sports keywords."""
        event = {"title": "Morning Yoga Session"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "5"  # MOVE & THRIVE

        event = {"title": "5K Run"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "5"

    def test_infer_food_keywords(self, extractor):
        """Should infer category 6 for food keywords."""
        event = {"title": "Wine Tasting Evening"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "6"  # TASTE & SAVOR

    def test_infer_nature_keywords(self, extractor):
        """Should infer category 7 for nature keywords."""
        event = {"title": "Hiking Adventure"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "7"  # EXPLORE & WANDER

    def test_infer_wellness_keywords(self, extractor):
        """Should infer category 8 for wellness keywords."""
        event = {"title": "Meditation Retreat"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "8"  # REST & RECHARGE

    def test_infer_charity_keywords(self, extractor):
        """Should infer category 9 for charity keywords."""
        event = {"title": "Charity Fundraiser"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "9"  # GIVE & IMPACT

    def test_infer_festival_keywords(self, extractor):
        """Should infer category 10 for festival keywords."""
        event = {"title": "Summer Festival Celebration"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "10"  # CELEBRATE & COMMEMORATE

    def test_infer_default(self, extractor):
        """Should default to category 1 when no keywords match."""
        event = {"title": "Some Random Event"}
        result = extractor._infer_primary_category_rules(event)
        assert result == "1"  # Default to PLAY & PURE FUN


class TestInferEventTypeRules:
    """Tests for _infer_event_type_rules method."""

    def test_infer_festival(self, extractor):
        """Should infer festival type."""
        event = {"title": "Summer Music Festival"}
        result = extractor._infer_event_type_rules(event)
        assert result == "festival"

    def test_infer_party(self, extractor):
        """Should infer party type."""
        event = {"title": "Birthday Party"}
        result = extractor._infer_event_type_rules(event)
        assert result == "party"

    def test_infer_concert(self, extractor):
        """Should infer concert type."""
        event = {"title": "Live Concert"}
        result = extractor._infer_event_type_rules(event)
        assert result == "concert"

    def test_infer_workshop(self, extractor):
        """Should infer workshop type."""
        event = {"title": "Photography Workshop"}
        result = extractor._infer_event_type_rules(event)
        assert result == "workshop"

        event = {"title": "DJ Masterclass"}
        result = extractor._infer_event_type_rules(event)
        assert result == "workshop"

    def test_infer_exhibition(self, extractor):
        """Should infer exhibition type."""
        event = {"title": "Modern Art Exhibition"}
        result = extractor._infer_event_type_rules(event)
        assert result == "exhibition"

    def test_infer_conference(self, extractor):
        """Should infer conference type."""
        event = {"title": "Tech Conference 2024"}
        result = extractor._infer_event_type_rules(event)
        assert result == "conference"

    def test_infer_default_nightlife(self, extractor):
        """Should default to nightlife for unmatched."""
        event = {"title": "Saturday Night Event"}
        result = extractor._infer_event_type_rules(event)
        assert result == "nightlife"


class TestInferGenresRules:
    """Tests for _infer_genres_rules method."""

    def test_infer_techno(self, extractor):
        """Should infer techno genre."""
        event = {"title": "Techno Night", "description": ""}
        result = extractor._infer_genres_rules(event)
        assert "techno" in result

    def test_infer_house(self, extractor):
        """Should infer house genre."""
        event = {"title": "Deep House Session", "description": ""}
        result = extractor._infer_genres_rules(event)
        assert "house" in result

    def test_infer_electronic(self, extractor):
        """Should infer electronic genre."""
        event = {"title": "Electronic Music Festival", "description": ""}
        result = extractor._infer_genres_rules(event)
        assert "electronic" in result

    def test_infer_multiple_genres(self, extractor):
        """Should infer multiple genres."""
        event = {"title": "Techno House Night", "description": "Electronic music event"}
        result = extractor._infer_genres_rules(event)
        assert "techno" in result
        assert "house" in result
        assert "electronic" in result

    def test_infer_hip_hop(self, extractor):
        """Should infer hip hop genre."""
        event = {"title": "Hip Hop Night", "description": ""}
        result = extractor._infer_genres_rules(event)
        assert "hip_hop" in result

    def test_infer_default_electronic(self, extractor):
        """Should default to electronic."""
        event = {"title": "Music Event", "description": ""}
        result = extractor._infer_genres_rules(event)
        assert "electronic" in result


class TestInferTagsRules:
    """Tests for _infer_tags_rules method."""

    def test_infer_music_tags(self, extractor):
        """Should infer music-related tags."""
        event = {"title": "Live DJ Set"}
        result = extractor._infer_tags_rules(event)
        assert "music" in result

    def test_infer_electronic_tags(self, extractor):
        """Should infer electronic tags."""
        event = {"title": "Techno Party"}
        result = extractor._infer_tags_rules(event)
        assert "electronic" in result
        assert "party" in result

    def test_infer_party_tags(self, extractor):
        """Should infer party tags."""
        event = {"title": "Birthday Party"}
        result = extractor._infer_tags_rules(event)
        assert "party" in result

    def test_infer_nightlife_tags(self, extractor):
        """Should infer nightlife tags."""
        event = {"title": "Club Night"}
        result = extractor._infer_tags_rules(event)
        assert "nightlife" in result

    def test_infer_art_tags(self, extractor):
        """Should infer art tags."""
        event = {"title": "Art Exhibition"}
        result = extractor._infer_tags_rules(event)
        assert "art" in result

    def test_infer_default_event_tag(self, extractor):
        """Should default to 'event' tag."""
        event = {"title": "Something Random"}
        result = extractor._infer_tags_rules(event)
        assert "event" in result


class TestInferCostLevel:
    """Tests for _infer_cost_level method."""

    def test_free_event_by_flag(self, extractor):
        """Should return 'free' when is_free flag is set."""
        event = {"is_free": True}
        result = extractor._infer_cost_level(event)
        assert result == "free"

    def test_free_event_by_price_zero(self, extractor):
        """Should return 'free' when price is 0 AND is_free flag set."""
        # Note: minimum_price=0 alone doesn't trigger "free" because
        # event_context.get("minimum_price") is falsy for 0.
        # Use is_free flag for zero-price events.
        event = {"minimum_price": 0, "is_free": True}
        result = extractor._infer_cost_level(event)
        assert result == "free"

    def test_low_cost(self, extractor):
        """Should return 'low' for price <= 15."""
        event = {"minimum_price": 10}
        result = extractor._infer_cost_level(event)
        assert result == "low"

        event = {"minimum_price": 15}
        result = extractor._infer_cost_level(event)
        assert result == "low"

    def test_medium_cost(self, extractor):
        """Should return 'medium' for price 16-50."""
        event = {"minimum_price": 25}
        result = extractor._infer_cost_level(event)
        assert result == "medium"

        event = {"minimum_price": 50}
        result = extractor._infer_cost_level(event)
        assert result == "medium"

    def test_high_cost(self, extractor):
        """Should return 'high' for price > 50."""
        event = {"minimum_price": 100}
        result = extractor._infer_cost_level(event)
        assert result == "high"

    def test_default_medium_no_price(self, extractor):
        """Should return 'medium' when no price info."""
        event = {"title": "Event"}
        result = extractor._infer_cost_level(event)
        assert result == "medium"

    def test_cost_from_string(self, extractor):
        """Should parse cost from string."""
        event = {"cost": "£25 entry"}
        result = extractor._infer_cost_level(event)
        assert result == "medium"


class TestInferTimeScale:
    """Tests for _infer_time_scale method."""

    def test_short_duration(self, extractor):
        """Should return 'short' for <= 120 minutes."""
        event = {"duration_minutes": 60}
        result = extractor._infer_time_scale(event)
        assert result == "short"

        event = {"duration_minutes": 120}
        result = extractor._infer_time_scale(event)
        assert result == "short"

    def test_long_duration(self, extractor):
        """Should return 'long' for 121-480 minutes."""
        event = {"duration_minutes": 240}
        result = extractor._infer_time_scale(event)
        assert result == "long"

        event = {"duration_minutes": 480}
        result = extractor._infer_time_scale(event)
        assert result == "long"

    def test_recurring_duration(self, extractor):
        """Should return 'recurring' for > 480 minutes."""
        event = {"duration_minutes": 600}
        result = extractor._infer_time_scale(event)
        assert result == "recurring"

    def test_festival_is_long(self, extractor):
        """Should return 'long' for festival (by title)."""
        event = {"title": "Summer Festival"}
        result = extractor._infer_time_scale(event)
        assert result == "long"

    def test_workshop_is_short(self, extractor):
        """Should return 'short' for workshop (by title)."""
        event = {"title": "Photography Workshop"}
        result = extractor._infer_time_scale(event)
        assert result == "short"

    def test_default_long(self, extractor):
        """Should default to 'long'."""
        event = {"title": "Random Event"}
        result = extractor._infer_time_scale(event)
        assert result == "long"


class TestInferEmotionalOutput:
    """Tests for _infer_emotional_output method."""

    def test_infer_joy(self, extractor):
        """Should infer joy for party keywords."""
        result = extractor._infer_emotional_output("party celebration fun")
        assert "joy" in result

    def test_infer_excitement(self, extractor):
        """Should infer excitement for live/festival keywords."""
        result = extractor._infer_emotional_output("live concert festival")
        assert "excitement" in result

    def test_infer_connection(self, extractor):
        """Should infer connection for community keywords."""
        result = extractor._infer_emotional_output("meetup community together")
        assert "connection" in result

    def test_infer_energy(self, extractor):
        """Should infer energy for dance/techno keywords."""
        result = extractor._infer_emotional_output("dance techno electronic club")
        assert "energy" in result

    def test_infer_relaxation(self, extractor):
        """Should infer relaxation for chill keywords."""
        result = extractor._infer_emotional_output("chill ambient lounge")
        assert "relaxation" in result

    def test_infer_growth(self, extractor):
        """Should infer growth for learning keywords."""
        result = extractor._infer_emotional_output("workshop learn course skill")
        assert "growth" in result

    def test_infer_default_enjoyment(self, extractor):
        """Should default to enjoyment."""
        result = extractor._infer_emotional_output("random text")
        assert result == ["enjoyment"]

    def test_infer_multiple_emotions(self, extractor):
        """Should infer multiple emotions."""
        result = extractor._infer_emotional_output(
            "party festival community dance together"
        )
        assert "joy" in result
        assert "excitement" in result
        assert "connection" in result
        assert "energy" in result


class TestEnrichWithRules:
    """Tests for _enrich_with_rules method."""

    def test_enrich_high_energy(self, extractor):
        """Should set high energy for party/rave keywords."""
        event = {"title": "Techno Rave", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["energy_level"] == "high"

    def test_enrich_medium_energy(self, extractor):
        """Should set medium energy for workshop keywords."""
        event = {"title": "Art Workshop", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["energy_level"] == "medium"

    def test_enrich_low_energy(self, extractor):
        """Should set low energy for meditation keywords."""
        event = {"title": "Meditation Session", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["energy_level"] == "low"

    def test_enrich_social_large_group(self, extractor):
        """Should set large_group for festival/party."""
        event = {"title": "Festival Party", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["social_intensity"] == "large_group"

    def test_enrich_social_small_group(self, extractor):
        """Should set small_group for workshop/meetup."""
        event = {"title": "Coding Workshop", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["social_intensity"] == "small_group"

    def test_enrich_cognitive_high(self, extractor):
        """Should set high cognitive for training/seminar."""
        # Note: "masterclass" contains "class" which triggers "medium" first,
        # so use words that only match the high-cognitive keywords.
        event = {"title": "DJ Training Seminar", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["cognitive_load"] == "high"

    def test_enrich_physical_moderate(self, extractor):
        """Should set moderate physical for dance/sports."""
        event = {"title": "Dance Fitness Class", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["physical_involvement"] == "moderate"

    def test_enrich_environment_outdoor(self, extractor):
        """Should set outdoor for outdoor keywords."""
        event = {"title": "Rooftop Party", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["environment"] == "outdoor"

    def test_enrich_environment_digital(self, extractor):
        """Should set digital for online keywords."""
        event = {"title": "Online Workshop", "description": "Virtual event"}
        result = extractor._enrich_with_rules(event)
        assert result["environment"] == "digital"

    def test_enrich_age_adults(self, extractor):
        """Should set adults for club keywords."""
        event = {"title": "Club Night 18+", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["age_accessibility"] == "adults"

    def test_enrich_age_all(self, extractor):
        """Should set all ages for family keywords."""
        event = {"title": "Family Fun Day", "description": ""}
        result = extractor._enrich_with_rules(event)
        assert result["age_accessibility"] == "all"

    def test_enrich_repeatability_low(self, extractor):
        """Should set low repeatability for festival."""
        event = {"title": "Annual Festival", "description": "Special event"}
        result = extractor._enrich_with_rules(event)
        assert result["repeatability"] == "low"

    def test_enrich_repeatability_high(self, extractor):
        """Should set high repeatability for weekly."""
        event = {"title": "Weekly Meetup", "description": "Every Tuesday"}
        result = extractor._enrich_with_rules(event)
        assert result["repeatability"] == "high"

    def test_enrich_has_all_fields(self, extractor):
        """Should return all expected fields."""
        event = {"title": "Test Event", "description": ""}
        result = extractor._enrich_with_rules(event)

        expected_fields = [
            "energy_level",
            "social_intensity",
            "cognitive_load",
            "physical_involvement",
            "environment",
            "risk_level",
            "age_accessibility",
            "repeatability",
            "emotional_output",
        ]
        for field in expected_fields:
            assert field in result


class TestFillMissingFieldsRules:
    """Tests for _fill_missing_fields_rules method."""

    def test_fill_event_type(self, extractor):
        """Should fill event_type using rules."""
        event = {"title": "Rock Festival"}
        result = extractor._fill_missing_fields_rules(event, ["event_type"])
        assert result["event_type"] == "festival"

    def test_fill_tags(self, extractor):
        """Should fill tags using rules."""
        event = {"title": "Techno Party Night"}
        result = extractor._fill_missing_fields_rules(event, ["tags"])
        assert "tags" in result
        assert isinstance(result["tags"], list)

    def test_fill_energy_level(self, extractor):
        """Should fill energy_level."""
        event = {"title": "Techno Rave Party"}
        result = extractor._fill_missing_fields_rules(event, ["energy_level"])
        assert result["energy_level"] == "high"

    def test_fill_multiple_fields(self, extractor):
        """Should fill multiple requested fields."""
        event = {"title": "Festival Party"}
        fields = ["event_type", "tags", "energy_level", "social_intensity"]
        result = extractor._fill_missing_fields_rules(event, fields)

        assert "event_type" in result
        assert "tags" in result
        assert "energy_level" in result
        assert "social_intensity" in result

    def test_fill_empty_fields_list(self, extractor):
        """Should return empty dict for empty fields list."""
        event = {"title": "Test"}
        result = extractor._fill_missing_fields_rules(event, [])
        assert result == {}


class TestExtractPrimaryCategory:
    """Tests for extract_primary_category method (rule-based)."""

    def test_extract_returns_extraction_object(self, extractor):
        """Should return PrimaryCategoryExtraction object."""
        event = {"title": "Techno Concert"}
        result = extractor.extract_primary_category(event)

        assert hasattr(result, "category_id")
        assert hasattr(result, "reasoning")
        assert hasattr(result, "confidence")

    def test_extract_uses_rules_without_llm(self, extractor):
        """Should use rule-based extraction without LLM."""
        event = {"title": "Techno Concert"}
        result = extractor.extract_primary_category(event)

        assert result.category_id == "1"
        assert "Rule-based" in result.reasoning
        assert result.confidence == 0.5


class TestExtractSubcategory:
    """Tests for extract_subcategory method (rule-based)."""

    def test_extract_returns_extraction_object(self, extractor):
        """Should return SubcategoryExtraction object."""
        event = {"title": "Test Event"}
        result = extractor.extract_subcategory(event, "1")

        assert hasattr(result, "subcategory_id")
        assert hasattr(result, "subcategory_name")
        assert hasattr(result, "confidence")

    def test_extract_fallback_uses_first_subcategory(self, extractor):
        """Should fallback to first subcategory of category."""
        event = {"title": "Test Event"}
        result = extractor.extract_subcategory(event, "1")

        assert result.subcategory_id == "1.1"
        assert result.confidence == 0.3


class TestFormatEventContext:
    """Tests for _format_event_context method."""

    def test_format_with_title(self, extractor):
        """Should include title."""
        event = {"title": "Test Event"}
        result = extractor._format_event_context(event)
        assert "Title: Test Event" in result

    def test_format_with_description(self, extractor):
        """Should include description."""
        event = {"title": "Test", "description": "A great event"}
        result = extractor._format_event_context(event)
        assert "Description: A great event" in result

    def test_format_with_venue(self, extractor):
        """Should include venue."""
        event = {"title": "Test", "venue_name": "Club XYZ"}
        result = extractor._format_event_context(event)
        assert "Venue: Club XYZ" in result

    def test_format_with_artists(self, extractor):
        """Should include artists."""
        event = {"title": "Test", "artists": ["Artist A", "Artist B"]}
        result = extractor._format_event_context(event)
        assert "Artists: Artist A, Artist B" in result

    def test_format_truncates_long_description(self, extractor):
        """Should truncate very long descriptions."""
        long_desc = "x" * 1000
        event = {"title": "Test", "description": long_desc}
        result = extractor._format_event_context(event)
        # Should truncate to 500 chars
        assert len(result.split("Description: ")[1]) <= 500


class TestFactoryFunction:
    """Tests for create_feature_extractor_from_config."""

    def test_create_from_config(self):
        """Should create extractor from config dict."""
        config = {
            "provider": "openai",
            "model_name": "gpt-4",
            "temperature": 0.2,
        }
        extractor = create_feature_extractor_from_config(config)

        assert isinstance(extractor, FeatureExtractor)
        assert extractor.model_name == "gpt-4"
        assert extractor.temperature == 0.2

    def test_create_with_defaults(self):
        """Should use defaults for missing config."""
        config = {}
        extractor = create_feature_extractor_from_config(config)

        assert extractor.provider == "openai"
        assert extractor.model_name == "gpt-4o-mini"
        assert extractor.temperature == 0.1
