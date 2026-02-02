"""
Scraper module for event ingestion.

Provides standalone scraping capabilities using Playwright.

Usage:
    from src.ingestion.scrapers import load_event_scraper_config, EventScraper

    config = load_event_scraper_config("ra_co", city="barcelona")
    scraper = EventScraper(config)
    results = scraper.fetch_listing_pages()
"""

from .config_loader import load_event_scraper_config, get_config_path, list_available_configs
from .event_scraper import EventScraper, ScraperConfig, FetchResult

__all__ = [
    # Config loading
    "load_event_scraper_config",
    "get_config_path",
    "list_available_configs",
    # Scraper classes
    "EventScraper",
    "ScraperConfig",
    "FetchResult",
]
