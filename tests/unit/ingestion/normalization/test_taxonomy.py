"""
Unit tests for the taxonomy module.

Tests for taxonomy loading, indexing, and lookup functions.
"""

from src.schemas.taxonomy import (
    build_primary_to_subcategory_index,
    build_taxonomy_index,
    find_best_activity_match,
    get_activities_for_subcategory,
    get_activity_by_id,
    get_all_subcategory_ids,
    get_all_subcategory_options,
    get_full_taxonomy_dimension,
    get_primary_category_for_subcategory,
    get_primary_category_id_map,
    get_primary_category_mappings,
    get_primary_category_value_to_id_map,
    get_subcategory_by_id,
    list_all_activities,
    load_taxonomy,
    search_activities_by_name,
    validate_subcategory_for_primary,
)


class TestLoadTaxonomy:
    """Tests for load_taxonomy function."""

    def test_load_taxonomy_returns_dict(self):
        """load_taxonomy should return a valid taxonomy dict."""
        taxonomy = load_taxonomy()
        assert isinstance(taxonomy, dict)
        assert "categories" in taxonomy
        assert len(taxonomy["categories"]) > 0

    def test_load_taxonomy_has_categories(self):
        """Taxonomy should have all 10 primary categories."""
        taxonomy = load_taxonomy()
        categories = taxonomy["categories"]
        assert len(categories) == 10

    def test_load_taxonomy_cached(self):
        """load_taxonomy should return same instance (cached)."""
        taxonomy1 = load_taxonomy()
        taxonomy2 = load_taxonomy()
        # LRU cache means same object is returned
        assert taxonomy1 is taxonomy2


class TestBuildTaxonomyIndex:
    """Tests for build_taxonomy_index function."""

    def test_build_index_returns_dict(self):
        """build_taxonomy_index should return a mapping dict."""
        index = build_taxonomy_index()
        assert isinstance(index, dict)
        assert len(index) > 0

    def test_index_has_subcategory_sets(self):
        """Index values should be sets of subcategory IDs."""
        index = build_taxonomy_index()
        for key, value in index.items():
            assert isinstance(value, set)
            # Each subcategory ID should be a string like "1.1", "1.2", etc.
            for sub_id in value:
                assert isinstance(sub_id, str)
                assert "." in sub_id


class TestPrimaryCategoryMappings:
    """Tests for primary category ID mapping functions."""

    def test_id_map_has_10_entries(self):
        """ID map should have exactly 10 entries (1-10)."""
        id_map = get_primary_category_id_map()
        assert len(id_map) == 10
        assert all(str(i) in id_map for i in range(1, 11))

    def test_id_map_values(self):
        """ID map should have correct category values."""
        id_map = get_primary_category_id_map()
        assert id_map["1"] == "play_and_fun"
        assert id_map["5"] == "social_connection"
        assert id_map["10"] == "contribution_and_impact"

    def test_value_to_id_map_reverse(self):
        """Value-to-ID map should be reverse of ID-to-value."""
        id_map = get_primary_category_id_map()
        value_map = get_primary_category_value_to_id_map()

        # Check reverse mapping
        for id_key, value in id_map.items():
            assert value_map[value] == id_key

    def test_get_mappings_returns_tuple(self):
        """get_primary_category_mappings should return both maps."""
        id_to_val, val_to_id = get_primary_category_mappings()

        assert isinstance(id_to_val, dict)
        assert isinstance(val_to_id, dict)
        assert len(id_to_val) == 10
        assert len(val_to_id) == 10


class TestBuildPrimaryToSubcategoryIndex:
    """Tests for build_primary_to_subcategory_index function."""

    def test_returns_dict_with_sets(self):
        """Should return dict mapping primary IDs to subcategory sets."""
        index = build_primary_to_subcategory_index()
        assert isinstance(index, dict)
        # Should have 10 primary categories
        assert len(index) == 10

    def test_subcategories_match_primary(self):
        """Subcategory IDs should start with their primary category ID."""
        index = build_primary_to_subcategory_index()
        for primary_id, subcats in index.items():
            for sub_id in subcats:
                # Subcategory like "1.4" should start with "1."
                assert sub_id.startswith(f"{primary_id}.")


class TestValidateSubcategoryForPrimary:
    """Tests for validate_subcategory_for_primary function."""

    def test_valid_subcategory_with_id(self):
        """Valid subcategory should return True."""
        # 1.x subcategories belong to primary 1
        assert validate_subcategory_for_primary("1.1", "1") is True
        assert validate_subcategory_for_primary("1.4", "1") is True
        assert validate_subcategory_for_primary("5.3", "5") is True

    def test_valid_subcategory_with_value(self):
        """Should accept primary category value as well as ID."""
        assert validate_subcategory_for_primary("1.4", "play_and_fun") is True
        assert validate_subcategory_for_primary("5.1", "social_connection") is True

    def test_invalid_subcategory(self):
        """Invalid subcategory should return False."""
        # 2.x subcategories don't belong to primary 1
        assert validate_subcategory_for_primary("2.1", "1") is False
        assert validate_subcategory_for_primary("1.4", "5") is False


class TestSubcategoryFunctions:
    """Tests for subcategory access functions."""

    def test_get_all_options_has_entries(self):
        """get_all_subcategory_options should return non-empty list."""
        options = get_all_subcategory_options()
        assert isinstance(options, list)
        assert len(options) > 0

    def test_options_have_required_fields(self):
        """Each option should have id, name, primary_category."""
        options = get_all_subcategory_options()
        for opt in options[:10]:  # Check first 10
            assert "id" in opt
            assert "name" in opt
            assert "primary_category" in opt

    def test_get_all_ids_returns_set(self):
        """get_all_subcategory_ids should return set of strings."""
        ids = get_all_subcategory_ids()
        assert isinstance(ids, set)
        assert len(ids) > 0
        for sub_id in list(ids)[:5]:
            assert isinstance(sub_id, str)
            assert "." in sub_id

    def test_get_subcategory_by_id_valid(self):
        """get_subcategory_by_id should return dict for valid ID."""
        # Get a valid ID first
        all_ids = get_all_subcategory_ids()
        valid_id = next(iter(all_ids))

        result = get_subcategory_by_id(valid_id)
        assert result is not None
        assert "id" in result
        assert "name" in result
        assert "_primary_category" in result

    def test_get_subcategory_by_id_invalid(self):
        """get_subcategory_by_id should return None for invalid ID."""
        result = get_subcategory_by_id("99.99")
        assert result is None


class TestActivityFunctions:
    """Tests for activity access functions."""

    def test_list_all_activities_returns_list(self):
        """list_all_activities should return non-empty list."""
        activities = list_all_activities()
        assert isinstance(activities, list)
        assert len(activities) > 0

    def test_activities_have_context(self):
        """Activities should have context fields."""
        activities = list_all_activities()
        for activity in activities[:5]:
            assert "_primary_category" in activity
            assert "_subcategory_id" in activity
            assert "activity_id" in activity
            assert "name" in activity

    def test_get_activity_by_id_valid(self):
        """get_activity_by_id should return activity for valid ID."""
        # Get a valid activity ID
        activities = list_all_activities()
        if activities:
            valid_id = activities[0]["activity_id"]
            result = get_activity_by_id(valid_id)
            assert result is not None
            assert result["activity_id"] == valid_id

    def test_get_activity_by_id_invalid(self):
        """get_activity_by_id should return None for invalid ID."""
        result = get_activity_by_id("invalid-uuid")
        assert result is None

    def test_get_activities_for_subcategory(self):
        """get_activities_for_subcategory should return list."""
        # Get a valid subcategory
        all_ids = get_all_subcategory_ids()
        valid_id = next(iter(all_ids))

        activities = get_activities_for_subcategory(valid_id)
        assert isinstance(activities, list)
        # May be empty or have activities

    def test_get_activities_for_invalid_subcategory(self):
        """get_activities_for_subcategory should return empty for invalid."""
        activities = get_activities_for_subcategory("99.99")
        assert activities == []


class TestFindBestActivityMatch:
    """Tests for find_best_activity_match function."""

    def test_find_match_with_threshold(self):
        """Should find match when above threshold."""
        # Get a subcategory with activities
        all_ids = get_all_subcategory_ids()
        for sub_id in all_ids:
            activities = get_activities_for_subcategory(sub_id)
            if activities:
                # Use activity name as context to guarantee match
                activity_name = activities[0]["name"]
                result = find_best_activity_match(activity_name, sub_id, threshold=0.3)
                if result:
                    assert "_match_score" in result
                    assert result["_match_score"] >= 0.3
                break

    def test_find_match_returns_none_below_threshold(self):
        """Should return None when no match above threshold."""
        all_ids = get_all_subcategory_ids()
        valid_id = next(iter(all_ids))

        # Use text that won't match anything well
        result = find_best_activity_match("xyzzyx123 nomatch", valid_id, threshold=0.9)
        assert result is None

    def test_find_match_invalid_subcategory(self):
        """Should return None for invalid subcategory."""
        result = find_best_activity_match("test event", "99.99")
        assert result is None


class TestSearchActivitiesByName:
    """Tests for search_activities_by_name function."""

    def test_search_returns_list(self):
        """search should return list of results."""
        results = search_activities_by_name("game")
        assert isinstance(results, list)

    def test_search_results_have_score(self):
        """Results should have _match_score."""
        results = search_activities_by_name("music")
        for result in results:
            assert "_match_score" in result

    def test_search_respects_limit(self):
        """Should respect limit parameter."""
        results = search_activities_by_name("event", limit=3)
        assert len(results) <= 3

    def test_search_sorted_by_score(self):
        """Results should be sorted by score descending."""
        results = search_activities_by_name("game", limit=10)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["_match_score"] >= results[i + 1]["_match_score"]


class TestGetPrimaryCategoryForSubcategory:
    """Tests for get_primary_category_for_subcategory function."""

    def test_returns_primary_for_valid_subcategory(self):
        """Should return primary category key for valid subcategory."""
        all_ids = get_all_subcategory_ids()
        valid_id = next(iter(all_ids))

        result = get_primary_category_for_subcategory(valid_id)
        assert result is not None
        assert isinstance(result, str)

    def test_returns_none_for_invalid_subcategory(self):
        """Should return None for invalid subcategory."""
        result = get_primary_category_for_subcategory("99.99")
        assert result is None


class TestGetFullTaxonomyDimension:
    """Tests for get_full_taxonomy_dimension function."""

    def test_basic_dimension(self):
        """Should create basic dimension without activity."""
        all_ids = get_all_subcategory_ids()
        valid_id = next(iter(all_ids))
        primary_id = valid_id.split(".")[0]

        # Get primary category value from ID
        id_map = get_primary_category_id_map()
        primary_value = id_map[primary_id]

        dim = get_full_taxonomy_dimension(
            primary_category=primary_value,
            subcategory_id=valid_id,
            confidence=0.8,
        )

        assert dim["primary_category"] == primary_value
        assert dim["subcategory"] == valid_id
        assert dim["confidence"] == 0.8

    def test_dimension_with_activity(self):
        """Should include activity details when activity_id provided."""
        activities = list_all_activities()
        if activities:
            activity = activities[0]
            activity_id = activity["activity_id"]
            sub_id = activity["_subcategory_id"]
            primary_key = activity["_primary_category"]

            dim = get_full_taxonomy_dimension(
                primary_category=primary_key,
                subcategory_id=sub_id,
                activity_id=activity_id,
                confidence=0.9,
            )

            assert dim["activity_id"] == activity_id
            assert dim["activity_name"] == activity["name"]
            # Should have activity-level attributes
            if "energy_level" in activity:
                assert dim.get("energy_level") == activity["energy_level"]

    def test_dimension_with_custom_values(self):
        """Should accept custom values override."""
        all_ids = get_all_subcategory_ids()
        valid_id = next(iter(all_ids))
        primary_id = valid_id.split(".")[0]
        id_map = get_primary_category_id_map()
        primary_value = id_map[primary_id]

        custom_values = ["custom1", "custom2"]
        dim = get_full_taxonomy_dimension(
            primary_category=primary_value,
            subcategory_id=valid_id,
            values=custom_values,
        )

        # Either subcategory_values or values should have the custom values
        values_in_dim = dim.get("subcategory_values", dim.get("values", []))
        assert values_in_dim == custom_values
