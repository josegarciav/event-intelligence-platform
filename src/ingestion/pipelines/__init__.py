"""
Event sources module for ingestion pipelines.

This package contains all source-specific pipeline implementations.
Each source implements the BasePipeline interface to handle:
- Fetching raw data from the source
- Parsing and extracting structured information
- Mapping to the Human Experience Taxonomy
- Normalizing to the canonical EventSchema
"""
