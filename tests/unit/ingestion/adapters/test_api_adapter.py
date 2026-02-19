"""
Unit tests for the api_adapter module.

Tests for APIAdapterConfig and APIAdapter classes.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from src.ingestion.adapters.api_adapter import (
    APIAdapter,
    APIAdapterConfig,
)
from src.ingestion.adapters.base_adapter import SourceType

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
        assert adapter._client is None

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


class TestAPIAdapterGetClient:
    """Tests for APIAdapter._get_client method."""

    def test_creates_client_on_first_call(self, api_config):
        """Should create async HTTP client on first call."""
        adapter = APIAdapter(api_config)
        client = adapter._get_client()

        assert client is not None
        assert isinstance(client, httpx.AsyncClient)

    def test_returns_same_client(self, api_config):
        """Should return the same client on subsequent calls."""
        adapter = APIAdapter(api_config)
        client1 = adapter._get_client()
        client2 = adapter._get_client()

        assert client1 is client2

    def test_sets_default_headers(self, api_config):
        """Should set default headers on the client."""
        adapter = APIAdapter(api_config)
        client = adapter._get_client()

        # httpx Headers is case-insensitive
        assert "user-agent" in client.headers
        assert client.headers["accept"] == "application/json"

    def test_includes_custom_headers(self):
        """Should include custom headers from config."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
            headers={"X-Custom": "value"},
        )
        adapter = APIAdapter(config)
        client = adapter._get_client()

        assert client.headers["x-custom"] == "value"

    def test_sets_authorization_with_api_key(self):
        """Should set Authorization header when API key provided."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
            api_key="test-key",
        )
        adapter = APIAdapter(config)
        client = adapter._get_client()

        assert client.headers["authorization"] == "Bearer test-key"


class TestAPIAdapterFetch:
    """Tests for APIAdapter.fetch method."""

    def test_fetch_success(self, api_config):
        """Should return successful FetchResult."""
        adapter = APIAdapter(api_config)
        with patch.object(
            adapter, "_make_request", new=AsyncMock(return_value=MOCK_API_RESPONSE)
        ):
            result = asyncio.run(adapter.fetch())

        assert result.success is True
        assert result.source_type == SourceType.API
        assert len(result.raw_data) == 2
        assert result.total_fetched == 2

    def test_fetch_with_custom_query_builder(self, api_config):
        """Should use custom query builder."""
        builder = MagicMock(return_value={"custom": "query"})
        adapter = APIAdapter(api_config, query_builder=builder)

        with patch.object(
            adapter, "_make_request", new=AsyncMock(return_value=MOCK_API_RESPONSE)
        ):
            asyncio.run(adapter.fetch(param1="value1"))

        builder.assert_called_once_with(param1="value1")

    def test_fetch_with_custom_response_parser(self, api_config):
        """Should use custom response parser."""
        parser = MagicMock(return_value=[{"parsed": "data"}])
        adapter = APIAdapter(api_config, response_parser=parser)

        with patch.object(
            adapter, "_make_request", new=AsyncMock(return_value={"custom": "response"})
        ):
            result = asyncio.run(adapter.fetch())

        parser.assert_called_once_with({"custom": "response"})
        assert result.raw_data == [{"parsed": "data"}]

    def test_fetch_handles_exception(self, api_config):
        """Should handle exceptions gracefully."""
        adapter = APIAdapter(api_config)

        with patch.object(
            adapter,
            "_make_request",
            new=AsyncMock(side_effect=Exception("Connection failed")),
        ):
            result = asyncio.run(adapter.fetch())

        assert result.success is False
        assert "Connection failed" in result.errors

    def test_fetch_empty_response(self, api_config):
        """Should handle empty response."""
        adapter = APIAdapter(api_config)

        with patch.object(adapter, "_make_request", new=AsyncMock(return_value=None)):
            result = asyncio.run(adapter.fetch())

        assert result.success is False
        assert result.total_fetched == 0

    def test_fetch_tracks_timestamps(self, api_config):
        """Should track fetch timestamps."""
        adapter = APIAdapter(api_config)

        with patch.object(
            adapter, "_make_request", new=AsyncMock(return_value=MOCK_API_RESPONSE)
        ):
            result = asyncio.run(adapter.fetch())

        assert result.fetch_started_at is not None
        assert result.fetch_ended_at is not None
        assert result.fetch_started_at <= result.fetch_ended_at


class TestAPIAdapterMakeRequest:
    """Tests for APIAdapter._make_request method."""

    def test_make_get_request(self, api_config):
        """Should make GET request for REST API."""
        adapter = APIAdapter(api_config)
        response = MagicMock()
        response.json.return_value = {"data": "test"}
        response.raise_for_status = MagicMock()
        client = AsyncMock()
        client.get = AsyncMock(return_value=response)

        with patch("asyncio.sleep", new=AsyncMock()):
            result = asyncio.run(adapter._make_request(client, {"param": "value"}))

        client.get.assert_called_once()
        assert result == {"data": "test"}

    def test_make_post_request_for_graphql(self, graphql_config):
        """Should make POST request for GraphQL API."""
        adapter = APIAdapter(graphql_config)
        response = MagicMock()
        response.json.return_value = {"data": "test"}
        response.raise_for_status = MagicMock()
        client = AsyncMock()
        client.post = AsyncMock(return_value=response)

        with patch("asyncio.sleep", new=AsyncMock()):
            result = asyncio.run(adapter._make_request(client, {"query": "..."}))

        client.post.assert_called_once()
        assert result == {"data": "test"}

    def test_retry_on_failure(self, api_config):
        """Should retry on request failure."""
        adapter = APIAdapter(api_config)
        success_response = MagicMock()
        success_response.json.return_value = {"data": "success"}
        success_response.raise_for_status = MagicMock()
        client = AsyncMock()
        client.get = AsyncMock(
            side_effect=[
                httpx.HTTPError("Failed"),
                success_response,
            ]
        )

        with patch("asyncio.sleep", new=AsyncMock()):
            result = asyncio.run(adapter._make_request(client, {}))

        assert client.get.call_count == 2
        assert result == {"data": "success"}

    def test_max_retries_exceeded(self, api_config):
        """Should return None after max retries."""
        config = APIAdapterConfig(
            source_id="test",
            source_type=SourceType.API,
            base_url="https://api.example.com",
            max_retries=2,
        )
        adapter = APIAdapter(config)
        client = AsyncMock()
        client.get = AsyncMock(side_effect=httpx.HTTPError("Failed"))

        with patch("asyncio.sleep", new=AsyncMock()):
            result = asyncio.run(adapter._make_request(client, {}))

        assert result is None
        assert client.get.call_count == 3  # Initial + 2 retries

    def test_rate_limiting(self, api_config):
        """Should respect rate limit via asyncio.sleep."""
        adapter = APIAdapter(api_config)
        response = MagicMock()
        response.json.return_value = {"data": "test"}
        response.raise_for_status = MagicMock()
        client = AsyncMock()
        client.get = AsyncMock(return_value=response)

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            asyncio.run(adapter._make_request(client, {}))

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

    def test_close_client(self, api_config):
        """Should close the async HTTP client."""
        adapter = APIAdapter(api_config)
        mock_client = AsyncMock()
        adapter._client = mock_client

        asyncio.run(adapter.close())

        mock_client.aclose.assert_called_once()
        assert adapter._client is None

    def test_close_without_client(self, api_config):
        """Should handle close when no client exists."""
        adapter = APIAdapter(api_config)

        # Should not raise
        asyncio.run(adapter.close())
        assert adapter._client is None


class TestAPIAdapterContextManager:
    """Tests for APIAdapter async context manager usage."""

    def test_context_manager(self, api_config):
        """Should work as async context manager."""
        adapter = APIAdapter(api_config)

        async def run():
            with patch.object(adapter, "close", new=AsyncMock()) as mock_close:
                async with adapter as ctx:
                    assert ctx is adapter
            mock_close.assert_called_once()

        asyncio.run(run())
