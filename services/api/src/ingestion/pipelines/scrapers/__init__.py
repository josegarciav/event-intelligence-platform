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
    BaseScraperPipeline as BaseScraperPipeline,
    EventScraper as EventScraper,
    PageFetchResult as PageFetchResult,
    ScraperConfig as ScraperConfig,
    load_scraper_config as load_scraper_config,
)
