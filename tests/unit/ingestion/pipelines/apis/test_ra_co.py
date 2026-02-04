"""
Unit tests for the ra_co module.

Tests for RaCoAdapter and RaCoPipeline classes.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import uuid

import pytest

from src.ingestion.pipelines.apis.ra_co import (
    RaCoAdapter,
    RaCoPipeline,
    create_ra_co_pipeline,
    EVENTS_QUERY,
)
from src.ingestion.adapters.api_adapter import APIAdapterConfig
from src.ingestion.adapters.base_adapter import SourceType, FetchResult
from src.ingestion.base_pipeline import PipelineConfig
from src.schemas.event import (
    EventSchema,
    EventType,
    EventFormat,
    PrimaryCategory,
)


# =============================================================================
# TEST DATA
# =============================================================================


MOCK_GRAPHQL_RESPONSE = {
    "data": {
        "eventListings": {
            "data": [
                {
                    "id": "listing-1",
                    "event": {
                        "id": "event-1",
                        "title": "Techno Night",
                        "content": "<p>Amazing techno event</p>",
                        "date": "2024-06-15",
                        "startTime": "2024-06-15T22:00:00",
                        "endTime": "2024-06-16T06:00:00",
                        "venue": {
                            "name": "Club XYZ",
                            "address": "123 Main St",
                            "area": {
                                "name": "Barcelona",
                                "country": {
                                    "name": "Spain",
                                    "urlCode": "ES",
                                },
                            },
                        },
                        "artists": [
                            {"name": "Artist A"},
                            {"name": "Artist B"},
                        ],
                        "images": [
                            {"filename": "event1.jpg"},
                        ],
                        "cost": "€15",
                        "contentUrl": "/events/1234",
                    },
                },
                {
                    "id": "listing-2",
                    "event": {
                        "id": "event-2",
                        "title": "House Party",
                        "content": "House music all night",
                        "date": "2024-06-16",
                        "startTime": "2024-06-16T23:00:00",
                        "endTime": "2024-06-17T05:00:00",
                        "venue": {
                            "name": "Club ABC",
                            "address": "456 Other St",
                            "area": {
                                "name": "Barcelona",
                                "country": {
                                    "name": "Spain",
                                    "urlCode": "ES",
                                },
                            },
                        },
                        "artists": [],
                        "images": [],
                        "cost": "Free",
                        "contentUrl": "/events/5678",
                    },
                },
            ],
            "totalResults": 2,
        }
    }
}


MOCK_RAW_EVENT = {
    "id": "event-1",
    "title": "Techno Night",
    "content": "<p>Amazing techno event</p>",
    "date": "2024-06-15",
    "startTime": "2024-06-15T22:00:00",
    "endTime": "2024-06-16T06:00:00",
    "venue": {
        "name": "Club XYZ",
        "address": "123 Main St",
        "area": {
            "name": "Barcelona",
            "country": {
                "name": "Spain",
                "urlCode": "ES",
            },
        },
    },
    "artists": [{"name": "Artist A"}, {"name": "Artist B"}],
    "images": [{"filename": "event1.jpg"}],
    "cost": "€15",
    "contentUrl": "/events/1234",
    "_listing_id": "listing-1",
}


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def api_config():
    """Create API adapter config for ra.co."""
    return APIAdapterConfig(
        source_id="ra_co",
        source_type=SourceType.API,
        graphql_endpoint="https://ra.co/graphql",
    )


@pytest.fixture
def pipeline_config():
    """Create pipeline config."""
    return PipelineConfig(
        source_name="ra_co",
        batch_size=50,
    )


@pytest.fixture
def adapter(api_config):
    """Create RaCoAdapter."""
    return RaCoAdapter(api_config)


@pytest.fixture
def pipeline(pipeline_config, adapter):
    """Create RaCoPipeline."""
    return RaCoPipeline(pipeline_config, adapter)


# =============================================================================
# TEST CLASSES - RaCoAdapter
# =============================================================================


class TestRaCoAdapterInit:
    """Tests for RaCoAdapter initialization."""

    def test_init_sets_query_builder(self, api_config):
        """Should set query builder."""
        adapter = RaCoAdapter(api_config)
        assert adapter.query_builder is not None

    def test_init_sets_response_parser(self, api_config):
        """Should set response parser."""
        adapter = RaCoAdapter(api_config)
        assert adapter.response_parser is not None


class TestRaCoAdapterBuildQuery:
    """Tests for RaCoAdapter._build_query method."""

    def test_build_query_default_params(self, adapter):
        """Should build query with default parameters."""
        result = adapter._build_query()

        assert "query" in result
        assert "variables" in result
        assert result["query"] == EVENTS_QUERY

    def test_build_query_custom_area(self, adapter):
        """Should use custom area_id."""
        result = adapter._build_query(area_id=30)

        assert result["variables"]["filters"]["areas"]["eq"] == 30

    def test_build_query_custom_page_size(self, adapter):
        """Should use custom page_size."""
        result = adapter._build_query(page_size=100)

        assert result["variables"]["pageSize"] == 100

    def test_build_query_custom_dates(self, adapter):
        """Should use custom date range."""
        result = adapter._build_query(
            date_from="2024-07-01",
            date_to="2024-07-31",
        )

        assert result["variables"]["filters"]["listingDate"]["gte"] == "2024-07-01"
        assert result["variables"]["filters"]["listingDate"]["lte"] == "2024-07-31"

    def test_build_query_default_dates(self, adapter):
        """Should use default dates when not provided."""
        result = adapter._build_query()

        # Should have date filter with today's date
        assert "listingDate" in result["variables"]["filters"]


class TestRaCoAdapterParseResponse:
    """Tests for RaCoAdapter._parse_response method."""

    def test_parse_response_extracts_events(self, adapter):
        """Should extract events from GraphQL response."""
        result = adapter._parse_response(MOCK_GRAPHQL_RESPONSE)

        assert len(result) == 2
        assert result[0]["title"] == "Techno Night"
        assert result[1]["title"] == "House Party"

    def test_parse_response_adds_listing_id(self, adapter):
        """Should add listing_id to events."""
        result = adapter._parse_response(MOCK_GRAPHQL_RESPONSE)

        assert result[0]["_listing_id"] == "listing-1"
        assert result[1]["_listing_id"] == "listing-2"

    def test_parse_response_handles_errors(self, adapter):
        """Should return empty list on GraphQL errors."""
        response = {"errors": [{"message": "Query failed"}]}
        result = adapter._parse_response(response)

        assert result == []

    def test_parse_response_handles_empty_data(self, adapter):
        """Should handle empty data gracefully."""
        response = {"data": {"eventListings": {"data": []}}}
        result = adapter._parse_response(response)

        assert result == []

    def test_parse_response_handles_missing_event(self, adapter):
        """Should skip listings without event data."""
        response = {
            "data": {
                "eventListings": {
                    "data": [
                        {"id": "listing-1", "event": None},
                        {"id": "listing-2", "event": {"id": "e1", "title": "Test"}},
                    ]
                }
            }
        }
        result = adapter._parse_response(response)

        assert len(result) == 1
        assert result[0]["title"] == "Test"


class TestRaCoAdapterFetch:
    """Tests for RaCoAdapter.fetch method with pagination."""

    @patch("src.ingestion.adapters.api_adapter.APIAdapter.fetch")
    def test_fetch_single_page(self, mock_parent_fetch, adapter):
        """Should fetch single page when less than page_size."""
        mock_parent_fetch.return_value = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"id": 1}],
            total_fetched=1,
            metadata={"total_available": 1},
        )

        result = adapter.fetch(page_size=50)

        assert result.success is True
        assert mock_parent_fetch.call_count == 1

    @patch("src.ingestion.adapters.api_adapter.APIAdapter.fetch")
    def test_fetch_multiple_pages(self, mock_parent_fetch, adapter):
        """Should paginate through multiple pages."""
        # First page returns full page_size
        page1 = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"id": i} for i in range(50)],
            total_fetched=50,
            metadata={"total_available": 75},
        )
        # Second page returns less than page_size
        page2 = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"id": i} for i in range(25)],
            total_fetched=25,
            metadata={"total_available": 75},
        )
        mock_parent_fetch.side_effect = [page1, page2]

        result = adapter.fetch(page_size=50, max_pages=10)

        assert result.success is True
        assert len(result.raw_data) == 75
        assert result.metadata["pages_fetched"] == 2

    @patch("src.ingestion.adapters.api_adapter.APIAdapter.fetch")
    def test_fetch_stops_on_empty_page(self, mock_parent_fetch, adapter):
        """Should stop when page returns empty or less than page_size."""
        # First page returns less than page_size (which triggers stop)
        page1 = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"id": 1}],
            total_fetched=1,
            metadata={"total_available": 10},
        )
        mock_parent_fetch.return_value = page1

        result = adapter.fetch(page_size=50)

        # Stops after first page because it returned less than page_size
        assert len(result.raw_data) == 1
        assert mock_parent_fetch.call_count == 1

    @patch("src.ingestion.adapters.api_adapter.APIAdapter.fetch")
    def test_fetch_respects_max_pages(self, mock_parent_fetch, adapter):
        """Should respect max_pages limit."""
        page = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"id": i} for i in range(50)],
            total_fetched=50,
            metadata={"total_available": 1000},
        )
        mock_parent_fetch.return_value = page

        result = adapter.fetch(max_pages=3, page_size=50)

        assert mock_parent_fetch.call_count == 3
        assert len(result.raw_data) == 150


# =============================================================================
# TEST CLASSES - RaCoPipeline
# =============================================================================


class TestRaCoPipelineParseRawEvent:
    """Tests for RaCoPipeline.parse_raw_event method."""

    def test_parse_extracts_basic_fields(self, pipeline):
        """Should extract basic event fields."""
        result = pipeline.parse_raw_event(MOCK_RAW_EVENT)

        assert result["source_event_id"] == "event-1"
        assert result["title"] == "Techno Night"
        assert result["venue_name"] == "Club XYZ"

    def test_parse_extracts_location(self, pipeline):
        """Should extract location info."""
        result = pipeline.parse_raw_event(MOCK_RAW_EVENT)

        assert result["city"] == "Barcelona"
        assert result["country_name"] == "Spain"
        assert result["country_code"] == "ES"
        assert result["venue_address"] == "123 Main St"

    def test_parse_extracts_artists(self, pipeline):
        """Should extract artist names."""
        result = pipeline.parse_raw_event(MOCK_RAW_EVENT)

        assert result["artists"] == ["Artist A", "Artist B"]

    def test_parse_cleans_html_description(self, pipeline):
        """Should clean HTML from description."""
        result = pipeline.parse_raw_event(MOCK_RAW_EVENT)

        assert "<p>" not in result["description"]
        assert "Amazing techno event" in result["description"]

    def test_parse_extracts_image_url(self, pipeline):
        """Should construct image URL."""
        result = pipeline.parse_raw_event(MOCK_RAW_EVENT)

        assert result["image_url"] == "https://ra.co/images/events/flyer/event1.jpg"

    def test_parse_handles_missing_venue(self, pipeline):
        """Should handle missing venue gracefully."""
        event = {**MOCK_RAW_EVENT, "venue": None}
        result = pipeline.parse_raw_event(event)

        assert result["venue_name"] is None
        assert result["city"] is None

    def test_parse_handles_empty_artists(self, pipeline):
        """Should handle empty artists list."""
        event = {**MOCK_RAW_EVENT, "artists": []}
        result = pipeline.parse_raw_event(event)

        assert result["artists"] == []


class TestRaCoPipelineMapToTaxonomy:
    """Tests for RaCoPipeline.map_to_taxonomy method."""

    def test_maps_to_play_and_fun(self, pipeline):
        """Should map to PLAY_AND_FUN category."""
        event = {"title": "Techno Night", "description": "Electronic music"}
        primary_cat, dimensions = pipeline.map_to_taxonomy(event)

        assert primary_cat == PrimaryCategory.PLAY_AND_PURE_FUN.value

    def test_includes_music_subcategory(self, pipeline):
        """Should include Music & Rhythm Play subcategory."""
        event = {"title": "Techno Night"}
        _, dimensions = pipeline.map_to_taxonomy(event)

        music_dim = next((d for d in dimensions if d["subcategory"] == "1.4"), None)
        assert music_dim is not None
        assert music_dim["confidence"] == 0.95

    def test_includes_social_dimension(self, pipeline):
        """Should include social connection dimension."""
        event = {"title": "Techno Night"}
        _, dimensions = pipeline.map_to_taxonomy(event)

        social_dim = next((d for d in dimensions if d["subcategory"] == "5.7"), None)
        assert social_dim is not None

    def test_adds_exploration_for_festival(self, pipeline):
        """Should add exploration dimension for festivals."""
        event = {"title": "Summer Festival Outdoor"}
        _, dimensions = pipeline.map_to_taxonomy(event)

        explore_dim = next((d for d in dimensions if d["subcategory"] == "2.4"), None)
        assert explore_dim is not None

    def test_adds_learning_for_workshop(self, pipeline):
        """Should add learning dimension for workshops."""
        event = {"title": "DJ Workshop"}
        _, dimensions = pipeline.map_to_taxonomy(event)

        learn_dim = next((d for d in dimensions if d["subcategory"] == "4.2"), None)
        assert learn_dim is not None


class TestRaCoPipelineNormalizeToSchema:
    """Tests for RaCoPipeline.normalize_to_schema method."""

    def test_creates_event_schema(self, pipeline):
        """Should create EventSchema instance."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)

        result = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        assert isinstance(result, EventSchema)
        assert result.title == "Techno Night"

    def test_sets_location(self, pipeline):
        """Should set location info."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)

        result = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        assert result.location.venue_name == "Club XYZ"
        assert result.location.city == "Barcelona"
        assert result.location.country_code == "ES"

    def test_sets_price_info(self, pipeline):
        """Should parse and set price info."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)

        result = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        assert result.price.currency == "EUR"
        assert result.price.minimum_price == 15.0

    def test_sets_free_for_free_events(self, pipeline):
        """Should set is_free for free events."""
        event = {**MOCK_RAW_EVENT, "cost": "Free"}
        parsed = pipeline.parse_raw_event(event)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)

        result = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        assert result.price.is_free is True

    def test_sets_source_info(self, pipeline):
        """Should set source info."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)

        result = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        assert result.source.source_name == "ra_co"
        assert result.source.source_event_id == "event-1"
        assert "ra.co" in result.source.source_url

    def test_sets_event_type_festival(self, pipeline):
        """Should detect festival event type."""
        event = {**MOCK_RAW_EVENT, "title": "Summer Festival"}
        parsed = pipeline.parse_raw_event(event)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)

        result = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        assert result.event_type == EventType.FESTIVAL

    def test_sets_event_type_party(self, pipeline):
        """Should detect party event type."""
        event = {**MOCK_RAW_EVENT, "title": "House Party"}
        parsed = pipeline.parse_raw_event(event)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)

        result = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        assert result.event_type == EventType.PARTY

    def test_stores_artists_in_custom_fields(self, pipeline):
        """Should store artists in custom_fields."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)

        result = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        assert result.custom_fields["artists"] == ["Artist A", "Artist B"]


class TestRaCoPipelineValidateEvent:
    """Tests for RaCoPipeline.validate_event method."""

    def test_valid_event(self, pipeline):
        """Should validate complete event."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)
        event = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        is_valid, errors = pipeline.validate_event(event)

        assert is_valid is True

    def test_invalid_without_title(self, pipeline):
        """Should reject event without title."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)
        event = pipeline.normalize_to_schema(parsed, primary_cat, dims)
        event.title = "Untitled Event"

        is_valid, errors = pipeline.validate_event(event)

        assert "Title is required" in errors

    def test_invalid_without_city(self, pipeline):
        """Should reject event without proper city."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)
        event = pipeline.normalize_to_schema(parsed, primary_cat, dims)
        # Set city to empty string (schema requires string, can't be None)
        event.location.city = ""

        is_valid, errors = pipeline.validate_event(event)

        assert "City is required" in errors


class TestRaCoPipelineEnrichEvent:
    """Tests for RaCoPipeline.enrich_event method."""

    def test_calculates_duration(self, pipeline):
        """Should calculate duration in minutes."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)
        event = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        enriched = pipeline.enrich_event(event)

        assert enriched.duration_minutes is not None
        assert enriched.duration_minutes > 0

    def test_sets_timezone(self, pipeline):
        """Should set timezone based on city."""
        parsed = pipeline.parse_raw_event(MOCK_RAW_EVENT)
        primary_cat, dims = pipeline.map_to_taxonomy(parsed)
        event = pipeline.normalize_to_schema(parsed, primary_cat, dims)

        enriched = pipeline.enrich_event(event)

        assert enriched.location.timezone == "Europe/Madrid"


class TestRaCoPipelineParseDatetime:
    """Tests for RaCoPipeline._parse_datetime method."""

    def test_parse_iso_format(self, pipeline):
        """Should parse ISO format datetime."""
        result = pipeline._parse_datetime("2024-06-15T22:00:00")

        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 22

    def test_parse_date_only(self, pipeline):
        """Should parse date-only format."""
        result = pipeline._parse_datetime("2024-06-15")

        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_parse_datetime_object(self, pipeline):
        """Should return datetime object as-is."""
        dt = datetime(2024, 6, 15, 22, 0)
        result = pipeline._parse_datetime(dt)

        assert result == dt

    def test_parse_none_returns_now(self, pipeline):
        """Should return current time for None."""
        result = pipeline._parse_datetime(None)

        assert result is not None
        assert isinstance(result, datetime)


# =============================================================================
# TEST CLASSES - Factory Function
# =============================================================================


class TestCreateRaCoPipeline:
    """Tests for create_ra_co_pipeline factory function."""

    def test_creates_pipeline(self, pipeline_config):
        """Should create configured pipeline."""
        source_config = {
            "graphql_endpoint": "https://ra.co/graphql",
        }

        result = create_ra_co_pipeline(pipeline_config, source_config)

        assert isinstance(result, RaCoPipeline)

    def test_configures_adapter(self, pipeline_config):
        """Should configure adapter from source_config."""
        source_config = {
            "graphql_endpoint": "https://ra.co/graphql",
            "request_timeout": 60,
            "max_retries": 5,
        }

        result = create_ra_co_pipeline(pipeline_config, source_config)

        assert result.adapter.config.request_timeout == 60
        assert result.adapter.config.max_retries == 5

    def test_creates_feature_extractor_when_enabled(self, pipeline_config):
        """Should create feature extractor when enabled."""
        source_config = {
            "graphql_endpoint": "https://ra.co/graphql",
            "feature_extraction": {
                "enabled": True,
                "provider": "openai",
            },
        }

        result = create_ra_co_pipeline(pipeline_config, source_config)

        assert result.feature_extractor is not None

    def test_no_feature_extractor_when_disabled(self, pipeline_config):
        """Should not create feature extractor when disabled."""
        source_config = {
            "graphql_endpoint": "https://ra.co/graphql",
            "feature_extraction": {
                "enabled": False,
            },
        }

        result = create_ra_co_pipeline(pipeline_config, source_config)

        assert result.feature_extractor is None
