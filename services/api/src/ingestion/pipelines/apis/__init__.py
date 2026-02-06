"""
API-based event pipelines.

These pipelines use REST or GraphQL APIs to ingest events from sources
that provide programmatic access to their data.
"""

from .ra_co import RaCoPipeline, RaCoAdapter, create_ra_co_pipeline

__all__ = [
    "RaCoPipeline",
    "RaCoAdapter",
    "create_ra_co_pipeline",
]
