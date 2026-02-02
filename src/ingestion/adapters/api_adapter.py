"""
API Source Adapter.

Adapter for fetching data from API-based sources (REST, GraphQL).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import logging
import time

import requests

from .base_adapter import BaseSourceAdapter, AdapterConfig, FetchResult, SourceType


logger = logging.getLogger(__name__)


@dataclass
class APIAdapterConfig(AdapterConfig):
    """
    Configuration for API-based adapters.
    """
    base_url: str = ""
    api_key: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)

    # GraphQL specific
    graphql_endpoint: Optional[str] = None
    graphql_query: Optional[str] = None

    def __post_init__(self):
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
        query_builder: Optional[Callable[..., Dict]] = None,
        response_parser: Optional[Callable[[Dict], List[Dict]]] = None,
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
        self._session: Optional[requests.Session] = None
        super().__init__(config)

    @property
    def api_config(self) -> APIAdapterConfig:
        """Get typed config."""
        return self.config

    def _validate_config(self) -> None:
        """Validate API configuration."""
        if not self.api_config.base_url and not self.api_config.graphql_endpoint:
            raise ValueError("API adapter requires base_url or graphql_endpoint")

    def _get_session(self) -> requests.Session:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
                **self.api_config.headers,
            })
            if self.api_config.api_key:
                self._session.headers["Authorization"] = f"Bearer {self.api_config.api_key}"
        return self._session

    def fetch(self, **kwargs) -> FetchResult:
        """
        Fetch data from the API.

        Args:
            **kwargs: Parameters passed to query_builder
                Common: city, country_code, page_size, date_from, date_to

        Returns:
            FetchResult with raw data
        """
        fetch_started = datetime.utcnow()
        all_data = []
        errors = []
        metadata = {"pages_fetched": 0, "api_calls": 0}

        try:
            session = self._get_session()

            # Build query using custom builder or default
            if self.query_builder:
                query_data = self.query_builder(**kwargs)
            else:
                query_data = self._default_query_builder(**kwargs)

            # Make request
            response = self._make_request(session, query_data)
            metadata["api_calls"] += 1

            if response:
                # Parse response using custom parser or default
                if self.response_parser:
                    data = self.response_parser(response)
                else:
                    data = self._default_response_parser(response)

                all_data.extend(data)
                metadata["pages_fetched"] = 1
                metadata["total_available"] = response.get("totalResults", len(data))

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
            fetch_ended_at=datetime.utcnow(),
        )

    def _make_request(
        self,
        session: requests.Session,
        query_data: Dict,
        retry_count: int = 0,
    ) -> Optional[Dict]:
        """
        Make HTTP request with retry logic.

        Args:
            session: HTTP session
            query_data: Request body/params
            retry_count: Current retry attempt

        Returns:
            Response JSON or None on failure
        """
        url = self.api_config.graphql_endpoint or self.api_config.base_url

        try:
            # Rate limiting
            time.sleep(1.0 / self.api_config.rate_limit_per_second)

            if self.api_config.graphql_endpoint:
                response = session.post(
                    url,
                    json=query_data,
                    timeout=self.api_config.request_timeout,
                )
            else:
                response = session.get(
                    url,
                    params=query_data,
                    timeout=self.api_config.request_timeout,
                )

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            if retry_count < self.api_config.max_retries:
                wait_time = 2 ** retry_count
                logger.warning(f"Request failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
                return self._make_request(session, query_data, retry_count + 1)

            logger.error(f"Request failed after {retry_count} retries: {e}")
            return None

    def _default_query_builder(self, **kwargs) -> Dict:
        """Default query builder - override or provide custom."""
        return kwargs

    def _default_response_parser(self, response: Dict) -> List[Dict]:
        """Default response parser - override or provide custom."""
        if "data" in response:
            return response["data"] if isinstance(response["data"], list) else [response["data"]]
        return [response]

    def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            self._session.close()
            self._session = None
