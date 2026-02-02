"""
HTML parsers for scraper pipelines.

Each source has its own parser that extracts structured event data from HTML pages.
"""

from .ra_co_parser import RaCoEventParser

__all__ = [
    "RaCoEventParser",
]
