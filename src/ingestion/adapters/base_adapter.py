"""
Base Source Adapter.

Abstract base class defining the interface for all source adapters.
Implements the Strategy pattern for different data fetching strategies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging


class SourceType(str, Enum):
    """Type of data source."""
    API = "api"
    SCRAPER = "scraper"


@dataclass
class FetchResult:
    """
    Result of a data fetch operation.

    Provides a unified result format for both API and scraper sources.
    """
    success: bool
    source_type: SourceType
    raw_data: List[Dict[str, Any]] = field(default_factory=list)
    total_fetched: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    fetch_started_at: Optional[datetime] = None
    fetch_ended_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate fetch duration."""
        if self.fetch_started_at and self.fetch_ended_at:
            return (self.fetch_ended_at - self.fetch_started_at).total_seconds()
        return 0.0


@dataclass
class AdapterConfig:
    """
    Base configuration for source adapters.

    Extended by specific adapter types (API, Scraper).
    """
    source_id: str
    source_type: SourceType
    request_timeout: int = 30
    max_retries: int = 3
    rate_limit_per_second: float = 1.0
    custom_config: Dict[str, Any] = field(default_factory=dict)


class BaseSourceAdapter(ABC):
    """
    Abstract base class for source adapters.

    Adapters encapsulate the logic for fetching raw data from different
    source types (APIs, web scraping). They provide a unified interface
    that pipelines use regardless of the underlying data source.

    Subclasses must implement:
        - fetch(): Fetch raw data from the source
        - validate_config(): Validate adapter-specific configuration
    """

    def __init__(self, config: AdapterConfig):
        """
        Initialize the adapter.

        Args:
            config: AdapterConfig with source-specific settings
        """
        self.config = config
        self.logger = logging.getLogger(f"adapter.{config.source_id}")
        self._validate_config()

    @property
    def source_type(self) -> SourceType:
        """Get the source type."""
        return self.config.source_type

    @property
    def source_id(self) -> str:
        """Get the source identifier."""
        return self.config.source_id

    @abstractmethod
    def fetch(self, **kwargs) -> FetchResult:
        """
        Fetch raw data from the source.

        Args:
            **kwargs: Source-specific fetch parameters
                - For APIs: city, country_code, date_range, page_size, etc.
                - For scrapers: max_pages, max_events, etc.

        Returns:
            FetchResult with raw data and metadata
        """
        pass

    @abstractmethod
    def _validate_config(self) -> None:
        """
        Validate adapter-specific configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    def close(self) -> None:
        """
        Release any resources held by the adapter.

        Override in subclasses that hold resources (e.g., browser instances).
        """
        pass

    def __enter__(self) -> "BaseSourceAdapter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
