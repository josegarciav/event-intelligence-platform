"""
Unit tests for the taxonomy_mapper module.

Tests for TaxonomyMapper rule evaluation and dimension creation.
"""

import pytest

from src.ingestion.normalization.taxonomy_mapper import (
    TaxonomyMapper,
    create_taxonomy_mapper_from_config,
)
from src.schemas.event import PrimaryCategory
from src.schemas.taxonomy import get_all_subcategory_ids


@pytest.fixture
def valid_subcategory_id():
    """Get a valid subcategory ID for testing."""
    all_ids = get_all_subcategory_ids()
    # Find a subcategory starting with "1." for play_and_fun
    for sub_id in all_ids:
        if sub_id.startswith("1."):
            return sub_id
    return "1.1"


@pytest.fixture
def basic_mapper(valid_subcategory_id):
    """Create a basic TaxonomyMapper for testing."""
    return TaxonomyMapper(
        {
            "default_primary": "play_and_fun",
            "default_subcategory": valid_subcategory_id,
            "rules": [],
        }
    )


class TestTaxonomyMapperInit:
    """Tests for TaxonomyMapper initialization."""

    def test_init_with_defaults(self, valid_subcategory_id):
        """Should initialize with defaults."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
            }
        )
        assert mapper.default_primary == "play_and_fun"
        assert mapper.default_subcategory == valid_subcategory_id
        assert mapper.rules == []

    def test_init_with_numeric_id(self, valid_subcategory_id):
        """Should accept numeric ID for primary category."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "1",
                "default_subcategory": valid_subcategory_id,
            }
        )
        assert mapper.default_primary == "play_and_fun"

    def test_init_with_rules(self, valid_subcategory_id):
        """Should store rules."""
        rules = [
            {"match": {"always": True}, "assign": {"primary_category": "play_and_fun"}}
        ]
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
                "rules": rules,
            }
        )
        assert len(mapper.rules) == 1

    def test_init_invalid_subcategory_primary_mismatch(self):
        """Should raise when subcategory doesn't match primary."""
        # Get a subcategory starting with "2." for different category
        all_ids = get_all_subcategory_ids()
        cat2_sub = None
        for sub_id in all_ids:
            if sub_id.startswith("2."):
                cat2_sub = sub_id
                break

        if cat2_sub:
            with pytest.raises(ValueError, match="does not belong to"):
                TaxonomyMapper(
                    {
                        "default_primary": "play_and_fun",  # Category 1
                        "default_subcategory": cat2_sub,  # Category 2 subcategory
                    }
                )

    def test_init_invalid_primary_fallback(self, valid_subcategory_id):
        """Should fallback to play_and_fun for invalid primary."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "invalid_category",
                "default_subcategory": valid_subcategory_id,
            }
        )
        assert mapper.default_primary == "play_and_fun"


class TestEvaluateMatch:
    """Tests for _evaluate_match method."""

    def test_always_condition(self, basic_mapper):
        """Should match when 'always' is true."""
        event = {"title": "Test Event"}
        assert basic_mapper._evaluate_match(event, {"always": True}) is True

    def test_title_contains_match(self, basic_mapper):
        """Should match when title contains keyword."""
        event = {"title": "Techno Party Night"}
        assert (
            basic_mapper._evaluate_match(event, {"title_contains": ["techno", "house"]})
            is True
        )

    def test_title_contains_no_match(self, basic_mapper):
        """Should not match when title doesn't contain keyword."""
        event = {"title": "Jazz Concert"}
        assert (
            basic_mapper._evaluate_match(event, {"title_contains": ["techno", "house"]})
            is False
        )

    def test_title_contains_case_insensitive(self, basic_mapper):
        """Should match case-insensitively."""
        event = {"title": "TECHNO PARTY"}
        assert (
            basic_mapper._evaluate_match(event, {"title_contains": ["techno"]}) is True
        )

    def test_description_contains_match(self, basic_mapper):
        """Should match when description contains keyword."""
        event = {"description": "Join us for a night of electronic music"}
        assert (
            basic_mapper._evaluate_match(
                event, {"description_contains": ["electronic"]}
            )
            is True
        )

    def test_description_contains_no_match(self, basic_mapper):
        """Should not match when description doesn't contain keyword."""
        event = {"description": "Classical music concert"}
        assert (
            basic_mapper._evaluate_match(
                event, {"description_contains": ["electronic"]}
            )
            is False
        )

    def test_field_equals_match(self, basic_mapper):
        """Should match when field equals value."""
        event = {"event_type": "concert"}
        assert (
            basic_mapper._evaluate_match(
                event, {"field_equals": {"event_type": "concert"}}
            )
            is True
        )

    def test_field_equals_no_match(self, basic_mapper):
        """Should not match when field doesn't equal value."""
        event = {"event_type": "workshop"}
        assert (
            basic_mapper._evaluate_match(
                event, {"field_equals": {"event_type": "concert"}}
            )
            is False
        )

    def test_field_in_match(self, basic_mapper):
        """Should match when field value in list."""
        event = {"event_type": "concert"}
        assert (
            basic_mapper._evaluate_match(
                event, {"field_in": {"event_type": ["concert", "festival", "party"]}}
            )
            is True
        )

    def test_field_in_no_match(self, basic_mapper):
        """Should not match when field value not in list."""
        event = {"event_type": "workshop"}
        assert (
            basic_mapper._evaluate_match(
                event, {"field_in": {"event_type": ["concert", "festival"]}}
            )
            is False
        )

    def test_regex_match(self, basic_mapper):
        """Should match with regex pattern."""
        event = {"title": "Festival 2024 - Electronic Music"}
        assert (
            basic_mapper._evaluate_match(
                event, {"regex": {"title": r"festival.*\d{4}"}}
            )
            is True
        )

    def test_regex_no_match(self, basic_mapper):
        """Should not match when regex doesn't match."""
        event = {"title": "Regular Party Night"}
        assert (
            basic_mapper._evaluate_match(
                event, {"regex": {"title": r"festival.*\d{4}"}}
            )
            is False
        )

    def test_no_conditions(self, basic_mapper):
        """Should match when no specific conditions."""
        event = {"title": "Any Event"}
        assert basic_mapper._evaluate_match(event, {}) is True

    def test_multiple_conditions_all_match(self, basic_mapper):
        """Should match when all conditions match."""
        event = {
            "title": "Techno Festival",
            "event_type": "festival",
        }
        match_config = {
            "title_contains": ["techno"],
            "field_equals": {"event_type": "festival"},
        }
        assert basic_mapper._evaluate_match(event, match_config) is True

    def test_multiple_conditions_one_fails(self, basic_mapper):
        """Should not match when any condition fails."""
        event = {
            "title": "Jazz Festival",
            "event_type": "festival",
        }
        match_config = {
            "title_contains": ["techno"],  # Fails
            "field_equals": {"event_type": "festival"},  # Passes
        }
        assert basic_mapper._evaluate_match(event, match_config) is False


class TestCreateDimension:
    """Tests for _create_dimension method."""

    def test_create_with_category(self, valid_subcategory_id):
        """Should create dimension with primary category."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
            }
        )
        event = {"title": "Test Event"}
        dim = mapper._create_dimension(
            event,
            {
                "primary_category": "play_and_fun",
                "subcategory": valid_subcategory_id,
                "confidence": 0.8,
            },
        )

        assert dim is not None
        assert dim.primary_category == PrimaryCategory.PLAY_AND_PURE_FUN
        assert dim.subcategory == valid_subcategory_id
        assert dim.confidence == 0.8

    def test_create_with_numeric_category_id(self, valid_subcategory_id):
        """Should accept numeric ID for primary category."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "1",
                "default_subcategory": valid_subcategory_id,
            }
        )
        event = {"title": "Test Event"}
        dim = mapper._create_dimension(
            event,
            {
                "primary_category": "1",
                "subcategory": valid_subcategory_id,
            },
        )

        assert dim is not None
        assert dim.primary_category == PrimaryCategory.PLAY_AND_PURE_FUN

    def test_create_with_values(self, valid_subcategory_id):
        """Should include provided values."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
            }
        )
        event = {"title": "Test Event"}
        dim = mapper._create_dimension(
            event,
            {
                "primary_category": "play_and_fun",
                "subcategory": valid_subcategory_id,
                "values": ["energy", "excitement"],
            },
        )

        assert dim is not None
        assert dim.values == ["energy", "excitement"]

    def test_create_invalid_primary_returns_none(self, valid_subcategory_id):
        """Should return None for invalid primary category."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
            }
        )
        event = {"title": "Test Event"}
        dim = mapper._create_dimension(
            event,
            {
                "primary_category": "not_a_category",
            },
        )

        assert dim is None

    def test_create_mismatched_subcategory_returns_none(self):
        """Should return None when subcategory doesn't match primary."""
        # Get subcategories for different categories
        all_ids = get_all_subcategory_ids()
        cat1_sub = None
        cat2_sub = None
        for sub_id in all_ids:
            if sub_id.startswith("1.") and not cat1_sub:
                cat1_sub = sub_id
            elif sub_id.startswith("2.") and not cat2_sub:
                cat2_sub = sub_id

        if cat1_sub and cat2_sub:
            mapper = TaxonomyMapper(
                {
                    "default_primary": "play_and_fun",
                    "default_subcategory": cat1_sub,
                }
            )
            event = {"title": "Test Event"}
            dim = mapper._create_dimension(
                event,
                {
                    "primary_category": "play_and_fun",  # Category 1
                    "subcategory": cat2_sub,  # Category 2 subcategory
                },
            )

            assert dim is None


class TestMapEvent:
    """Tests for map_event method."""

    def test_map_with_matching_rule(self, valid_subcategory_id):
        """Should apply first matching rule."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
                "rules": [
                    {
                        "match": {"title_contains": ["techno"]},
                        "assign": {
                            "primary_category": "play_and_fun",
                            "subcategory": valid_subcategory_id,
                            "confidence": 0.9,
                        },
                    },
                ],
            }
        )

        event = {"title": "Techno Night"}
        primary, dimensions = mapper.map_event(event)

        assert primary == "play_and_fun"
        assert len(dimensions) == 1
        assert dimensions[0].confidence == 0.9

    def test_map_no_rules_match_uses_default(self, valid_subcategory_id):
        """Should use defaults when no rules match."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
                "rules": [
                    {
                        "match": {"title_contains": ["techno"]},
                        "assign": {"primary_category": "play_and_fun"},
                    },
                ],
            }
        )

        event = {"title": "Jazz Concert"}
        primary, dimensions = mapper.map_event(event)

        assert primary == "play_and_fun"
        assert len(dimensions) == 1
        assert dimensions[0].subcategory == valid_subcategory_id

    def test_map_multiple_rules_match(self, valid_subcategory_id):
        """Should return dimensions from all matching rules."""
        # Get different subcategories for the same category
        all_ids = get_all_subcategory_ids()
        cat1_subs = [sid for sid in all_ids if sid.startswith("1.")]

        if len(cat1_subs) >= 2:
            sub1, sub2 = cat1_subs[0], cat1_subs[1]

            mapper = TaxonomyMapper(
                {
                    "default_primary": "play_and_fun",
                    "default_subcategory": sub1,
                    "rules": [
                        {
                            "match": {"title_contains": ["music"]},
                            "assign": {
                                "primary_category": "play_and_fun",
                                "subcategory": sub1,
                            },
                        },
                        {
                            "match": {"title_contains": ["party"]},
                            "assign": {
                                "primary_category": "play_and_fun",
                                "subcategory": sub2,
                            },
                        },
                    ],
                }
            )

            event = {"title": "Music Party Night"}
            primary, dimensions = mapper.map_event(event)

            # Both rules should match
            assert len(dimensions) == 2

    def test_map_always_rule(self, valid_subcategory_id):
        """Should match 'always' rule."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
                "rules": [
                    {
                        "match": {"always": True},
                        "assign": {
                            "primary_category": "play_and_fun",
                            "subcategory": valid_subcategory_id,
                            "confidence": 0.95,
                        },
                    },
                ],
            }
        )

        event = {"title": "Any Event"}
        primary, dimensions = mapper.map_event(event)

        assert len(dimensions) == 1
        assert dimensions[0].confidence == 0.95


class TestGetFullTaxonomyData:
    """Tests for get_full_taxonomy_data method."""

    def test_returns_full_data(self, valid_subcategory_id):
        """Should return full taxonomy dimension data."""
        mapper = TaxonomyMapper(
            {
                "default_primary": "play_and_fun",
                "default_subcategory": valid_subcategory_id,
                "rules": [
                    {
                        "match": {"always": True},
                        "assign": {
                            "primary_category": "play_and_fun",
                            "subcategory": valid_subcategory_id,
                        },
                    },
                ],
            }
        )

        event = {"title": "Test Event", "description": "A fun event"}
        primary, full_dims = mapper.get_full_taxonomy_data(event)

        assert primary == "play_and_fun"
        assert len(full_dims) == 1
        assert "primary_category" in full_dims[0]
        assert "subcategory" in full_dims[0]


class TestFactoryFunction:
    """Tests for create_taxonomy_mapper_from_config."""

    def test_create_from_config(self, valid_subcategory_id):
        """Should create mapper from config dict."""
        config = {
            "default_primary": "play_and_fun",
            "default_subcategory": valid_subcategory_id,
            "rules": [{"match": {"always": True}, "assign": {}}],
        }
        mapper = create_taxonomy_mapper_from_config(config)

        assert isinstance(mapper, TaxonomyMapper)
        assert mapper.default_primary == "play_and_fun"

    def test_create_with_minimal_config(self):
        """Should handle minimal config."""
        config = {}
        mapper = create_taxonomy_mapper_from_config(config)

        assert isinstance(mapper, TaxonomyMapper)
        assert mapper.default_primary == "play_and_fun"
