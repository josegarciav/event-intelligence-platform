"""
Scraper-based event pipelines.

These pipelines use web scraping (via the scrapping library) to ingest events
from sources that don't have APIs or when scraping is more appropriate.
"""

from .base_scraper_pipeline import BaseScraperPipeline
from .ra_co_scraper import RaCoScraperPipeline

__all__ = [
    "BaseScraperPipeline",
    "RaCoScraperPipeline",
]
