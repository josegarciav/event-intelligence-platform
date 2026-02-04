"""
Unit tests for the api_adapter module.

Tests for APIAdapterConfig and APIAdapter classes.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests

from src.ingestion.adapters.api_adapter import (
    APIAdapter,
    APIAdapterConfig,
)
from src.ingestion.adapters.base_adapter import SourceType, FetchResult

# =============================================================================
# TEST DATA
# =============================================================================


MOCK_API_RESPONSE = {
    "data": [
        {"id": 1, "title": "Event 1"},
        {"id": 2, "title": "Event 2"},
    ],
    "totalResults": 2,
}


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def api_config():
    """Create a basic API adapter config."""
    return APIAdapterConfig(
        source_id="test_api",
        source_type=SourceType.API,
        base_url="https://api.example.com/events",
    )


@pytest.fixture
def graphql_config():
    """Create a GraphQL API adapter config."""
    return APIAdapterConfig(
        source_id="test_graphql",
        source_type=SourceType.API,
        graphql_endpoint="https://api.example.com/graphql",
    )


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    return session


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestAPIAdapterConfig:
    """Tests for APIAdapterConfig dataclass."""

    def test_create_config(self):
        """Should create config with required fields."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
        )
        assert config.source_id == "test"
        assert config.base_url == "https://api.example.com"

    def test_default_values(self):
        """Should have sensible defaults."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
        )
        assert config.api_key is None
        assert config.headers == {}
        assert config.graphql_endpoint is None
        assert config.graphql_query is None

    def test_source_type_set(self):
        """Should have source_type set to API."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
        )
        assert config.source_type == SourceType.API

    def test_custom_headers(self):
        """Should accept custom headers."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
            headers={"X-Custom-Header": "value"},
        )
        assert config.headers["X-Custom-Header"] == "value"

    def test_api_key(self):
        """Should store API key."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
            api_key="secret-key",
        )
        assert config.api_key == "secret-key"


class TestAPIAdapterInit:
    """Tests for APIAdapter initialization."""

    def test_init_with_base_url(self, api_config):
        """Should initialize with base_url config."""
        adapter = APIAdapter(api_config)
        assert adapter.api_config.base_url == "https://api.example.com/events"
        assert adapter._session is None

    def test_init_with_graphql_endpoint(self, graphql_config):
        """Should initialize with graphql_endpoint config."""
        adapter = APIAdapter(graphql_config)
        assert adapter.api_config.graphql_endpoint == "https://api.example.com/graphql"

    def test_init_with_query_builder(self, api_config):
        """Should accept custom query builder."""
        builder = MagicMock()
        adapter = APIAdapter(api_config, query_builder=builder)
        assert adapter.query_builder is builder

    def test_init_with_response_parser(self, api_config):
        """Should accept custom response parser."""
        parser = MagicMock()
        adapter = APIAdapter(api_config, response_parser=parser)
        assert adapter.response_parser is parser

    def test_validate_config_requires_url(self):
        """Should raise ValueError if no URL provided."""
        config = APIAdapterConfig(source_id="test", source_type=SourceType.API)
        with pytest.raises(ValueError, match="requires base_url or graphql_endpoint"):
            APIAdapter(config)


class TestAPIAdapterGetSession:
    """Tests for APIAdapter._get_session method."""

    def test_creates_session_on_first_call(self, api_config):
        """Should create session on first call."""
        adapter = APIAdapter(api_config)
        session = adapter._get_session()

        assert session is not None
        assert isinstance(session, requests.Session)

    def test_returns_same_session(self, api_config):
        """Should return the same session on subsequent calls."""
        adapter = APIAdapter(api_config)
        session1 = adapter._get_session()
        session2 = adapter._get_session()

        assert session1 is session2

    def test_sets_default_headers(self, api_config):
        """Should set default headers."""
        adapter = APIAdapter(api_config)
        session = adapter._get_session()

        assert "User-Agent" in session.headers
        assert "Accept" in session.headers
        assert session.headers["Accept"] == "application/json"

    def test_includes_custom_headers(self):
        """Should include custom headers from config."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
            headers={"X-Custom": "value"},
        )
        adapter = APIAdapter(config)
        session = adapter._get_session()

        assert session.headers.get("X-Custom") == "value"

    def test_sets_authorization_with_api_key(self):
        """Should set Authorization header when API key provided."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
            api_key="test-key",
        )
        adapter = APIAdapter(config)
        session = adapter._get_session()

        assert session.headers.get("Authorization") == "Bearer test-key"


class TestAPIAdapterFetch:
    """Tests for APIAdapter.fetch method."""

    @patch.object(APIAdapter, "_get_session")
    @patch.object(APIAdapter, "_make_request")
    def test_fetch_success(self, mock_request, mock_get_session, api_config):
        """Should return successful FetchResult."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_request.return_value = MOCK_API_RESPONSE

        adapter = APIAdapter(api_config)
        result = adapter.fetch()

        assert result.success is True
        assert result.source_type == SourceType.API
        assert len(result.raw_data) == 2
        assert result.total_fetched == 2

    @patch.object(APIAdapter, "_get_session")
    @patch.object(APIAdapter, "_make_request")
    def test_fetch_with_custom_query_builder(
        self, mock_request, mock_get_session, api_config
    ):
        """Should use custom query builder."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_request.return_value = MOCK_API_RESPONSE

        builder = MagicMock(return_value={"custom": "query"})
        adapter = APIAdapter(api_config, query_builder=builder)
        adapter.fetch(param1="value1")

        builder.assert_called_once_with(param1="value1")

    @patch.object(APIAdapter, "_get_session")
    @patch.object(APIAdapter, "_make_request")
    def test_fetch_with_custom_response_parser(
        self, mock_request, mock_get_session, api_config
    ):
        """Should use custom response parser."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_request.return_value = {"custom": "response"}

        parser = MagicMock(return_value=[{"parsed": "data"}])
        adapter = APIAdapter(api_config, response_parser=parser)
        result = adapter.fetch()

        parser.assert_called_once_with({"custom": "response"})
        assert result.raw_data == [{"parsed": "data"}]

    @patch.object(APIAdapter, "_get_session")
    @patch.object(APIAdapter, "_make_request")
    def test_fetch_handles_exception(self, mock_request, mock_get_session, api_config):
        """Should handle exceptions gracefully."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_request.side_effect = Exception("Connection failed")

        adapter = APIAdapter(api_config)
        result = adapter.fetch()

        assert result.success is False
        assert "Connection failed" in result.errors

    @patch.object(APIAdapter, "_get_session")
    @patch.object(APIAdapter, "_make_request")
    def test_fetch_empty_response(self, mock_request, mock_get_session, api_config):
        """Should handle empty response."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_request.return_value = None

        adapter = APIAdapter(api_config)
        result = adapter.fetch()

        assert result.success is False
        assert result.total_fetched == 0

    @patch.object(APIAdapter, "_get_session")
    @patch.object(APIAdapter, "_make_request")
    def test_fetch_tracks_timestamps(self, mock_request, mock_get_session, api_config):
        """Should track fetch timestamps."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_request.return_value = MOCK_API_RESPONSE

        adapter = APIAdapter(api_config)
        result = adapter.fetch()

        assert result.fetch_started_at is not None
        assert result.fetch_ended_at is not None
        assert result.fetch_started_at <= result.fetch_ended_at


class TestAPIAdapterMakeRequest:
    """Tests for APIAdapter._make_request method."""

    @patch("time.sleep")
    def test_make_get_request(self, mock_sleep, api_config):
        """Should make GET request for REST API."""
        adapter = APIAdapter(api_config)
        session = MagicMock()
        response = MagicMock()
        response.json.return_value = {"data": "test"}
        session.get.return_value = response

        result = adapter._make_request(session, {"param": "value"})

        session.get.assert_called_once()
        assert result == {"data": "test"}

    @patch("time.sleep")
    def test_make_post_request_for_graphql(self, mock_sleep, graphql_config):
        """Should make POST request for GraphQL API."""
        adapter = APIAdapter(graphql_config)
        session = MagicMock()
        response = MagicMock()
        response.json.return_value = {"data": "test"}
        session.post.return_value = response

        result = adapter._make_request(session, {"query": "..."})

        session.post.assert_called_once()
        assert result == {"data": "test"}

    @patch("time.sleep")
    def test_retry_on_failure(self, mock_sleep, api_config):
        """Should retry on request failure."""
        adapter = APIAdapter(api_config)
        session = MagicMock()
        session.get.side_effect = [
            requests.RequestException("Failed"),
            MagicMock(json=MagicMock(return_value={"data": "success"})),
        ]

        result = adapter._make_request(session, {})

        assert session.get.call_count == 2
        assert result == {"data": "success"}

    @patch("time.sleep")
    def test_max_retries_exceeded(self, mock_sleep, api_config):
        """Should return None after max retries."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
            max_retries=2,
        )
        adapter = APIAdapter(config)
        session = MagicMock()
        session.get.side_effect = requests.RequestException("Failed")

        result = adapter._make_request(session, {})

        assert result is None
        assert session.get.call_count == 3  # Initial + 2 retries

    @patch("time.sleep")
    def test_rate_limiting(self, mock_sleep, api_config):
        """Should respect rate limit."""
        adapter = APIAdapter(api_config)
        session = MagicMock()
        response = MagicMock()
        response.json.return_value = {"data": "test"}
        session.get.return_value = response

        adapter._make_request(session, {})

        mock_sleep.assert_called()


class TestAPIAdapterDefaultParsers:
    """Tests for APIAdapter default query builder and response parser."""

    def test_default_query_builder(self, api_config):
        """Should return kwargs as query."""
        adapter = APIAdapter(api_config)
        result = adapter._default_query_builder(key1="val1", key2="val2")

        assert result == {"key1": "val1", "key2": "val2"}

    def test_default_response_parser_with_data_list(self, api_config):
        """Should extract data list from response."""
        adapter = APIAdapter(api_config)
        result = adapter._default_response_parser({"data": [{"id": 1}, {"id": 2}]})

        assert result == [{"id": 1}, {"id": 2}]

    def test_default_response_parser_with_data_object(self, api_config):
        """Should wrap single data object in list."""
        adapter = APIAdapter(api_config)
        result = adapter._default_response_parser({"data": {"id": 1}})

        assert result == [{"id": 1}]

    def test_default_response_parser_no_data_key(self, api_config):
        """Should return response wrapped in list if no data key."""
        adapter = APIAdapter(api_config)
        result = adapter._default_response_parser({"id": 1, "title": "Test"})

        assert result == [{"id": 1, "title": "Test"}]


class TestAPIAdapterClose:
    """Tests for APIAdapter.close method."""

    def test_close_session(self, api_config):
        """Should close the HTTP session."""
        adapter = APIAdapter(api_config)
        mock_session = MagicMock()
        adapter._session = mock_session

        adapter.close()

        mock_session.close.assert_called_once()
        assert adapter._session is None

    def test_close_without_session(self, api_config):
        """Should handle close when no session exists."""
        adapter = APIAdapter(api_config)

        # Should not raise
        adapter.close()
        assert adapter._session is None


class TestAPIAdapterContextManager:
    """Tests for APIAdapter context manager usage."""

    def test_context_manager(self, api_config):
        """Should work as context manager."""
        adapter = APIAdapter(api_config)

        with patch.object(adapter, "close") as mock_close:
            with adapter as ctx:
                assert ctx is adapter
            mock_close.assert_called_once()
