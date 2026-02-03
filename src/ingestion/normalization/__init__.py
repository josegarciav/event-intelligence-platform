"""
Normalization module for event data.

This package provides:
- EventSchema: Canonical event data model
- Taxonomy models: PrimaryCategory, TaxonomyDimension, Subcategory
- Location/Price/Organizer models: LocationInfo, PriceInfo, OrganizerInfo, etc.
- CurrencyParser: Price string parsing utilities
- TaxonomyMapper: Taxonomy classification helpers
- FeatureExtractor: Feature extraction from raw events
- FieldMapper: Field mapping utilities
"""

from .event_schema import (
    EventSchema,
    EventBatch,
    PrimaryCategory,
    EventType,
    EventFormat,
    DayOfWeek,
    TaxonomyDimension,
    Subcategory,
    Coordinates,
    LocationInfo,
    PriceInfo,
    TicketInfo,
    OrganizerInfo,
    SourceInfo,
    MediaAsset,
    EngagementMetrics,
)
from .currency import CurrencyParser
from .taxonomy_mapper import TaxonomyMapper, create_taxonomy_mapper_from_config
from .taxonomy import (
    load_taxonomy,
    build_taxonomy_index,
    get_all_subcategory_options,
    get_all_subcategory_ids,
    get_activity_by_id,
    get_subcategory_by_id,
    get_activities_for_subcategory,
    find_best_activity_match,
    get_primary_category_for_subcategory,
    get_full_taxonomy_dimension,
    list_all_activities,
    search_activities_by_name,
)
from .feature_extractor import FeatureExtractor, create_feature_extractor_from_config
from .field_mapper import FieldMapper, create_field_mapper_from_config

__all__ = [
    # Event Schema
    "EventSchema",
    "EventBatch",
    # Enums
    "PrimaryCategory",
    "EventType",
    "EventFormat",
    "DayOfWeek",
    # Taxonomy
    "TaxonomyDimension",
    "Subcategory",
    # Location
    "Coordinates",
    "LocationInfo",
    # Pricing
    "PriceInfo",
    "TicketInfo",
    # Organizer & Source
    "OrganizerInfo",
    "SourceInfo",
    # Media
    "MediaAsset",
    "EngagementMetrics",
    # Currency
    "CurrencyParser",
    # Taxonomy Mapper
    "TaxonomyMapper",
    "create_taxonomy_mapper_from_config",
    # Taxonomy helpers
    "load_taxonomy",
    "build_taxonomy_index",
    "get_all_subcategory_options",
    "get_all_subcategory_ids",
    "get_activity_by_id",
    "get_subcategory_by_id",
    "get_activities_for_subcategory",
    "find_best_activity_match",
    "get_primary_category_for_subcategory",
    "get_full_taxonomy_dimension",
    "list_all_activities",
    "search_activities_by_name",
    # Feature Extractor
    "FeatureExtractor",
    "create_feature_extractor_from_config",
    # Field Mapper
    "FieldMapper",
    "create_field_mapper_from_config",
]
