"""
Normalization module for event data.

This package contains:
- event_schema.py: Canonical EventSchema and all related Pydantic models
- schema.py: (legacy - to be consolidated)
- enrich.py: Enrichment logic and utilities
"""

from normalization.event_schema import (
    EventSchema,
    EventBatch,
    PrimaryCategory,
    Subcategory,
    EventType,
    EventFormat,
    LocationInfo,
    Coordinates,
    PriceInfo,
    TicketInfo,
    OrganizerInfo,
    SourceInfo,
    TaxonomyDimension,
)

__all__ = [
    "EventSchema",
    "EventBatch",
    "PrimaryCategory",
    "Subcategory",
    "EventType",
    "EventFormat",
    "LocationInfo",
    "Coordinates",
    "PriceInfo",
    "TicketInfo",
    "OrganizerInfo",
    "SourceInfo",
    "TaxonomyDimension",
]
