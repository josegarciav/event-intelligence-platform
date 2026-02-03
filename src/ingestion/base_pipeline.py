"""
Base Pipeline Architecture.

This module defines the abstract base class for all event ingestion pipelines.
Pipelines handle the complete workflow from raw data fetching to normalized
EventSchema output, using source adapters for data retrieval.

Architecture:
    SourceAdapter (API/Scraper) → BasePipeline → EventSchema

Any new data source must:
1. Create an adapter (or use existing API/Scraper adapter)
2. Inherit from BasePipeline and implement abstract methods
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid

from src.ingestion.normalization.event_schema import EventSchema
from src.ingestion.adapters import BaseSourceAdapter, SourceType


class PipelineStatus(str, Enum):
    """Status of a pipeline execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


@dataclass
class PipelineConfig:
    """
    Configuration for a pipeline instance.

    This is pipeline-level config, separate from adapter-level config.
    """

    source_name: str
    source_type: SourceType = SourceType.API
    request_timeout: int = 30
    max_retries: int = 3
    batch_size: int = 100
    rate_limit_per_second: float = 1.0
    deduplicate: bool = True
    deduplication_strategy: str = "exact"
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineExecutionResult:
    """Result of a pipeline execution."""

    status: PipelineStatus
    source_name: str
    source_type: SourceType
    execution_id: str
    started_at: datetime
    ended_at: datetime
    total_events_processed: int = 0
    successful_events: int = 0
    failed_events: int = 0
    events: List[EventSchema] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Calculate execution duration."""
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_events_processed == 0:
            return 0.0
        return (self.successful_events / self.total_events_processed) * 100


class BasePipeline(ABC):
    """
    Abstract base class for all event ingestion pipelines.

    Pipelines implement a standardized workflow:
    1. Fetch raw data (via adapter)
    2. Parse raw data to intermediate format
    3. Map to taxonomy categories
    4. Normalize to EventSchema
    5. Validate events
    6. Enrich with additional data

    Subclasses must:
    - Provide an adapter in __init__
    - Implement all abstract methods for source-specific logic
    """

    def __init__(self, config: PipelineConfig, adapter: BaseSourceAdapter):
        """
        Initialize the pipeline.

        Args:
            config: PipelineConfig with pipeline settings
            adapter: Source adapter for data fetching
        """
        self.config = config
        self.adapter = adapter
        self.logger = self._setup_logger()
        self.execution_id: Optional[str] = None
        self.execution_start_time: Optional[datetime] = None

    def _setup_logger(self) -> logging.Logger:
        """Setup source-specific logger."""
        logger = logging.getLogger(f"pipeline.{self.config.source_name}")
        logger.setLevel(logging.INFO)
        return logger

    @property
    def source_type(self) -> SourceType:
        """Get the source type from adapter."""
        return self.adapter.source_type

    # ========================================================================
    # ABSTRACT METHODS - Must be implemented by subclasses
    # ========================================================================

    @abstractmethod
    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw event data into intermediate structured format.

        Args:
            raw_event: Single raw event from adapter

        Returns:
            Parsed event with standardized intermediate keys
        """
        pass

    @abstractmethod
    def map_to_taxonomy(
        self, parsed_event: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Map parsed event to Human Experience Taxonomy.

        Args:
            parsed_event: Parsed event dictionary

        Returns:
            Tuple of (primary_category, taxonomy_dimensions)
        """
        pass

    @abstractmethod
    def normalize_to_schema(
        self,
        parsed_event: Dict[str, Any],
        primary_cat: str,
        taxonomy_dims: List[Dict[str, Any]],
    ) -> EventSchema:
        """
        Normalize parsed event to canonical EventSchema.

        Args:
            parsed_event: Parsed event dictionary
            primary_cat: Primary taxonomy category
            taxonomy_dims: Taxonomy dimensions

        Returns:
            EventSchema instance
        """
        pass

    @abstractmethod
    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """
        Validate a normalized event.

        Args:
            event: Normalized EventSchema instance

        Returns:
            Tuple of (is_valid, validation_messages)
        """
        pass

    @abstractmethod
    def enrich_event(self, event: EventSchema) -> EventSchema:
        """
        Enrich event with additional data.

        Args:
            event: EventSchema to enrich

        Returns:
            Enriched EventSchema
        """
        pass

    # ========================================================================
    # CONCRETE METHODS - Pipeline execution
    # ========================================================================

    def execute(self, **kwargs) -> PipelineExecutionResult:
        """
        Execute the full pipeline workflow.

        Args:
            **kwargs: Parameters passed to the adapter's fetch method

        Returns:
            PipelineExecutionResult with summary and events
        """
        self.execution_id = self._generate_execution_id()
        self.execution_start_time = datetime.utcnow()

        self.logger.info(f"Starting pipeline execution: {self.execution_id}")
        self.logger.info(f"Source type: {self.source_type.value}")

        try:
            # Step 1: Fetch raw data via adapter
            fetch_result = self.adapter.fetch(**kwargs)

            if not fetch_result.success:
                self.logger.error(f"Fetch failed: {fetch_result.errors}")
                return PipelineExecutionResult(
                    status=PipelineStatus.FAILED,
                    source_name=self.config.source_name,
                    source_type=self.source_type,
                    execution_id=self.execution_id,
                    started_at=self.execution_start_time,
                    ended_at=datetime.utcnow(),
                    errors=[
                        {"error": e, "stage": "fetch"} for e in fetch_result.errors
                    ],
                    metadata=fetch_result.metadata,
                )

            self.logger.info(f"Fetched {fetch_result.total_fetched} raw events")

            # Step 2-6: Process events through pipeline
            normalized_events = self._process_events_batch(fetch_result.raw_data)

            # Step 7: Deduplication
            if self.config.deduplicate and normalized_events:
                from src.ingestion.deduplication import (
                    get_deduplicator,
                    DeduplicationStrategy,
                )

                deduplicator = get_deduplicator(
                    DeduplicationStrategy(self.config.deduplication_strategy)
                )
                before_count = len(normalized_events)
                normalized_events = deduplicator.deduplicate(normalized_events)
                self.logger.info(
                    f"Deduplication: {before_count} -> {len(normalized_events)} events"
                )

            status = (
                PipelineStatus.SUCCESS if normalized_events else PipelineStatus.FAILED
            )
            if normalized_events and len(normalized_events) < len(
                fetch_result.raw_data
            ):
                status = PipelineStatus.PARTIAL_SUCCESS

            result = PipelineExecutionResult(
                status=status,
                source_name=self.config.source_name,
                source_type=self.source_type,
                execution_id=self.execution_id,
                started_at=self.execution_start_time,
                ended_at=datetime.utcnow(),
                total_events_processed=len(fetch_result.raw_data),
                successful_events=len(normalized_events),
                failed_events=len(fetch_result.raw_data) - len(normalized_events),
                events=normalized_events,
                metadata={
                    **fetch_result.metadata,
                    "fetch_duration_s": fetch_result.duration_seconds,
                },
            )

            self.logger.info(
                f"Pipeline completed: {result.successful_events}/{result.total_events_processed} successful"
            )
            return result

        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            return PipelineExecutionResult(
                status=PipelineStatus.FAILED,
                source_name=self.config.source_name,
                source_type=self.source_type,
                execution_id=self.execution_id,
                started_at=self.execution_start_time,
                ended_at=datetime.utcnow(),
                errors=[{"error": str(e), "stage": "execution"}],
            )

    def _process_events_batch(
        self, raw_events: List[Dict[str, Any]]
    ) -> List[EventSchema]:
        """Process a batch of raw events through the pipeline."""
        normalized_events = []

        for idx, raw_event in enumerate(raw_events):
            try:
                # Step 2: Parse
                parsed_event = self.parse_raw_event(raw_event)

                # Step 3: Taxonomy mapping
                primary_cat, taxonomy_dims = self.map_to_taxonomy(parsed_event)

                # Step 4: Normalize
                event = self.normalize_to_schema(
                    parsed_event, primary_cat, taxonomy_dims
                )

                # Step 5: Validate
                is_valid, validation_messages = self.validate_event(event)
                event.normalization_errors.extend(validation_messages)

                if not is_valid:
                    self.logger.warning(
                        f"Validation warnings for event {idx}: {validation_messages}"
                    )

                # Step 6: Enrich
                event = self.enrich_event(event)

                # Calculate quality score
                event.data_quality_score = self._calculate_quality_score(event)

                normalized_events.append(event)

            except Exception as e:
                self.logger.error(f"Failed to process event {idx}: {e}", exc_info=True)
                continue

        return normalized_events

    def _calculate_quality_score(self, event: EventSchema) -> float:
        """Calculate data quality score (0.0-1.0)."""
        score = 0.0

        # Key fields (40%)
        key_fields_present = all(
            [
                event.title,
                event.location.city,
                event.start_datetime,
            ]
        )
        score += 0.4 if key_fields_present else 0.0

        # Enrichment fields (30%)
        enrichment_bonus = 0.0
        enrichment_bonus += 0.05 if event.image_url else 0.0
        enrichment_bonus += 0.05 if event.location.coordinates else 0.0
        enrichment_bonus += 0.05 if event.price and not event.price.is_free else 0.0
        enrichment_bonus += 0.05 if event.organizer and event.organizer.name else 0.0
        enrichment_bonus += 0.05 if event.end_datetime else 0.0
        enrichment_bonus += 0.05 if event.description else 0.0
        score += min(enrichment_bonus, 0.3)

        # Taxonomy confidence (20%)
        if event.taxonomy_dimensions:
            avg_confidence = sum(
                dim.confidence for dim in event.taxonomy_dimensions
            ) / len(event.taxonomy_dimensions)
            score += avg_confidence * 0.2

        # Penalize validation errors (up to -10%)
        error_penalty = min(len(event.normalization_errors) * 0.02, 0.1)
        score -= error_penalty

        return max(0.0, min(score, 1.0))

    def _generate_execution_id(self) -> str:
        """Generate unique execution identifier."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{self.config.source_name}_{timestamp}_{unique_id}"

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def to_dataframe(self, events: List[EventSchema]):
        """
        Convert events to pandas DataFrame.

        Includes:
        - Core event fields (title, description, dates, location)
        - Pricing information
        - Primary taxonomy dimension with all enrichment fields
        - Full taxonomy JSON for reference
        """
        import pandas as pd
        import json

        rows = []
        for event in events:
            artists_list = event.custom_fields.get("artists", [])
            artists_str = ", ".join(
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in artists_list
            )

            # Build full taxonomy JSON with all fields
            taxonomy_json = json.dumps(
                [
                    {
                        "primary_category": dim.primary_category,
                        "subcategory": dim.subcategory,
                        "subcategory_name": dim.subcategory_name,
                        "activity_id": dim.activity_id,
                        "activity_name": dim.activity_name,
                        "confidence": dim.confidence,
                        "energy_level": dim.energy_level,
                        "social_intensity": dim.social_intensity,
                        "cognitive_load": dim.cognitive_load,
                        "physical_involvement": dim.physical_involvement,
                        "cost_level": dim.cost_level,
                        "time_scale": dim.time_scale,
                        "environment": dim.environment,
                        "emotional_output": dim.emotional_output,
                        "risk_level": dim.risk_level,
                        "age_accessibility": dim.age_accessibility,
                        "repeatability": dim.repeatability,
                    }
                    for dim in event.taxonomy_dimensions
                ]
            )

            # Handle event_type which could be Enum or string
            event_type_val = None
            if event.event_type:
                event_type_val = (
                    event.event_type.value
                    if hasattr(event.event_type, "value")
                    else str(event.event_type)
                )

            format_val = None
            if event.format:
                format_val = (
                    event.format.value
                    if hasattr(event.format, "value")
                    else str(event.format)
                )

            # Get primary taxonomy dimension for flat columns
            primary_dim = (
                event.taxonomy_dimensions[0] if event.taxonomy_dimensions else None
            )

            row = {
                # Core event info
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description[:500] if event.description else None,
                "start_datetime": event.start_datetime,
                "end_datetime": event.end_datetime,
                "duration_minutes": event.duration_minutes,
                # Location
                "city": event.location.city,
                "country_code": event.location.country_code,
                "venue_name": event.location.venue_name,
                # Artists
                "artists": artists_str,
                # Taxonomy - primary category
                "primary_category": event.primary_category,
                "subcategory": primary_dim.subcategory if primary_dim else None,
                "subcategory_name": primary_dim.subcategory_name if primary_dim else None,
                # Taxonomy - activity level fields
                "activity_name": primary_dim.activity_name if primary_dim else None,
                "energy_level": primary_dim.energy_level if primary_dim else None,
                "social_intensity": primary_dim.social_intensity if primary_dim else None,
                "cognitive_load": primary_dim.cognitive_load if primary_dim else None,
                "physical_involvement": (
                    primary_dim.physical_involvement if primary_dim else None
                ),
                "cost_level": primary_dim.cost_level if primary_dim else None,
                "time_scale": primary_dim.time_scale if primary_dim else None,
                "environment": primary_dim.environment if primary_dim else None,
                "emotional_output": (
                    ", ".join(primary_dim.emotional_output)
                    if primary_dim and primary_dim.emotional_output
                    else None
                ),
                "risk_level": primary_dim.risk_level if primary_dim else None,
                "age_accessibility": (
                    primary_dim.age_accessibility if primary_dim else None
                ),
                "repeatability": primary_dim.repeatability if primary_dim else None,
                # Full taxonomy JSON
                "taxonomy_json": taxonomy_json,
                # Event type & format
                "event_type": event_type_val,
                "format": format_val,
                # Pricing
                "is_free": event.price.is_free if event.price else None,
                "min_price": (
                    float(event.price.minimum_price)
                    if event.price and event.price.minimum_price
                    else None
                ),
                "max_price": (
                    float(event.price.maximum_price)
                    if event.price and event.price.maximum_price
                    else None
                ),
                "currency_code": event.price.currency if event.price else None,
                # Organizer & source
                "organizer": event.organizer.name if event.organizer else None,
                "source_url": event.source.source_url if event.source else None,
                "image_url": event.image_url,
                # Quality
                "data_quality_score": event.data_quality_score,
            }
            rows.append(row)

        return pd.DataFrame(rows)

    def close(self) -> None:
        """Release adapter resources."""
        if self.adapter:
            self.adapter.close()
