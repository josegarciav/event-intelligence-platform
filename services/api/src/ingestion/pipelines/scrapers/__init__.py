"""
Initialization module for ingestion pipeline scrapers.

This package provides:
- BaseScraperPipeline: Abstract base class for scraper-based pipelines
- EventScraper: Playwright-based browser automation for web scraping
- ScraperConfig: Configuration dataclass for scrapers
- PageFetchResult: Result dataclass for page fetching
- Config loading utilities for JSON scraper configs
"""

from .base_scraper import BaseScraperPipeline as BaseScraperPipeline
from .base_scraper import EventScraper as EventScraper
from .base_scraper import PageFetchResult as PageFetchResult
from .base_scraper import ScraperConfig as ScraperConfig
from .base_scraper import load_scraper_config as load_scraper_config
