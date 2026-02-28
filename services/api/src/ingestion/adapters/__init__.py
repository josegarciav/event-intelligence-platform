"""
Source Adapters for Event Ingestion.

Adapters provide a unified interface for fetching data from different source types:
- API sources (GraphQL, REST)
- Scraper sources (HTML parsing with Playwright)

Usage:
    from src.ingestion.adapters import APIAdapter, ScraperAdapter, SourceType

    # For API sources
    adapter = APIAdapter(config)
    raw_data = adapter.fetch(city="barcelona")

    # For scraper sources
    adapter = ScraperAdapter(scraper_config)
    raw_data = adapter.fetch(max_pages=2)
"""

from .api_adapter import APIAdapter
from .base_adapter import BaseSourceAdapter, FetchResult, SourceType
from .scraper_adapter import ScraperAdapter

__all__ = [
    "BaseSourceAdapter",
    "SourceType",
    "FetchResult",
    "APIAdapter",
    "ScraperAdapter",
]
