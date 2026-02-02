"""
Scraper module for event ingestion.

Provides standalone scraping capabilities using Playwright.
"""

from .config_loader import load_event_scraper_config, get_config_path, list_available_configs
from .event_scraper import EventScraper, ScraperConfig, FetchResult

__all__ = [
    "load_event_scraper_config",
    "get_config_path",
    "list_available_configs",
    "EventScraper",
    "ScraperConfig",
    "FetchResult",
]
