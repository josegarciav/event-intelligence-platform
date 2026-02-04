"""
Unit tests for the base_api module.

Tests for BaseAPIPipeline, APISourceConfig, and ConfigDrivenAPIAdapter.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from typing import Dict, Any

import pytest

from src.ingestion.pipelines.apis.base_api import (
    BaseAPIPipeline,
    APISourceConfig,
    ConfigDrivenAPIAdapter,
    create_api_pipeline_from_config,
)
from src.ingestion.base_pipeline import PipelineConfig
from src.ingestion.adapters import SourceType
from src.ingestion.normalization.event_schema import (
    EventSchema,
    EventType,
    LocationInfo,
    PrimaryCategory,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_source_config():
    """Create a sample APISourceConfig."""
    return APISourceConfig(
        source_name="test_api",
        enabled=True,
        endpoint="https://api.example.com/graphql",
        protocol="graphql",
        timeout_seconds=30,
        max_retries=3,
        query_template="query { events { id title } }",
        query_variables={"limit": 50},
        response_path="data.events",
        field_mappings={
            "title": "name",
            "source_event_id": "id",
        },
        taxonomy_config={
            "default_primary": "play_and_fun",
            "default_subcategory": "1.4",
        },
        defaults={
            "location": {
                "city": "Barcelona",
                "country_code": "ES",
                "timezone": "Europe/Madrid",
            }
        },
    )


@pytest.fixture
def sample_pipeline_config():
    """Create a sample PipelineConfig."""
    return PipelineConfig(
        source_name="test_api",
        source_type=SourceType.API,
        request_timeout=30,
    )


@pytest.fixture
def sample_raw_event():
    """Sample raw event from API."""
    return {
        "id": "12345",
        "name": "Test Concert",
        "description": "A great event",
        "startTime": "2025-06-15T20:00:00Z",
        "endTime": "2025-06-16T02:00:00Z",
        "venue": {
            "name": "Test Venue",
            "address": "123 Main St",
        },
        "cost": "€15-25",
    }


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestAPISourceConfig:
    """Tests for APISourceConfig dataclass."""

    def test_config_defaults(self):
        """Should have sensible defaults."""
        config = APISourceConfig(source_name="test")
        assert config.enabled is True
        assert config.protocol == "graphql"
        assert config.timeout_seconds == 30
        assert config.max_retries == 3
        assert config.pagination_type == "page_number"
        assert config.max_pages == 10
        assert config.default_page_size == 50

    def test_config_custom_values(self):
        """Should accept custom values."""
        config = APISourceConfig(
            source_name="custom",
            endpoint="https://api.test.com",
            protocol="rest",
            timeout_seconds=60,
            max_pages=20,
            field_mappings={"title": "name"},
        )
        assert config.source_name == "custom"
        assert config.endpoint == "https://api.test.com"
        assert config.protocol == "rest"
        assert config.timeout_seconds == 60
        assert config.max_pages == 20


class TestConfigDrivenAPIAdapterSubstitution:
    """Tests for variable substitution in ConfigDrivenAPIAdapter."""

    def test_substitute_string(self, sample_source_config):
        """Should substitute variables in strings."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        result = adapter._substitute_variables(
            "Hello {{name}}, your ID is {{id}}",
            {"name": "World", "id": "123"},
        )

        assert result == "Hello World, your ID is 123"

    def test_substitute_dict(self, sample_source_config):
        """Should substitute variables in nested dicts."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        template = {
            "filters": {
                "city": "{{city}}",
                "limit": "{{limit}}",
            }
        }
        result = adapter._substitute_variables(
            template,
            {"city": "Barcelona", "limit": "50"},
        )

        assert result["filters"]["city"] == "Barcelona"
        assert result["filters"]["limit"] == "50"

    def test_substitute_list(self, sample_source_config):
        """Should substitute variables in lists."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        result = adapter._substitute_variables(
            ["{{a}}", "{{b}}", "static"],
            {"a": "first", "b": "second"},
        )

        assert result == ["first", "second", "static"]

    def test_substitute_preserves_non_string(self, sample_source_config):
        """Should preserve non-string values."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        result = adapter._substitute_variables(42, {"x": "y"})

        assert result == 42


class TestConfigDrivenAPIAdapterParseResponse:
    """Tests for response parsing in ConfigDrivenAPIAdapter."""

    def test_parse_simple_path(self, sample_source_config):
        """Should parse simple response path."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        sample_source_config.response_path = "data.events"
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        response = {"data": {"events": [{"id": 1}, {"id": 2}]}}
        result = adapter._parse_response(response)

        assert len(result) == 2
        assert result[0]["id"] == 1

    def test_parse_with_errors(self, sample_source_config):
        """Should return empty list when errors present."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        response = {"errors": [{"message": "Query failed"}]}
        result = adapter._parse_response(response)

        assert result == []

    def test_parse_missing_path(self, sample_source_config):
        """Should return empty list for missing path."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        sample_source_config.response_path = "data.nonexistent"
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        response = {"data": {"events": []}}
        result = adapter._parse_response(response)

        assert result == []


class TestBaseAPIPipelineParseRawEvent:
    """Tests for parse_raw_event method."""

    @patch.object(ConfigDrivenAPIAdapter, "__init__", return_value=None)
    def test_parse_uses_field_mapper(
        self, mock_adapter_init, sample_pipeline_config, sample_source_config
    ):
        """Should use field mapper for parsing."""
        sample_source_config.field_mappings = {
            "title": "name",
            "source_event_id": "id",
        }

        # Manually create pipeline without full adapter initialization
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config
        pipeline.config = sample_pipeline_config
        from src.ingestion.normalization.field_mapper import FieldMapper

        pipeline.field_mapper = FieldMapper(sample_source_config.field_mappings)
        pipeline.taxonomy_mapper = MagicMock()
        pipeline.feature_extractor = None

        raw = {"name": "Test Event", "id": "123"}
        result = pipeline.parse_raw_event(raw)

        assert result["title"] == "Test Event"
        assert result["source_event_id"] == "123"


class TestBaseAPIPipelineDetermineEventType:
    """Tests for _determine_event_type method."""

    def test_determine_from_rules(self, sample_source_config):
        """Should determine event type from rules."""
        sample_source_config.event_type_rules = [
            {"match": {"title_contains": ["festival"]}, "type": "festival"},
            {"match": {"title_contains": ["concert"]}, "type": "concert"},
            {"default": True, "type": "other"},
        ]

        # Create minimal pipeline
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        event = {"title": "Summer Festival 2025"}
        result = pipeline._determine_event_type(event)

        assert result == EventType.FESTIVAL

    def test_determine_concert(self, sample_source_config):
        """Should detect concert type."""
        sample_source_config.event_type_rules = [
            {"match": {"title_contains": ["concert", "live"]}, "type": "concert"},
        ]

        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        event = {"title": "Live Concert Night"}
        result = pipeline._determine_event_type(event)

        assert result == EventType.CONCERT

    def test_determine_default(self, sample_source_config):
        """Should return None when no rules match."""
        sample_source_config.event_type_rules = [
            {"match": {"title_contains": ["festival"]}, "type": "festival"},
        ]

        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        event = {"title": "Random Event"}
        result = pipeline._determine_event_type(event)

        assert result is None


class TestBaseAPIPipelineParseDatetime:
    """Tests for _parse_datetime method."""

    def test_parse_iso_format(self, sample_source_config):
        """Should parse ISO format."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config
        pipeline.logger = MagicMock()

        result = pipeline._parse_datetime("2025-06-15T20:00:00Z")

        assert result.year == 2025
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 20

    def test_parse_iso_with_milliseconds(self, sample_source_config):
        """Should parse ISO with milliseconds."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config
        pipeline.logger = MagicMock()

        result = pipeline._parse_datetime("2025-06-15T20:00:00.123Z")

        assert result.year == 2025
        assert result.month == 6

    def test_parse_date_only(self, sample_source_config):
        """Should parse date-only format."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config
        pipeline.logger = MagicMock()

        result = pipeline._parse_datetime("2025-06-15")

        assert result.year == 2025
        assert result.month == 6
        assert result.day == 15

    def test_parse_datetime_object(self, sample_source_config):
        """Should return datetime object as-is."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config
        pipeline.logger = MagicMock()

        dt = datetime(2025, 6, 15, 20, 0)
        result = pipeline._parse_datetime(dt)

        assert result == dt

    def test_parse_none_returns_now(self, sample_source_config):
        """Should return current time for None."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config
        pipeline.logger = MagicMock()

        result = pipeline._parse_datetime(None)

        # Should be within last few seconds
        assert (datetime.now(timezone.utc) - result).total_seconds() < 5


class TestBaseAPIPipelineValidateEvent:
    """Tests for validate_event method."""

    def test_validate_required_title(self, sample_source_config, create_event):
        """Should validate required title."""
        sample_source_config.validation = {"required_fields": ["title"]}

        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        event = create_event(title="Untitled Event")  # Invalid title

        is_valid, errors = pipeline.validate_event(event)

        assert "Title is required" in errors

    def test_validate_future_event(self, sample_source_config, create_event):
        """Should warn for past events."""
        sample_source_config.validation = {"future_events_only": True}

        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        event = create_event(
            title="Past Event",
            start_datetime=datetime.now(timezone.utc) - timedelta(days=1),
        )

        is_valid, errors = pipeline.validate_event(event)

        assert any("past" in e.lower() for e in errors)

    def test_validate_city_required(self, sample_source_config, create_event):
        """Should require city."""
        sample_source_config.validation = {}

        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        event = create_event(
            title="Test Event",
            location=LocationInfo(city="", venue_name="Venue"),  # Empty city
        )

        is_valid, errors = pipeline.validate_event(event)

        assert "City is required" in errors


class TestBaseAPIPipelineEnrichEvent:
    """Tests for enrich_event method."""

    def test_enrich_calculates_duration(self, sample_source_config, create_event):
        """Should calculate duration from start/end."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=3)

        event = create_event(
            title="Test Event",
            start_datetime=start,
            end_datetime=end,
        )

        result = pipeline.enrich_event(event)

        assert result.duration_minutes == 180

    def test_enrich_sets_timezone_by_city(self, sample_source_config, create_event):
        """Should set timezone based on city."""
        sample_source_config.defaults = {"location": {}}

        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        event = create_event(
            title="Test Event",
            location=LocationInfo(city="Berlin", venue_name="Test Venue"),
        )

        result = pipeline.enrich_event(event)

        assert result.location.timezone == "Europe/Berlin"

    def test_enrich_uses_default_timezone(self, sample_source_config, create_event):
        """Should use config default timezone."""
        sample_source_config.defaults = {
            "location": {"timezone": "Europe/Madrid"}
        }

        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = sample_source_config

        event = create_event(
            title="Test Event",
            location=LocationInfo(city="Unknown City", venue_name="Test Venue"),
        )

        result = pipeline.enrich_event(event)

        assert result.location.timezone == "Europe/Madrid"


class TestCreateAPIPipelineFromConfig:
    """Tests for create_api_pipeline_from_config factory function."""

    @patch.object(BaseAPIPipeline, "__init__", return_value=None)
    def test_creates_pipeline(self, mock_init):
        """Should create pipeline from config dict."""
        config_dict = {
            "enabled": True,
            "connection": {
                "endpoint": "https://api.example.com/graphql",
                "protocol": "graphql",
            },
            "query": {
                "template": "query { events }",
                "response_path": "data.events",
            },
            "field_mappings": {"title": "name"},
            "taxonomy": {"default_primary": "play_and_fun"},
        }

        pipeline = create_api_pipeline_from_config("test_source", config_dict)

        mock_init.assert_called_once()

    def test_handles_minimal_config(self):
        """Should handle minimal configuration."""
        config_dict = {
            "enabled": True,
            "connection": {
                "endpoint": "https://api.example.com/graphql",
            },
        }

        # Should not raise
        with patch.object(BaseAPIPipeline, "__init__", return_value=None):
            pipeline = create_api_pipeline_from_config("test_source", config_dict)

    def test_extracts_pagination_config(self):
        """Should extract pagination configuration."""
        config_dict = {
            "connection": {"endpoint": "https://api.example.com"},
            "pagination": {
                "type": "cursor",
                "max_pages": 20,
                "default_page_size": 100,
            },
        }

        with patch.object(BaseAPIPipeline, "__init__", return_value=None) as mock_init:
            pipeline = create_api_pipeline_from_config("test_source", config_dict)

            # Check the source config passed to __init__
            call_args = mock_init.call_args
            source_config = call_args[0][1]  # Second positional arg
            assert source_config.pagination_type == "cursor"
            assert source_config.max_pages == 20
            assert source_config.default_page_size == 100

    def test_extracts_defaults(self):
        """Should extract defaults configuration."""
        config_dict = {
            "connection": {"endpoint": "https://api.example.com"},
            "defaults": {
                "location": {
                    "city": "Madrid",
                    "country_code": "ES",
                }
            },
        }

        with patch.object(BaseAPIPipeline, "__init__", return_value=None) as mock_init:
            pipeline = create_api_pipeline_from_config("test_source", config_dict)

            call_args = mock_init.call_args
            source_config = call_args[0][1]
            assert source_config.defaults["location"]["city"] == "Madrid"
