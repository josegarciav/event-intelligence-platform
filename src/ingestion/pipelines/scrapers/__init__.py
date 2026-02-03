"""
Initialization module for ingestion pipeline scrapers.

This package provides:
- BaseScraperPipeline: Abstract base class for scraper-based pipelines
- EventScraper: Playwright-based browser automation for web scraping
- ScraperConfig: Configuration dataclass for scrapers
- PageFetchResult: Result dataclass for page fetching
- Config loading utilities for JSON scraper configs
"""

from .base_scraper import (
    PageFetchResult,
    ScraperConfig,
    EventScraper,
    BaseScraperPipeline,
    get_config_path,
    list_available_configs,
    load_config_raw,
    load_scraper_config,
)

__all__ = [
    "PageFetchResult",
    "ScraperConfig",
    "EventScraper",
    "BaseScraperPipeline",
    "get_config_path",
    "list_available_configs",
    "load_config_raw",
    "load_scraper_config",
]
