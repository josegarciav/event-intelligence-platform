"""
Scraper-based event pipelines.

These pipelines use web scraping (via Playwright) to ingest events
from sources that don't have APIs.
"""

from .base_scraper_pipeline import BaseScraperPipeline

__all__ = [
    "BaseScraperPipeline",
]
