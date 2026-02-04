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
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid

from src.schemas.event import EventSchema
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
        self.execution_start_time = datetime.now(timezone.utc)

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
                    ended_at=datetime.now(timezone.utc),
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
                ended_at=datetime.now(timezone.utc),
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
                ended_at=datetime.now(timezone.utc),
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
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{self.config.source_name}_{timestamp}_{unique_id}"

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def to_dataframe(self, events: List[EventSchema]):
        """
        Convert events to comprehensive pandas DataFrame (Master Schema).

        This creates the master database from which all derived schemas
        (price, ticket_info, venue, etc.) can be built.

        Includes ALL fields from EventSchema with proper flattening of nested objects.
        """
        import pandas as pd
        import json

        rows = []
        for event in events:
            # ---- ARTISTS (from custom_fields) ----
            artists_list = event.custom_fields.get("artists", [])
            artists_str = ", ".join(
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in artists_list
            )

            # ---- TAXONOMY DIMENSIONS (JSON + flattened primary) ----
            taxonomy_json = json.dumps(
                [
                    {
                        "primary_category": dim.primary_category,
                        "subcategory": dim.subcategory,
                        "subcategory_name": dim.subcategory_name,
                        "values": dim.values,
                        "confidence": dim.confidence,
                        "activity_id": dim.activity_id,
                        "activity_name": dim.activity_name,
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

            # Get primary taxonomy dimension for flat columns
            primary_dim = (
                event.taxonomy_dimensions[0] if event.taxonomy_dimensions else None
            )

            # ---- ENUM VALUE EXTRACTION ----
            def get_enum_value(val):
                if val is None:
                    return None
                return val.value if hasattr(val, "value") else str(val)

            # ---- LOCATION FLATTENING ----
            loc = event.location
            lat = loc.coordinates.latitude if loc.coordinates else None
            lon = loc.coordinates.longitude if loc.coordinates else None

            # ---- PRICE FLATTENING ----
            price = event.price

            # ---- TICKET INFO FLATTENING ----
            ticket = event.ticket_info

            # ---- ORGANIZER FLATTENING ----
            org = event.organizer

            # ---- SOURCE FLATTENING ----
            src = event.source

            # ---- ENGAGEMENT FLATTENING ----
            eng = event.engagement

            # ---- MEDIA ASSETS (JSON) ----
            media_json = (
                json.dumps(
                    [
                        {
                            "type": m.type,
                            "url": m.url,
                            "title": m.title,
                            "description": m.description,
                        }
                        for m in event.media_assets
                    ]
                )
                if event.media_assets
                else None
            )

            row = {
                # ==== CORE EVENT INFO ====
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                # ==== TIMING ====
                "start_datetime": event.start_datetime,
                "end_datetime": event.end_datetime,
                "duration_minutes": event.duration_minutes,
                "is_all_day": event.is_all_day,
                "is_recurring": event.is_recurring,
                "recurrence_pattern": event.recurrence_pattern,
                # ==== LOCATION (flattened) ====
                "venue_name": loc.venue_name,
                "street_address": loc.street_address,
                "city": loc.city,
                "state_or_region": loc.state_or_region,
                "postal_code": loc.postal_code,
                "country_code": loc.country_code,
                "latitude": lat,
                "longitude": lon,
                "timezone": loc.timezone,
                # ==== EVENT DETAILS ====
                "event_type": get_enum_value(event.event_type),
                "event_format": get_enum_value(event.format),
                "capacity": event.capacity,
                "age_restriction": event.age_restriction,
                # ==== PRICE (flattened) ====
                "price_currency": price.currency if price else None,
                "price_is_free": price.is_free if price else None,
                "price_minimum": (
                    float(price.minimum_price)
                    if price and price.minimum_price
                    else None
                ),
                "price_maximum": (
                    float(price.maximum_price)
                    if price and price.maximum_price
                    else None
                ),
                "price_early_bird": (
                    float(price.early_bird_price)
                    if price and price.early_bird_price
                    else None
                ),
                "price_standard": (
                    float(price.standard_price)
                    if price and price.standard_price
                    else None
                ),
                "price_vip": (
                    float(price.vip_price) if price and price.vip_price else None
                ),
                "price_raw_text": price.price_raw_text if price else None,
                # ==== TICKET INFO (flattened) ====
                "ticket_url": ticket.url if ticket else None,
                "ticket_is_sold_out": ticket.is_sold_out if ticket else None,
                "ticket_count_available": (
                    ticket.ticket_count_available if ticket else None
                ),
                "ticket_early_bird_deadline": (
                    ticket.early_bird_deadline if ticket else None
                ),
                # ==== ORGANIZER (flattened) ====
                "organizer_name": org.name if org else None,
                "organizer_url": org.url if org else None,
                "organizer_email": org.email if org else None,
                "organizer_phone": org.phone if org else None,
                "organizer_image_url": org.image_url if org else None,
                "organizer_follower_count": org.follower_count if org else None,
                "organizer_verified": org.verified if org else None,
                # ==== SOURCE (flattened) ====
                "source_name": src.source_name if src else None,
                "source_event_id": src.source_event_id if src else None,
                "source_url": src.source_url if src else None,
                "source_last_updated": src.last_updated_from_source if src else None,
                "source_ingestion_timestamp": src.ingestion_timestamp if src else None,
                # ==== MEDIA ====
                "image_url": event.image_url,
                "media_assets_json": media_json,
                # ==== ENGAGEMENT (flattened) ====
                "engagement_going_count": eng.going_count if eng else None,
                "engagement_interested_count": eng.interested_count if eng else None,
                "engagement_views_count": eng.views_count if eng else None,
                "engagement_shares_count": eng.shares_count if eng else None,
                "engagement_comments_count": eng.comments_count if eng else None,
                "engagement_likes_count": eng.likes_count if eng else None,
                "engagement_last_updated": eng.last_updated if eng else None,
                # ==== TAXONOMY - PRIMARY CATEGORY ====
                "primary_category": get_enum_value(event.primary_category),
                # ==== TAXONOMY - PRIMARY DIMENSION (flattened) ====
                "taxonomy_subcategory": (
                    primary_dim.subcategory if primary_dim else None
                ),
                "taxonomy_subcategory_name": (
                    primary_dim.subcategory_name if primary_dim else None
                ),
                "taxonomy_values": (
                    ", ".join(primary_dim.values)
                    if primary_dim and primary_dim.values
                    else None
                ),
                "taxonomy_confidence": primary_dim.confidence if primary_dim else None,
                "taxonomy_activity_id": (
                    primary_dim.activity_id if primary_dim else None
                ),
                "taxonomy_activity_name": (
                    primary_dim.activity_name if primary_dim else None
                ),
                "taxonomy_energy_level": (
                    primary_dim.energy_level if primary_dim else None
                ),
                "taxonomy_social_intensity": (
                    primary_dim.social_intensity if primary_dim else None
                ),
                "taxonomy_cognitive_load": (
                    primary_dim.cognitive_load if primary_dim else None
                ),
                "taxonomy_physical_involvement": (
                    primary_dim.physical_involvement if primary_dim else None
                ),
                "taxonomy_cost_level": primary_dim.cost_level if primary_dim else None,
                "taxonomy_time_scale": primary_dim.time_scale if primary_dim else None,
                "taxonomy_environment": (
                    primary_dim.environment if primary_dim else None
                ),
                "taxonomy_emotional_output": (
                    ", ".join(primary_dim.emotional_output)
                    if primary_dim and primary_dim.emotional_output
                    else None
                ),
                "taxonomy_risk_level": primary_dim.risk_level if primary_dim else None,
                "taxonomy_age_accessibility": (
                    primary_dim.age_accessibility if primary_dim else None
                ),
                "taxonomy_repeatability": (
                    primary_dim.repeatability if primary_dim else None
                ),
                # ==== FULL TAXONOMY JSON (all dimensions) ====
                "taxonomy_dimensions_json": taxonomy_json,
                # ==== QUALITY & ERRORS ====
                "data_quality_score": event.data_quality_score,
                "normalization_errors": (
                    ", ".join(event.normalization_errors)
                    if event.normalization_errors
                    else None
                ),
                # ==== ADDITIONAL METADATA ====
                "tags": ", ".join(event.tags) if event.tags else None,
                "artists": artists_str,
                "custom_fields_json": (
                    json.dumps(event.custom_fields) if event.custom_fields else None
                ),
                # ==== PLATFORM TIMESTAMPS ====
                "created_at": event.created_at,
                "updated_at": event.updated_at,
            }
            rows.append(row)

        return pd.DataFrame(rows)

    def close(self) -> None:
        """Release adapter resources."""
        if self.adapter:
            self.adapter.close()
