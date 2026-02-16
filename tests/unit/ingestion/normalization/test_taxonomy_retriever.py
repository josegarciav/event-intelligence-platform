"""
Unit tests for the taxonomy_retriever module.

Tests for TaxonomyRetriever class and related functions.
"""

import json
from unittest.mock import mock_open, patch

import pytest
from src.ingestion.normalization.taxonomy_retriever import (
    TaxonomyRetriever,
    _load_taxonomy,
    get_taxonomy_retriever,
)

# =============================================================================
# TEST DATA
# =============================================================================


MOCK_TAXONOMY = {
    "categories": [
        {
            "category_id": "1",
            "category": "Play & Pure Fun",
            "description": "Entertainment and leisure activities",
            "subcategories": [
                {
                    "id": "1.1",
                    "name": "Digital Play",
                    "values": ["gaming", "virtual"],
                    "activities": [
                        {
                            "name": "Video Gaming",
                            "activity_id": "1.1.1",
                            "energy_level": "low | medium | high",
                            "social_intensity": "solo | small_group | large_group",
                            "cognitive_load": "low | medium | high",
                            "physical_involvement": "none | light | moderate",
                            "cost_level": "free | low | medium | high",
                            "time_scale": "short | long | recurring",
                            "environment": "indoor | outdoor | digital | mixed",
                            "risk_level": "none | very_low | low | medium",
                            "age_accessibility": "all | teens+ | adults",
                            "repeatability": "high | medium | low",
                            "emotional_output": ["excitement", "joy"],
                        }
                    ],
                },
                {
                    "id": "1.4",
                    "name": "Music & Rhythm Play",
                    "values": ["expression", "energy", "flow"],
                    "activities": [
                        {
                            "name": "Dancing",
                            "activity_id": "1.4.1",
                            "energy_level": "high",
                            "emotional_output": ["joy", "energy"],
                        },
                        {
                            "name": "Live Music",
                            "activity_id": "1.4.2",
                            "energy_level": "medium",
                            "emotional_output": ["excitement"],
                        },
                    ],
                },
            ],
        },
        {
            "category_id": "2",
            "category": "Learn & Discover",
            "description": "Educational activities",
            "subcategories": [
                {
                    "id": "2.1",
                    "name": "Formal Learning",
                    "values": ["knowledge", "growth"],
                    "activities": [
                        {
                            "name": "Workshop",
                            "activity_id": "2.1.1",
                        }
                    ],
                }
            ],
        },
    ]
}


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_taxonomy_file():
    """Mock the taxonomy file loading."""
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_TAXONOMY))):
        with patch(
            "src.ingestion.normalization.taxonomy_retriever.TAXONOMY_PATH",
            "/fake/path/taxonomy.json",
        ):
            # Clear the LRU cache
            _load_taxonomy.cache_clear()
            yield


@pytest.fixture
def retriever(mock_taxonomy_file):
    """Create a TaxonomyRetriever with mocked taxonomy data."""
    # Reset singleton
    import src.ingestion.normalization.taxonomy_retriever as tr

    tr._retriever = None
    return TaxonomyRetriever()


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestTaxonomyRetrieverInit:
    """Tests for TaxonomyRetriever initialization."""

    def test_init_loads_taxonomy(self, retriever):
        """Should load taxonomy on initialization."""
        assert retriever._taxonomy is not None
        assert "categories" in retriever._taxonomy

    def test_init_builds_category_index(self, retriever):
        """Should build category index."""
        assert "1" in retriever._category_index
        assert "2" in retriever._category_index

    def test_init_builds_subcategory_index(self, retriever):
        """Should build subcategory index."""
        assert "1.1" in retriever._subcategory_index
        assert "1.4" in retriever._subcategory_index
        assert "2.1" in retriever._subcategory_index

    def test_subcategory_index_includes_parent_info(self, retriever):
        """Should include parent category info in subcategory index."""
        sub = retriever._subcategory_index.get("1.4")
        assert sub is not None
        assert sub["_category_id"] == "1"
        assert sub["_category_name"] == "Play & Pure Fun"


class TestGetFullTaxonomy:
    """Tests for get_full_taxonomy method."""

    def test_returns_full_taxonomy(self, retriever):
        """Should return the complete taxonomy."""
        result = retriever.get_full_taxonomy()
        assert result == MOCK_TAXONOMY


class TestGetCategoryById:
    """Tests for get_category_by_id method."""

    def test_returns_category(self, retriever):
        """Should return category by ID."""
        result = retriever.get_category_by_id("1")
        assert result is not None
        assert result["category"] == "Play & Pure Fun"

    def test_returns_none_for_invalid_id(self, retriever):
        """Should return None for invalid category ID."""
        result = retriever.get_category_by_id("999")
        assert result is None


class TestGetSubcategoryById:
    """Tests for get_subcategory_by_id method."""

    def test_returns_subcategory(self, retriever):
        """Should return subcategory by ID."""
        result = retriever.get_subcategory_by_id("1.4")
        assert result is not None
        assert result["name"] == "Music & Rhythm Play"

    def test_includes_parent_category_info(self, retriever):
        """Should include parent category info."""
        result = retriever.get_subcategory_by_id("1.4")
        assert result["_category_id"] == "1"
        assert result["_category_name"] == "Play & Pure Fun"

    def test_returns_none_for_invalid_id(self, retriever):
        """Should return None for invalid subcategory ID."""
        result = retriever.get_subcategory_by_id("99.99")
        assert result is None


class TestGetActivitiesForSubcategory:
    """Tests for get_activities_for_subcategory method."""

    def test_returns_activities(self, retriever):
        """Should return activities for subcategory."""
        result = retriever.get_activities_for_subcategory("1.4")
        assert len(result) == 2
        assert result[0]["name"] == "Dancing"
        assert result[1]["name"] == "Live Music"

    def test_returns_empty_for_invalid_subcategory(self, retriever):
        """Should return empty list for invalid subcategory."""
        result = retriever.get_activities_for_subcategory("99.99")
        assert result == []


class TestGetCategoryContextForPrompt:
    """Tests for get_category_context_for_prompt method."""

    def test_returns_formatted_context(self, retriever):
        """Should return formatted category context."""
        result = retriever.get_category_context_for_prompt("1")

        assert "# Category: Play & Pure Fun (ID: 1)" in result
        assert "Entertainment and leisure activities" in result
        assert "## Subcategories:" in result
        assert "### 1.1: Digital Play" in result
        assert "### 1.4: Music & Rhythm Play" in result

    def test_includes_values(self, retriever):
        """Should include subcategory values."""
        result = retriever.get_category_context_for_prompt("1")
        assert "Values: gaming, virtual" in result

    def test_includes_activities(self, retriever):
        """Should include activity examples."""
        result = retriever.get_category_context_for_prompt("1")
        assert "Activities" in result
        assert "Dancing" in result

    def test_returns_not_found_message(self, retriever):
        """Should return not found message for invalid ID."""
        result = retriever.get_category_context_for_prompt("999")
        assert "Category 999 not found" in result


class TestGetSubcategoryContextForPrompt:
    """Tests for get_subcategory_context_for_prompt method."""

    def test_returns_formatted_context(self, retriever):
        """Should return formatted subcategory context."""
        result = retriever.get_subcategory_context_for_prompt("1.4")

        assert "# Subcategory: Music & Rhythm Play (ID: 1.4)" in result
        assert "Category: Play & Pure Fun (ID: 1)" in result
        assert "Values: expression, energy, flow" in result

    def test_includes_activities_with_attributes(self, retriever):
        """Should include activities with attribute options."""
        result = retriever.get_subcategory_context_for_prompt("1.4")
        assert "## Available Activities:" in result
        assert "### Dancing" in result
        assert "Activity ID: 1.4.1" in result

    def test_includes_emotional_output(self, retriever):
        """Should include emotional output for activities."""
        result = retriever.get_subcategory_context_for_prompt("1.4")
        assert "emotional_output:" in result

    def test_returns_not_found_message(self, retriever):
        """Should return not found message for invalid ID."""
        result = retriever.get_subcategory_context_for_prompt("99.99")
        assert "Subcategory 99.99 not found" in result


class TestGetAttributeOptions:
    """Tests for get_attribute_options method."""

    def test_returns_all_attribute_options(self, retriever):
        """Should return all attribute options."""
        result = retriever.get_attribute_options()

        assert "energy_level" in result
        assert "social_intensity" in result
        assert "cognitive_load" in result
        assert "physical_involvement" in result
        assert "cost_level" in result
        assert "time_scale" in result
        assert "environment" in result
        assert "risk_level" in result
        assert "age_accessibility" in result
        assert "repeatability" in result

    def test_energy_level_options(self, retriever):
        """Should have correct energy_level options."""
        result = retriever.get_attribute_options()
        assert result["energy_level"] == ["low", "medium", "high"]

    def test_social_intensity_options(self, retriever):
        """Should have correct social_intensity options."""
        result = retriever.get_attribute_options()
        assert result["social_intensity"] == ["solo", "small_group", "large_group"]

    def test_environment_options(self, retriever):
        """Should have correct environment options."""
        result = retriever.get_attribute_options()
        assert result["environment"] == ["indoor", "outdoor", "digital", "mixed"]


class TestGetAttributeOptionsString:
    """Tests for get_attribute_options_string method."""

    def test_returns_formatted_string(self, retriever):
        """Should return formatted string with all options."""
        result = retriever.get_attribute_options_string()

        assert "## Attribute Options (select ONE for each):" in result
        assert "- energy_level: low | medium | high" in result
        assert "- social_intensity: solo | small_group | large_group" in result


class TestGetAllCategoriesSummary:
    """Tests for get_all_categories_summary method."""

    def test_returns_summary(self, retriever):
        """Should return summary of categories."""
        result = retriever.get_all_categories_summary()

        assert "## Primary Categories (select ONE):" in result
        assert "ID 1:" in result
        assert "Play & Pure Fun" in result


class TestFindBestMatchingActivity:
    """Tests for find_best_matching_activity method."""

    def test_exact_match(self, retriever):
        """Should find exact matching activity."""
        result = retriever.find_best_matching_activity(
            subcategory_id="1.4",
            event_title="Dancing Night",
        )
        assert result is not None
        assert result["name"] == "Dancing"

    def test_partial_match(self, retriever):
        """Should find partial matching activity."""
        result = retriever.find_best_matching_activity(
            subcategory_id="1.4",
            event_title="Live Music Concert",
        )
        assert result is not None
        assert result["name"] == "Live Music"

    def test_match_with_description(self, retriever):
        """Should use description for matching."""
        result = retriever.find_best_matching_activity(
            subcategory_id="1.4",
            event_title="Event Night",
            event_description="Dancing all night long",
        )
        assert result is not None
        assert result["name"] == "Dancing"

    def test_no_match_below_threshold(self, retriever):
        """Should return None when no match above threshold."""
        result = retriever.find_best_matching_activity(
            subcategory_id="1.4",
            event_title="Random Unrelated Event XYZ",
        )
        assert result is None

    def test_invalid_subcategory(self, retriever):
        """Should return None for invalid subcategory."""
        result = retriever.find_best_matching_activity(
            subcategory_id="99.99",
            event_title="Dancing Night",
        )
        assert result is None


class TestGetTaxonomyRetriever:
    """Tests for get_taxonomy_retriever singleton function."""

    def test_returns_singleton(self, mock_taxonomy_file):
        """Should return singleton instance."""
        # Reset singleton
        import src.ingestion.normalization.taxonomy_retriever as tr

        tr._retriever = None

        retriever1 = get_taxonomy_retriever()
        retriever2 = get_taxonomy_retriever()

        assert retriever1 is retriever2

    def test_creates_instance_on_first_call(self, mock_taxonomy_file):
        """Should create instance on first call."""
        import src.ingestion.normalization.taxonomy_retriever as tr

        tr._retriever = None

        retriever = get_taxonomy_retriever()
        assert retriever is not None
        assert isinstance(retriever, TaxonomyRetriever)


class TestLoadTaxonomy:
    """Tests for _load_taxonomy function."""

    def test_caches_result(self, mock_taxonomy_file):
        """Should cache the loaded taxonomy."""
        _load_taxonomy.cache_clear()

        result1 = _load_taxonomy()
        result2 = _load_taxonomy()

        assert result1 is result2
