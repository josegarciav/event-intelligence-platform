"""
Base Pipeline Class Architecture.

This module defines the abstract base class and interfaces that all source-specific
pipelines must implement. It enforces a consistent pattern for data ingestion,
validation, normalization, and storage across all sources.

Any new data source (ra.co, Meetup, Ticketmaster, etc.) must inherit from
BasePipeline and implement the required abstract methods.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from normalization.event_schema import EventSchema, EventBatch

# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================


class PipelineStatus(str, Enum):
    """
    Status of a pipeline execution.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


@dataclass
class PipelineConfig:
    """
    Configuration for a pipeline instance.
    """

    source_name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    request_timeout: int = 30
    max_retries: int = 3
    batch_size: int = 100
    rate_limit_per_second: float = 1.0
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineExecutionResult:
    """
    Result of a pipeline execution.
    """

    status: PipelineStatus
    source_name: str
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
        """
        Calculate execution duration in seconds.
        """
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """
        Calculate success rate as percentage.
        """
        if self.total_events_processed == 0:
            return 0.0
        return (self.successful_events / self.total_events_processed) * 100


# ============================================================================
# BASE PIPELINE CLASS
# ============================================================================


class BasePipeline(ABC):
    """
    Abstract base class for all event ingestion pipelines.

    This class enforces a standardized workflow:
    1. Fetch raw data from the source
    2. Parse and extract structured data
    3. Normalize to canonical schema
    4. Validate and assess data quality
    5. Store results

    Each source-specific pipeline must inherit from this class and implement
    the abstract methods according to that source's API/scraping requirements.
    """

    def __init__(self, config: PipelineConfig):
        """
        Initialize the pipeline.

        Args:
            config: PipelineConfig instance with source-specific settings
        """
        self.config = config
        self.logger = self._setup_logger()
        self.execution_id: Optional[str] = None
        self.execution_start_time: Optional[datetime] = None

    def _setup_logger(self) -> logging.Logger:
        """
        Setup source-specific logger.
        """
        logger = logging.getLogger(f"pipeline.{self.config.source_name}")
        logger.setLevel(logging.INFO)
        return logger

    # ========================================================================
    # ABSTRACT METHODS - Must be implemented by subclasses
    # ========================================================================

    @abstractmethod
    def fetch_raw_data(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch raw event data from the source.

        This is the first step in the pipeline. Implement source-specific
        API calls, web scraping, or file parsing logic here.

        Args:
            **kwargs: Source-specific parameters (e.g., city, date range, limit)

        Returns:
            List of raw event data dictionaries

        Raises:
            Exception: Connection errors, API failures, etc.

        Example (for ra.co):
            - Call ra.co API with pagination
            - Handle rate limiting
            - Return raw JSON response as list of dicts
        """
        pass

    @abstractmethod
    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw event data into an intermediate structured format.

        This method extracts and cleans the raw data from the source into
        a consistent intermediate format before normalization to the
        canonical schema.

        Args:
            raw_event: Single raw event from source

        Returns:
            Parsed event with standardized intermediate keys

        Raises:
            ValueError: If critical fields are missing or malformed

        Example (for ra.co):
            Extract 'title', 'date', 'venue', 'artists', 'url', etc.
            Handle various date/time formats
            Normalize venue information
        """
        pass

    @abstractmethod
    def map_to_taxonomy(
        self, parsed_event: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Map parsed event to Human Experience Taxonomy categories.

        This method determines which primary category and subcategories
        (from the Human Experience Taxonomy) this event belongs to,
        along with confidence scores.

        Args:
            parsed_event: Parsed event dictionary

        Returns:
            Tuple of (primary_category, taxonomy_dimensions)
            - primary_category: str (enum value)
            - taxonomy_dimensions: List of dicts with category, subcategory, values, confidence

        Example (for ra.co DJ set):
            - Primary: "play_and_fun"
            - Dimensions: [
                {"primary": "play_and_fun", "sub": "music_rhythm", "values": [...], "confidence": 0.95},
                {"primary": "social_connection", "sub": "shared_activities", "values": [...], "confidence": 0.8}
              ]
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
        Normalize parsed event to the canonical EventSchema.

        This is the core normalization step. Transform all parsed event data
        into the canonical EventSchema, mapping source fields to schema fields,
        handling data type conversions, validations, and enrichments.

        Args:
            parsed_event: Parsed event dictionary
            primary_cat: Primary taxonomy category
            taxonomy_dims: Taxonomy dimensions from map_to_taxonomy()

        Returns:
            EventSchema instance (fully validated)

        Raises:
            ValueError: If required fields cannot be mapped or validated

        Example (for ra.co):
            - Map 'title' -> EventSchema.title
            - Map 'date' -> EventSchema.start_datetime (handle timezone)
            - Map 'venue' -> EventSchema.location
            - Map 'min_entry' -> EventSchema.price.minimum_price
            - Generate event_id from source_event_id
            - Set source metadata
        """
        pass

    @abstractmethod
    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """
        Validate a normalized event and assess data quality.

        This method performs additional validation beyond schema validation,
        including business logic checks, data quality assessment, and
        enrichment opportunity identification.

        Args:
            event: Normalized EventSchema instance

        Returns:
            Tuple of (is_valid, errors_and_warnings)
            - is_valid: bool (True if event passes validation, False otherwise)
            - errors_and_warnings: List of validation messages

        Example checks:
            - Location exists and is valid
            - Start time is in the future (or within acceptable range)
            - Price is reasonable for event type/location (not 0 for paid events)
            - Organizer name is not empty
            - Image URL is accessible
        """
        pass

    @abstractmethod
    def enrich_event(self, event: EventSchema) -> EventSchema:
        """
        Enrich the event with additional data and inferred information.

        This method adds value to the event data by performing enrichments:
        - Geocoding locations to get missing coordinates
        - Inferring timezone from location
        - Calculating duration from start/end times
        - Fetching organizer social metrics
        - Predicting event popularity based on historical patterns

        Args:
            event: EventSchema instance to enrich

        Returns:
            Enriched EventSchema instance

        Note:
            Enrichment failures should NOT prevent event storage.
            Use event.normalization_errors to track issues.
        """
        pass

    # ========================================================================
    # CONCRETE METHODS - Pipeline orchestration
    # ========================================================================

    def execute(self, **kwargs) -> PipelineExecutionResult:
        """
        Execute the full pipeline workflow.

        This is the main entry point. It orchestrates all steps:
        1. Fetch raw data
        2. Parse each event
        3. Map to taxonomy
        4. Normalize to schema
        5. Validate
        6. Enrich
        7. Store results

        Args:
            **kwargs: Parameters passed to fetch_raw_data()

        Returns:
            PipelineExecutionResult with summary and events
        """
        self.execution_id = self._generate_execution_id()
        self.execution_start_time = datetime.utcnow()

        self.logger.info(f"Starting pipeline execution: {self.execution_id}")

        try:
            raw_events = self.fetch_raw_data(**kwargs)
            self.logger.info(f"Fetched {len(raw_events)} raw events")

            normalized_events = self._process_events_batch(raw_events)

            result = PipelineExecutionResult(
                status=(
                    PipelineStatus.SUCCESS
                    if normalized_events
                    else PipelineStatus.FAILED
                ),
                source_name=self.config.source_name,
                execution_id=self.execution_id,
                started_at=self.execution_start_time,
                ended_at=datetime.utcnow(),
                total_events_processed=len(raw_events),
                successful_events=len(normalized_events),
                events=normalized_events,
            )

            self.logger.info(
                f"Pipeline execution completed: {result.successful_events}/{result.total_events_processed} successful"
            )
            return result

        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
            return PipelineExecutionResult(
                status=PipelineStatus.FAILED,
                source_name=self.config.source_name,
                execution_id=self.execution_id,
                started_at=self.execution_start_time,
                ended_at=datetime.utcnow(),
                errors=[{"error": str(e), "timestamp": datetime.utcnow().isoformat()}],
            )

    def _process_events_batch(
        self, raw_events: List[Dict[str, Any]]
    ) -> List[EventSchema]:
        """
        Process a batch of raw events through the normalization pipeline.
        """
        normalized_events = []

        for idx, raw_event in enumerate(raw_events):
            try:
                # Step 1: Parse
                parsed_event = self.parse_raw_event(raw_event)
                self.logger.debug(f"Parsed event {idx+1}/{len(raw_events)}")

                # Step 2: Taxonomy mapping
                primary_cat, taxonomy_dims = self.map_to_taxonomy(parsed_event)

                # Step 3: Normalize
                event = self.normalize_to_schema(
                    parsed_event, primary_cat, taxonomy_dims
                )

                # Step 4: Validate
                is_valid, validation_messages = self.validate_event(event)
                event.normalization_errors.extend(validation_messages)

                if not is_valid:
                    self.logger.warning(
                        f"Event validation warnings: {validation_messages}"
                    )

                # Step 5: Enrich
                event = self.enrich_event(event)

                # Step 6: Calculate quality score
                event.data_quality_score = self._calculate_quality_score(event)

                normalized_events.append(event)

            except Exception as e:
                self.logger.error(
                    f"Failed to process event {idx+1}: {str(e)}", exc_info=True
                )
                # Continue processing remaining events
                continue

        return normalized_events

    def _calculate_quality_score(self, event: EventSchema) -> float:
        """
        Calculate data quality score (0.0-1.0) for an event.
        TO IMPLEMENT a basic heuristic based on several factors.

        Factors:
        - Presence of key fields (title, location, start_datetime)
        - Presence of optional enrichment fields (image, coordinates, price)
        - Validation errors/warnings
        - Taxonomy confidence scores
        """
        score = 0.0

        # Key fields: worth 40%
        key_fields_present = all(
            [
                event.title,
                event.location.city,
                event.start_datetime,
            ]
        )
        score += 0.4 if key_fields_present else 0.0

        # Enrichment fields: worth 30%
        enrichment_bonus = 0.0
        enrichment_bonus += 0.05 if event.image_url else 0.0
        enrichment_bonus += 0.05 if event.location.coordinates else 0.0
        enrichment_bonus += 0.05 if not event.price.is_free else 0.0
        enrichment_bonus += 0.05 if event.organizer.name else 0.0
        enrichment_bonus += 0.05 if event.end_datetime else 0.0
        enrichment_bonus += 0.05 if event.media_assets else 0.0
        score += min(enrichment_bonus, 0.3)

        # Taxonomy confidence: worth 20%
        if event.taxonomy_dimensions:
            avg_confidence = sum(
                dim.confidence for dim in event.taxonomy_dimensions
            ) / len(event.taxonomy_dimensions)
            score += avg_confidence * 0.2

        # Penalize validation errors: up to -10%
        error_penalty = min(len(event.normalization_errors) * 0.02, 0.1)
        score -= error_penalty

        return max(0.0, min(score, 1.0))

    def _generate_execution_id(self) -> str:
        """
        Generate unique execution identifier.
        """
        import uuid

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{self.config.source_name}_{timestamp}_{unique_id}"

    # ========================================================================
    # HELPER METHODS - Utilities for subclasses
    # ========================================================================

    def handle_api_error(self, error: Exception, retry_count: int) -> bool:
        """
        Handle API errors with retry logic.

        Args:
            error: The exception that occurred
            retry_count: Current retry attempt number

        Returns:
            True if should retry, False if should give up
        """
        if retry_count >= self.config.max_retries:
            self.logger.error(f"Max retries exceeded: {error}")
            return False

        self.logger.warning(f"API error (attempt {retry_count + 1}): {error}")
        return True

    def rate_limit_delay(self) -> None:
        """
        Apply rate limiting delay if configured.
        """
        import time

        delay = 1.0 / self.config.rate_limit_per_second
        time.sleep(delay)
