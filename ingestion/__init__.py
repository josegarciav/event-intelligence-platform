"""
Ingestion Layer for Event Intelligence Platform.

This package handles all data ingestion, parsing, normalization, and storage
of event data from external sources.

Key Components:
- BasePipeline: Abstract base class for all source-specific pipelines
- PipelineOrchestrator: Coordinates execution and scheduling of pipelines
- Source implementations: RaCoEventPipeline, MeetupEventPipeline, etc.
"""

from ingestion.base_pipeline import (
    BasePipeline,
    PipelineConfig,
    PipelineExecutionResult,
    PipelineStatus,
)
from ingestion.orchestrator import (
    PipelineOrchestrator,
    ScheduledPipeline,
    create_orchestrator_from_config,
)

__all__ = [
    "BasePipeline",
    "PipelineConfig",
    "PipelineExecutionResult",
    "PipelineStatus",
    "PipelineOrchestrator",
    "ScheduledPipeline",
    "create_orchestrator_from_config",
]
