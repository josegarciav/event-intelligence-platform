"""
Unit tests for the field_mapper module.

Tests for FieldMapper field extraction and transformations.
"""

from src.ingestion.normalization.field_mapper import (
    FieldMapper,
    create_field_mapper_from_config,
)


class TestExtractField:
    """Tests for _extract_field method."""

    def test_simple_field(self):
        """Should extract simple field."""
        mapper = FieldMapper({"title": "title"})
        data = {"title": "Test Event"}
        result = mapper._extract_field(data, "title")
        assert result == "Test Event"

    def test_nested_field(self):
        """Should extract nested field with dot notation."""
        mapper = FieldMapper({})
        data = {"location": {"city": "Barcelona", "venue": "Club XYZ"}}
        result = mapper._extract_field(data, "location.city")
        assert result == "Barcelona"

    def test_deeply_nested_field(self):
        """Should extract deeply nested fields."""
        mapper = FieldMapper({})
        data = {"a": {"b": {"c": {"d": {"e": "deep_value"}}}}}
        result = mapper._extract_field(data, "a.b.c.d.e")
        assert result == "deep_value"

    def test_array_index(self):
        """Should extract array element by index."""
        mapper = FieldMapper({})
        data = {"items": ["first", "second", "third"]}
        result = mapper._extract_field(data, "items[0]")
        assert result == "first"

        result = mapper._extract_field(data, "items[2]")
        assert result == "third"

    def test_array_index_nested(self):
        """Should extract nested field from array element."""
        mapper = FieldMapper({})
        data = {"images": [{"filename": "img1.jpg"}, {"filename": "img2.jpg"}]}
        result = mapper._extract_field(data, "images[0].filename")
        assert result == "img1.jpg"

    def test_array_wildcard(self):
        """Should extract all elements with wildcard."""
        mapper = FieldMapper({})
        data = {"artists": [{"name": "Artist A"}, {"name": "Artist B"}]}
        result = mapper._extract_field(data, "artists[*].name")
        assert result == ["Artist A", "Artist B"]

    def test_array_wildcard_simple(self):
        """Should return array for simple wildcard."""
        mapper = FieldMapper({})
        data = {"tags": ["tag1", "tag2", "tag3"]}
        result = mapper._extract_field(data, "tags[*]")
        assert result == ["tag1", "tag2", "tag3"]

    def test_missing_field(self):
        """Should return None for missing field."""
        mapper = FieldMapper({})
        data = {"title": "Test"}
        result = mapper._extract_field(data, "description")
        assert result is None

    def test_missing_nested(self):
        """Should return None for missing nested path."""
        mapper = FieldMapper({})
        data = {"location": {"city": "Barcelona"}}
        result = mapper._extract_field(data, "location.country.code")
        assert result is None

    def test_array_index_out_of_bounds(self):
        """Should return None for out-of-bounds index."""
        mapper = FieldMapper({})
        data = {"items": ["first"]}
        result = mapper._extract_field(data, "items[5]")
        assert result is None

    def test_array_wildcard_on_non_array(self):
        """Should return empty list when wildcard on non-array."""
        mapper = FieldMapper({})
        data = {"not_array": "string"}
        result = mapper._extract_field(data, "not_array[*].name")
        assert result == []

    def test_empty_path(self):
        """Should return data for empty path."""
        mapper = FieldMapper({})
        data = {"title": "Test"}
        result = mapper._extract_field(data, "")
        assert result == data


class TestMapEvent:
    """Tests for map_event method."""

    def test_map_full_event(self):
        """Should map all configured fields."""
        # Note: Array indexing (field[0]) must be at the root level of access
        # because the index regex captures all chars before '[' as field name.
        # Use flat structure for array fields.
        mapper = FieldMapper(
            {
                "title": "event.title",
                "city": "event.location.city",
                "first_artist": "artists[0].name",
            }
        )
        raw = {
            "event": {
                "title": "Test Concert",
                "location": {"city": "Barcelona"},
            },
            "artists": [{"name": "Artist A"}],
        }
        result = mapper.map_event(raw)
        assert result["title"] == "Test Concert"
        assert result["city"] == "Barcelona"
        assert result["first_artist"] == "Artist A"

    def test_map_with_missing_fields(self):
        """Should handle missing fields gracefully."""
        mapper = FieldMapper(
            {
                "title": "title",
                "description": "description",
            }
        )
        raw = {"title": "Test Event"}
        result = mapper.map_event(raw)
        assert result["title"] == "Test Event"
        assert result["description"] is None

    def test_map_with_transformations(self):
        """Should apply transformations after extraction."""
        mapper = FieldMapper(
            field_mappings={"title": "title"},
            transformations={"title_upper": {"type": "uppercase", "source": "title"}},
        )
        raw = {"title": "test event"}
        result = mapper.map_event(raw)
        assert result["title"] == "test event"
        assert result["title_upper"] == "TEST EVENT"


class TestTransformations:
    """Tests for transformation types."""

    def test_uppercase(self):
        """Should transform to uppercase."""
        mapper = FieldMapper(
            field_mappings={"name": "name"},
            transformations={"name": {"type": "uppercase"}},
        )
        raw = {"name": "hello"}
        result = mapper.map_event(raw)
        assert result["name"] == "HELLO"

    def test_lowercase(self):
        """Should transform to lowercase."""
        mapper = FieldMapper(
            field_mappings={"name": "name"},
            transformations={"name": {"type": "lowercase"}},
        )
        raw = {"name": "HELLO"}
        result = mapper.map_event(raw)
        assert result["name"] == "hello"

    def test_default_value(self):
        """Should set default value when None."""
        mapper = FieldMapper(
            field_mappings={"status": "status"},
            transformations={"status": {"type": "default", "value": "pending"}},
        )
        raw = {}
        result = mapper.map_event(raw)
        assert result["status"] == "pending"

    def test_default_not_applied_when_value_exists(self):
        """Should not override existing value with default."""
        mapper = FieldMapper(
            field_mappings={"status": "status"},
            transformations={"status": {"type": "default", "value": "pending"}},
        )
        raw = {"status": "active"}
        result = mapper.map_event(raw)
        assert result["status"] == "active"

    def test_template(self):
        """Should apply template with placeholders."""
        mapper = FieldMapper(
            field_mappings={"filename": "filename"},
            transformations={
                "url": {
                    "type": "template",
                    "template": "https://example.com/images/{{filename}}",
                }
            },
        )
        raw = {"filename": "image.jpg"}
        result = mapper.map_event(raw)
        assert result["url"] == "https://example.com/images/image.jpg"

    def test_template_multiple_placeholders(self):
        """Should handle multiple placeholders."""
        mapper = FieldMapper(
            field_mappings={"title": "title", "venue": "venue"},
            transformations={
                "full_name": {
                    "type": "template",
                    "template": "{{title}} at {{venue}}",
                }
            },
        )
        raw = {"title": "Concert", "venue": "Stadium"}
        result = mapper.map_event(raw)
        assert result["full_name"] == "Concert at Stadium"

    def test_regex_extract(self):
        """Should extract using regex pattern."""
        mapper = FieldMapper(
            field_mappings={"price_text": "price"},
            transformations={
                "price_value": {
                    "type": "regex",
                    "source": "price_text",
                    "pattern": r"(\d+)",
                    "group": 1,
                }
            },
        )
        raw = {"price": "£25 entry"}
        result = mapper.map_event(raw)
        assert result["price_value"] == "25"

    def test_join_list(self):
        """Should join list elements."""
        mapper = FieldMapper(
            field_mappings={"tags": "tags"},
            transformations={
                "tags_string": {
                    "type": "join",
                    "source": "tags",
                    "separator": ", ",
                }
            },
        )
        raw = {"tags": ["music", "electronic", "party"]}
        result = mapper.map_event(raw)
        assert result["tags_string"] == "music, electronic, party"

    def test_split_string(self):
        """Should split string into list."""
        mapper = FieldMapper(
            field_mappings={"genres": "genres"},
            transformations={
                "genre_list": {
                    "type": "split",
                    "source": "genres",
                    "separator": ",",
                }
            },
        )
        raw = {"genres": "techno, house, electronic"}
        result = mapper.map_event(raw)
        assert result["genre_list"] == ["techno", "house", "electronic"]

    def test_coalesce(self):
        """Should return first non-None value."""
        mapper = FieldMapper(
            field_mappings={
                "primary": "primary",
                "secondary": "secondary",
                "fallback": "fallback",
            },
            transformations={
                "value": {
                    "type": "coalesce",
                    "sources": ["primary", "secondary", "fallback"],
                }
            },
        )
        raw = {"fallback": "default_value"}
        result = mapper.map_event(raw)
        assert result["value"] == "default_value"

    def test_concat(self):
        """Should concatenate multiple fields."""
        mapper = FieldMapper(
            field_mappings={"first": "first", "second": "second"},
            transformations={
                "combined": {
                    "type": "concat",
                    "sources": ["first", "second"],
                    "separator": " - ",
                }
            },
        )
        raw = {"first": "Part A", "second": "Part B"}
        result = mapper.map_event(raw)
        assert result["combined"] == "Part A - Part B"

    def test_conditional_when(self):
        """Should only apply transformation when condition met."""
        mapper = FieldMapper(
            field_mappings={"filename": "filename"},
            transformations={
                "url": {
                    "type": "template",
                    "template": "https://example.com/{{filename}}",
                    "when": "filename",
                }
            },
        )
        # With filename
        raw = {"filename": "test.jpg"}
        result = mapper.map_event(raw)
        assert result["url"] == "https://example.com/test.jpg"

        # Without filename
        raw_empty = {}
        result_empty = mapper.map_event(raw_empty)
        assert "url" not in result_empty or result_empty.get("url") is None


class TestFactoryFunction:
    """Tests for create_field_mapper_from_config."""

    def test_create_from_config(self):
        """Should create mapper from config dict."""
        config = {
            "field_mappings": {
                "title": "event.title",
                "venue": "event.venue.name",
            },
            "transformations": {
                "title_lower": {"type": "lowercase", "source": "title"}
            },
        }
        mapper = create_field_mapper_from_config(config)

        assert isinstance(mapper, FieldMapper)
        assert "title" in mapper.field_mappings
        assert "title_lower" in mapper.transformations

    def test_create_with_empty_config(self):
        """Should handle empty config."""
        mapper = create_field_mapper_from_config({})
        assert isinstance(mapper, FieldMapper)
        assert mapper.field_mappings == {}
        assert mapper.transformations == {}

    def test_create_with_mappings_only(self):
        """Should work with only field_mappings."""
        config = {"field_mappings": {"title": "title"}}
        mapper = create_field_mapper_from_config(config)
        assert mapper.field_mappings == {"title": "title"}
        assert mapper.transformations == {}
