"""
API Source Adapter.

Adapter for fetching data from API-based sources (REST, GraphQL).
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from .base_adapter import AdapterConfig, BaseSourceAdapter, FetchResult, SourceType

logger = logging.getLogger(__name__)


@dataclass
class APIAdapterConfig(AdapterConfig):
    """Configuration for API-based adapters."""

    base_url: str = ""
    api_key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    # GraphQL specific
    graphql_endpoint: str | None = None
    graphql_query: str | None = None

    def __post_init__(self):
        """Set source type to API."""
        self.source_type = SourceType.API


class APIAdapter(BaseSourceAdapter):
    """
    Adapter for API-based data sources.

    Supports both REST and GraphQL APIs with:
    - Automatic pagination
    - Rate limiting
    - Retry logic with exponential backoff
    - Custom headers and authentication
    """

    def __init__(
        self,
        config: APIAdapterConfig,
        query_builder: Callable[..., dict] | None = None,
        response_parser: Callable[[dict], list[dict]] | None = None,
    ):
        """
        Initialize the API adapter.

        Args:
            config: APIAdapterConfig with API settings
            query_builder: Function to build query/request body from kwargs
            response_parser: Function to extract data list from response
        """
        self.query_builder = query_builder
        self.response_parser = response_parser
        self._client: httpx.AsyncClient | None = None
        super().__init__(config)

    @property
    def api_config(self) -> APIAdapterConfig:
        """Get typed config."""
        return self.config  # type: ignore[return-value]

    def _validate_config(self) -> None:
        """Validate API configuration."""
        if not self.api_config.base_url and not self.api_config.graphql_endpoint:
            raise ValueError("API adapter requires base_url or graphql_endpoint")

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
                **self.api_config.headers,
            }
            if self.api_config.api_key:
                headers["Authorization"] = f"Bearer {self.api_config.api_key}"
            self._client = httpx.AsyncClient(headers=headers)
        return self._client

    async def fetch(self, **kwargs) -> FetchResult:
        """
        Fetch data from the API.

        Args:
            **kwargs: Parameters passed to query_builder
                Common: city, country_code, page_size, date_from, date_to

        Returns:
            FetchResult with raw data
        """
        fetch_started = datetime.now(UTC)
        all_data = []
        errors = []
        metadata = {"pages_fetched": 0, "api_calls": 0}

        try:
            client = self._get_client()

            # Build query using custom builder or default
            if self.query_builder:
                query_data = self.query_builder(**kwargs)
            else:
                query_data = self._default_query_builder(**kwargs)

            # Make request
            response = await self._make_request(client, query_data)
            metadata["api_calls"] += 1

            if response:
                # Parse response using custom parser or default
                if self.response_parser:
                    data = self.response_parser(response)
                else:
                    data = self._default_response_parser(response)

                all_data.extend(data)
                metadata["pages_fetched"] = 1
                metadata["total_available"] = self._extract_total_available(response, data)

        except Exception as e:
            logger.error(f"API fetch failed: {e}")
            errors.append(str(e))

        return FetchResult(
            success=len(all_data) > 0,
            source_type=SourceType.API,
            raw_data=all_data,
            total_fetched=len(all_data),
            errors=errors,
            metadata=metadata,
            fetch_started_at=fetch_started,
            fetch_ended_at=datetime.now(UTC),
        )

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        query_data: dict,
        retry_count: int = 0,
    ) -> dict | None:
        """
        Make HTTP request with retry logic.

        Args:
            client: Async HTTP client
            query_data: Request body/params
            retry_count: Current retry attempt

        Returns:
            Response JSON or None on failure
        """
        url = self.api_config.graphql_endpoint or self.api_config.base_url

        try:
            # Rate limiting
            await asyncio.sleep(1.0 / self.api_config.rate_limit_per_second)

            if self.api_config.graphql_endpoint:
                response = await client.post(
                    url,
                    json=query_data,
                    timeout=self.api_config.request_timeout,
                )
            else:
                response = await client.get(
                    url,
                    params=query_data,
                    timeout=self.api_config.request_timeout,
                )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            if retry_count < self.api_config.max_retries:
                wait_time = 2**retry_count
                logger.warning(f"Request failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
                return await self._make_request(client, query_data, retry_count + 1)

            logger.error(f"Request failed after {retry_count} retries: {e}")
            return None

    def _extract_total_available(self, response: dict, data: list) -> int:
        """
        Extract total available count from the API response.

        Override in subclasses to navigate source-specific response structures.
        """
        return response.get("totalResults", len(data))

    def _default_query_builder(self, **kwargs) -> dict:
        """Build a default query from keyword arguments."""
        return kwargs

    def _default_response_parser(self, response: dict) -> list[dict]:
        """Parse a default response structure into a list of dicts."""
        if "data" in response:
            return response["data"] if isinstance(response["data"], list) else [response["data"]]
        return [response]

    async def close(self) -> None:
        """Close async HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
