"""
Unit tests for the base_api module.

Tests for BaseAPIPipeline, APISourceConfig, and ConfigDrivenAPIAdapter.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.pipelines.apis.base_api import (
    BaseAPIPipeline,
    APISourceConfig,
    ConfigDrivenAPIAdapter,
    create_api_pipeline_from_config,
)
from src.ingestion.base_pipeline import BasePipeline, PipelineConfig
from src.ingestion.adapters import FetchResult, SourceType
from src.schemas.event import (
    EventType,
    LocationInfo,
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

    def test_substitute_preserves_int_type(self, sample_source_config):
        """Whole-placeholder substitution should preserve int type for GraphQL."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        result = adapter._substitute_variables(
            "{{area_id}}",
            {"area_id": 20},
        )

        assert result == 20
        assert isinstance(result, int)

    def test_substitute_int_in_mixed_string_becomes_str(self, sample_source_config):
        """Embedded placeholder should still produce a string."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        result = adapter._substitute_variables(
            "area={{area_id}}&page=1",
            {"area_id": 20},
        )

        assert result == "area=20&page=1"
        assert isinstance(result, str)

    def test_substitute_preserves_types_in_nested_dict(self, sample_source_config):
        """Type preservation should work in nested structures (like GraphQL vars)."""
        from src.ingestion.adapters.api_adapter import APIAdapterConfig

        api_config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            graphql_endpoint="https://test.com",
        )
        adapter = ConfigDrivenAPIAdapter(api_config, sample_source_config)

        template = {
            "filters": {
                "areas": {"eq": "{{area_id}}"},
            },
            "pageSize": "{{page_size}}",
            "page": "{{page}}",
        }
        result = adapter._substitute_variables(
            template,
            {"area_id": 20, "page_size": 50, "page": 1},
        )

        assert result["filters"]["areas"]["eq"] == 20
        assert isinstance(result["filters"]["areas"]["eq"], int)
        assert result["pageSize"] == 50
        assert isinstance(result["pageSize"], int)
        assert result["page"] == 1


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
        sample_source_config.defaults = {"location": {"timezone": "Europe/Madrid"}}

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

        create_api_pipeline_from_config("test_source", config_dict)

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
            create_api_pipeline_from_config("test_source", config_dict)

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
            create_api_pipeline_from_config("test_source", config_dict)

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
            create_api_pipeline_from_config("test_source", config_dict)

            call_args = mock_init.call_args
            source_config = call_args[0][1]
            assert source_config.defaults["location"]["city"] == "Madrid"


# =============================================================================
# HELPER: Pipeline with mocked adapter for date-splitting tests
# =============================================================================


def _make_pipeline_for_date_splitting(source_config=None, pipeline_config=None):
    """Create a BaseAPIPipeline instance with a mock adapter for testing."""
    pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
    pipeline.source_config = source_config or APISourceConfig(
        source_name="test_api",
        max_pages=2,
        default_page_size=50,
        defaults={"days_ahead": 30},
    )
    pipeline.config = pipeline_config or PipelineConfig(
        source_name="test_api",
        source_type=SourceType.API,
    )
    pipeline.adapter = MagicMock()
    pipeline.logger = MagicMock()
    return pipeline


def _make_fetch_result(count, total_available=None, success=True):
    """Build a FetchResult with `count` dummy events."""
    return FetchResult(
        success=success,
        source_type=SourceType.API,
        raw_data=[{"id": str(i)} for i in range(count)] if success and count else [],
        total_fetched=count,
        metadata={"total_available": total_available or count},
    )


# =============================================================================
# TESTS: _fetch_with_date_splitting
# =============================================================================


class TestFetchWithDateSplitting:
    """Tests for the adaptive sliding-window fetch logic."""

    def test_single_window_non_saturated(self):
        """When all data fits in one window, no splitting occurs."""
        pipeline = _make_pipeline_for_date_splitting()
        pipeline.adapter.fetch.return_value = _make_fetch_result(30, 30)

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-08",
        )

        assert len(events) == 30
        assert pipeline.adapter.fetch.call_count == 1

    def test_saturated_window_triggers_halving(self):
        """Saturated window should shrink and retry before accepting data."""
        pipeline = _make_pipeline_for_date_splitting()

        # First call: saturated (100 available, only 50 fetched) with 7d window
        # Second call: non-saturated after halving to ~3.5d
        pipeline.adapter.fetch.side_effect = [
            _make_fetch_result(50, total_available=100),  # saturated, retry
            _make_fetch_result(40, total_available=40),  # ok, advance
            _make_fetch_result(35, total_available=35),  # ok, advance
        ]

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-08",
        )

        # First fetch was saturated, so data is NOT collected (retry with smaller window)
        # Second + third fetches collected
        assert len(events) == 40 + 35
        assert pipeline.adapter.fetch.call_count == 3

    def test_multiple_halvings_on_dense_period(self):
        """Should halve multiple times for very dense data."""
        pipeline = _make_pipeline_for_date_splitting()

        # 7d → saturated → 3.5d (84h) → saturated → 1.75d (42h) → ok
        pipeline.adapter.fetch.side_effect = [
            _make_fetch_result(50, total_available=200),  # 168h window, saturated
            _make_fetch_result(50, total_available=150),  # 84h window, saturated
            _make_fetch_result(40, total_available=40),  # 42h window, ok
            _make_fetch_result(30, total_available=30),  # next window, ok
        ]

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-04",
        )

        # Only non-saturated fetches contribute events
        assert len(events) == 40 + 30
        # Two saturated retries + two successful fetches = 4 calls
        assert pipeline.adapter.fetch.call_count == 4

    def test_saturated_at_min_window_accepts_data_with_warning(self):
        """At min window (6h), should accept partial data and warn."""
        pipeline = _make_pipeline_for_date_splitting()

        saturated = _make_fetch_result(50, total_available=500)
        non_saturated = _make_fetch_result(10, total_available=10)

        # Halving: 168h→84h→42h→21h→10h→6h (min). At 6h: accept+warn.
        # After accepting at 6h, cursor advances to 06:00.
        # Window restores to 12h → fetch [06:00..18:00], then 24h → [18:00..June 2].
        pipeline.adapter.fetch.side_effect = [
            saturated,  # 168h, retry
            saturated,  # 84h, retry
            saturated,  # 42h, retry
            saturated,  # 21h, retry
            saturated,  # 10h, retry (10//2=5, clamped to 6)
            saturated,  # 6h (min), accept + warn, advance to 06:00
            non_saturated,  # 12h [06:00..18:00], ok, advance to 18:00
            non_saturated,  # 24h [18:00..June 2], ok, done
        ]

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-02",
        )

        # Saturated window data (50) + two non-saturated windows (10 + 10)
        assert len(events) == 50 + 10 + 10
        # Verify warning was logged for the saturated-at-min case
        warning_calls = [
            c
            for c in pipeline.logger.warning.call_args_list
            if "SATURATED at min window" in str(c)
        ]
        assert len(warning_calls) >= 1

    def test_window_restores_after_non_saturated(self):
        """Window size should gradually grow back after sparse period."""
        pipeline = _make_pipeline_for_date_splitting()

        # Track the date_from in each fetch call to verify window sizing
        call_dates = []

        def track_fetch(**kwargs):
            call_dates.append((kwargs.get("date_from"), kwargs.get("date_to")))
            return _make_fetch_result(10, total_available=10)

        pipeline.adapter.fetch.side_effect = track_fetch

        pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-07-01",
        )

        # All calls should succeed (non-saturated), window stays at 7 days
        assert len(call_dates) >= 4
        # Verify the windows advance forward
        for i in range(1, len(call_dates)):
            assert call_dates[i][0] >= call_dates[i - 1][0]

    def test_empty_fetch_advances_cursor(self):
        """Empty/failed fetch should advance cursor to avoid infinite loop."""
        pipeline = _make_pipeline_for_date_splitting()

        pipeline.adapter.fetch.side_effect = [
            _make_fetch_result(0, success=True),  # empty
            _make_fetch_result(20, total_available=20),  # next window ok
        ]

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-15",
        )

        assert len(events) == 20
        assert pipeline.adapter.fetch.call_count == 2

    def test_failed_fetch_advances_cursor(self):
        """Failed fetch should advance cursor."""
        pipeline = _make_pipeline_for_date_splitting()

        pipeline.adapter.fetch.side_effect = [
            _make_fetch_result(0, success=False),  # failed
            _make_fetch_result(15, total_available=15),  # ok
        ]

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-15",
        )

        assert len(events) == 15
        assert pipeline.adapter.fetch.call_count == 2

    def test_uses_config_days_ahead_default(self):
        """Should use days_ahead from config when date_to not provided."""
        pipeline = _make_pipeline_for_date_splitting()
        pipeline.source_config.defaults = {"days_ahead": 14}
        pipeline.adapter.fetch.return_value = _make_fetch_result(10, 10)

        with patch("src.ingestion.pipelines.apis.base_api.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 6, 1, tzinfo=timezone.utc)
            mock_dt.strptime = datetime.strptime
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            events = pipeline._fetch_with_date_splitting(
                area_id=20,
                city_name="Barcelona",
                date_from="2025-06-01",
            )

        # Should have fetched events (exact count depends on window math)
        assert len(events) >= 10

    def test_full_range_coverage(self):
        """Should cover the entire date range without gaps."""
        pipeline = _make_pipeline_for_date_splitting()

        fetched_ranges = []

        def track_fetch(**kwargs):
            fetched_ranges.append((kwargs["date_from"], kwargs["date_to"]))
            return _make_fetch_result(5, total_available=5)

        pipeline.adapter.fetch.side_effect = track_fetch

        pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-22",
        )

        # Verify no gaps: each window starts where the last ended
        for i in range(1, len(fetched_ranges)):
            prev_end = fetched_ranges[i - 1][1]
            curr_start = fetched_ranges[i][0]
            assert curr_start >= prev_end or curr_start == prev_end

    def test_passes_extra_kwargs_to_adapter(self):
        """Extra kwargs should be forwarded to adapter.fetch."""
        pipeline = _make_pipeline_for_date_splitting()
        pipeline.adapter.fetch.return_value = _make_fetch_result(10, 10)

        pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-08",
            custom_param="value",
        )

        # Verify custom_param was passed through
        fetch_kwargs = pipeline.adapter.fetch.call_args[1]
        assert fetch_kwargs["custom_param"] == "value"
        assert fetch_kwargs["area_id"] == 20


class TestFetchWithDateSplittingEdgeCases:
    """Edge cases for the sliding window algorithm."""

    def test_single_day_range(self):
        """Should handle a single-day date range."""
        pipeline = _make_pipeline_for_date_splitting()
        pipeline.adapter.fetch.return_value = _make_fetch_result(5, 5)

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-02",
        )

        assert len(events) == 5
        assert pipeline.adapter.fetch.call_count == 1

    def test_same_start_end_returns_empty(self):
        """Should return empty when start == end."""
        pipeline = _make_pipeline_for_date_splitting()

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-01",
        )

        assert len(events) == 0
        assert pipeline.adapter.fetch.call_count == 0

    def test_all_windows_empty(self):
        """Should handle case where all windows return no data."""
        pipeline = _make_pipeline_for_date_splitting()
        pipeline.adapter.fetch.return_value = _make_fetch_result(0, success=True)

        events = pipeline._fetch_with_date_splitting(
            area_id=20,
            city_name="Barcelona",
            date_from="2025-06-01",
            date_to="2025-06-15",
        )

        assert len(events) == 0
        assert pipeline.adapter.fetch.call_count >= 1


# =============================================================================
# TESTS: Multi-city execute() integration
# =============================================================================


class TestMultiCityExecution:
    """Tests for multi-city execution via execute()."""

    @patch.object(BaseAPIPipeline, "_process_events_batch", return_value=[])
    @patch.object(BaseAPIPipeline, "_fetch_with_date_splitting")
    @patch.object(BaseAPIPipeline, "__init__", return_value=None)
    def test_execute_iterates_over_areas(self, mock_init, mock_fetch, mock_process):
        """Should call _fetch_with_date_splitting for each city in areas."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = APISourceConfig(
            source_name="test_api",
            defaults={
                "areas": {"Barcelona": 20, "Madrid": 28},
            },
        )
        pipeline.config = PipelineConfig(
            source_name="test_api",
            source_type=SourceType.API,
            deduplicate=False,
        )
        pipeline.logger = MagicMock()
        pipeline.adapter = MagicMock()
        pipeline.adapter.source_type = SourceType.API

        mock_fetch.return_value = [{"id": "1"}, {"id": "2"}]

        pipeline.execute()

        # Should have been called twice — once per city
        assert mock_fetch.call_count == 2
        city_names = [c.kwargs["city_name"] for c in mock_fetch.call_args_list]
        assert "Barcelona" in city_names
        assert "Madrid" in city_names

    @patch.object(BaseAPIPipeline, "_process_events_batch", return_value=[])
    @patch.object(BaseAPIPipeline, "_fetch_with_date_splitting")
    @patch.object(BaseAPIPipeline, "__init__", return_value=None)
    def test_execute_continues_on_city_failure(
        self, mock_init, mock_fetch, mock_process
    ):
        """Should continue with other cities if one fails."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = APISourceConfig(
            source_name="test_api",
            defaults={
                "areas": {"Barcelona": 20, "Madrid": 28},
            },
        )
        pipeline.config = PipelineConfig(
            source_name="test_api",
            source_type=SourceType.API,
            deduplicate=False,
        )
        pipeline.logger = MagicMock()
        pipeline.adapter = MagicMock()
        pipeline.adapter.source_type = SourceType.API

        # First city fails, second succeeds
        mock_fetch.side_effect = [
            Exception("Network error"),
            [{"id": "1"}],
        ]

        result = pipeline.execute()

        assert mock_fetch.call_count == 2
        # Should have recorded the error
        assert len(result.errors) == 1
        assert "Network error" in result.errors[0]["error"]

    @patch.object(BaseAPIPipeline, "__init__", return_value=None)
    def test_execute_falls_back_to_base_without_areas(self, mock_init):
        """Without areas config, should fall back to BasePipeline.execute."""
        pipeline = BaseAPIPipeline.__new__(BaseAPIPipeline)
        pipeline.source_config = APISourceConfig(
            source_name="test_api",
            defaults={},  # No areas
        )
        pipeline.config = PipelineConfig(
            source_name="test_api",
            source_type=SourceType.API,
        )
        pipeline.logger = MagicMock()
        pipeline.adapter = MagicMock()
        pipeline.adapter.source_type = SourceType.API

        # Mock the parent execute
        with patch.object(
            BasePipeline, "execute", return_value=MagicMock()
        ) as mock_base_exec:
            pipeline.execute()
            mock_base_exec.assert_called_once()
