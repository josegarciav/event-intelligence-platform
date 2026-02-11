"""
Unit tests for the base_pipeline module.

Tests for BasePipeline, PipelineConfig, and PipelineExecutionResult.
"""

from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import MagicMock
from typing import Dict, Any, List, Tuple

import pytest

from src.ingestion.base_pipeline import (
    BasePipeline,
    PipelineConfig,
    PipelineExecutionResult,
    PipelineStatus,
)
from src.ingestion.adapters import BaseSourceAdapter, SourceType, FetchResult
from src.schemas.event import (
    EventSchema,
    EventFormat,
    LocationInfo,
    OrganizerInfo,
    PrimaryCategory,
    SourceInfo,
    TaxonomyDimension,
)
from src.schemas.taxonomy import get_all_subcategory_ids

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def valid_subcategory_id():
    """Get a valid subcategory ID for testing."""
    all_ids = get_all_subcategory_ids()
    for sub_id in all_ids:
        if sub_id.startswith("1."):
            return sub_id
    return "1.1"


@pytest.fixture
def sample_pipeline_config():
    """Create a sample PipelineConfig."""
    return PipelineConfig(
        source_name="test_source",
        source_type=SourceType.API,
        request_timeout=30,
        max_retries=3,
        batch_size=100,
        deduplicate=True,
        deduplication_strategy="exact",
    )


@pytest.fixture
def mock_adapter():
    """Create a mock adapter."""
    adapter = MagicMock(spec=BaseSourceAdapter)
    adapter.source_type = SourceType.API
    return adapter


@pytest.fixture
def sample_event(create_event, valid_subcategory_id):
    """Create a sample EventSchema for testing."""
    return create_event(
        title="Test Event",
        taxonomy_dimensions=[
            TaxonomyDimension(
                primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
                subcategory=valid_subcategory_id,
                confidence=0.8,
            )
        ],
    )


class ConcretePipeline(BasePipeline):
    """Concrete implementation of BasePipeline for testing."""

    def __init__(self, config, adapter, return_events=None, validate_result=None):
        super().__init__(config, adapter)
        self._return_events = return_events or []
        self._validate_result = validate_result or (True, [])

    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """Return raw event as-is for testing."""
        return raw_event

    def map_to_taxonomy(
        self, parsed_event: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Return default taxonomy mapping."""
        return "play_and_fun", []

    def normalize_to_schema(
        self,
        parsed_event: Dict[str, Any],
        primary_cat: str,
        taxonomy_dims: List[Dict[str, Any]],
    ) -> EventSchema:
        """Return pre-configured event."""
        if self._return_events:
            return self._return_events.pop(0)
        return EventSchema(
            event_id=str(uuid.uuid4()),
            title=parsed_event.get("title", "Test Event"),
            location=LocationInfo(city=parsed_event.get("city", "Test City")),
            start_datetime=datetime.now(timezone.utc) + timedelta(days=1),
            primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
            format=EventFormat.IN_PERSON,
            organizer=OrganizerInfo(name="Test Organizer"),
            source=SourceInfo(
                source_name="test",
                source_event_id="test-123",
                source_url="https://test.com/event",
                updated_at=datetime.now(timezone.utc),
            ),
        )

    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """Return configured validation result."""
        return self._validate_result

    def enrich_event(self, event: EventSchema) -> EventSchema:
        """Return event unchanged."""
        return event


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestPipelineStatus:
    """Tests for PipelineStatus enum."""

    def test_enum_values(self):
        """Should have all expected status values."""
        assert PipelineStatus.PENDING == "pending"
        assert PipelineStatus.RUNNING == "running"
        assert PipelineStatus.SUCCESS == "success"
        assert PipelineStatus.PARTIAL_SUCCESS == "partial_success"
        assert PipelineStatus.FAILED == "failed"

    def test_all_statuses_count(self):
        """Should have 5 status values."""
        assert len(PipelineStatus) == 5


class TestPipelineConfig:
    """Tests for PipelineConfig dataclass."""

    def test_config_defaults(self):
        """Should have sensible defaults."""
        config = PipelineConfig(source_name="test")
        assert config.source_type == SourceType.API
        assert config.request_timeout == 30
        assert config.max_retries == 3
        assert config.batch_size == 100
        assert config.rate_limit_per_second == 1.0
        assert config.deduplicate is True
        assert config.deduplication_strategy == "exact"
        assert config.custom_config == {}

    def test_config_custom_values(self):
        """Should accept custom values."""
        config = PipelineConfig(
            source_name="custom",
            source_type=SourceType.SCRAPER,
            request_timeout=60,
            max_retries=5,
            batch_size=50,
            rate_limit_per_second=0.5,
            deduplicate=False,
            deduplication_strategy="fuzzy",
            custom_config={"key": "value"},
        )
        assert config.source_name == "custom"
        assert config.source_type == SourceType.SCRAPER
        assert config.request_timeout == 60
        assert config.max_retries == 5
        assert config.batch_size == 50
        assert config.deduplicate is False
        assert config.custom_config == {"key": "value"}


class TestPipelineExecutionResult:
    """Tests for PipelineExecutionResult dataclass."""

    def test_result_creation(self):
        """Should create result with required fields."""
        now = datetime.utcnow()
        result = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="test_123",
            started_at=now,
            ended_at=now + timedelta(seconds=10),
        )
        assert result.status == PipelineStatus.SUCCESS
        assert result.source_name == "test"
        assert result.execution_id == "test_123"

    def test_duration_seconds(self):
        """Should calculate correct duration."""
        now = datetime.utcnow()
        result = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="test_123",
            started_at=now,
            ended_at=now + timedelta(seconds=30),
        )
        assert result.duration_seconds == 30.0

    def test_success_rate_with_events(self):
        """Should calculate correct success rate."""
        result = PipelineExecutionResult(
            status=PipelineStatus.PARTIAL_SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="test_123",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=100,
            successful_events=80,
            failed_events=20,
        )
        assert result.success_rate == 80.0

    def test_success_rate_zero_events(self):
        """Should return 0 for no events processed."""
        result = PipelineExecutionResult(
            status=PipelineStatus.FAILED,
            source_name="test",
            source_type=SourceType.API,
            execution_id="test_123",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=0,
        )
        assert result.success_rate == 0.0

    def test_default_lists(self):
        """Should default to empty lists."""
        result = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="test_123",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
        )
        assert result.events == []
        assert result.errors == []
        assert result.metadata == {}


class TestBasePipelineInit:
    """Tests for BasePipeline initialization."""

    def test_init_stores_config(self, sample_pipeline_config, mock_adapter):
        """Should store config and adapter."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        assert pipeline.config == sample_pipeline_config
        assert pipeline.adapter == mock_adapter

    def test_init_creates_logger(self, sample_pipeline_config, mock_adapter):
        """Should create logger with source name."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        assert pipeline.logger is not None
        assert "test_source" in pipeline.logger.name

    def test_source_type_property(self, sample_pipeline_config, mock_adapter):
        """Should return source type from adapter."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        assert pipeline.source_type == SourceType.API


class TestCalculateQualityScore:
    """Tests for _calculate_quality_score method."""

    def test_quality_all_key_fields(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should score 0.4 for key fields present."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        event = create_event(title="Test Event")
        score = pipeline._calculate_quality_score(event)
        # Has key fields (0.4), no enrichment, no taxonomy
        assert score >= 0.4

    def test_quality_missing_key_fields(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should score 0 for missing key fields."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        event = create_event(title="")  # Empty title
        score = pipeline._calculate_quality_score(event)
        assert score < 0.4

    def test_quality_with_enrichment(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should add bonus for enrichment fields."""
        from src.schemas.event import Coordinates

        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        event = create_event(
            title="Test Event",
            description="A great event",
            location=LocationInfo(
                city="Barcelona",
                venue_name="Test Venue",
                coordinates=Coordinates(latitude=41.38, longitude=2.17),
            ),
            end_datetime=datetime.utcnow() + timedelta(days=1, hours=3),
            image_url="https://example.com/image.jpg",
        )
        score = pipeline._calculate_quality_score(event)
        # Has key fields (0.4) + enrichment bonuses
        assert score > 0.5

    def test_quality_with_taxonomy_confidence(
        self, sample_pipeline_config, mock_adapter, create_event, valid_subcategory_id
    ):
        """Should add score for taxonomy confidence."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        event = create_event(
            title="Test Event",
            taxonomy_dimensions=[
                TaxonomyDimension(
                    primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
                    subcategory=valid_subcategory_id,
                    confidence=0.9,
                )
            ],
        )
        score = pipeline._calculate_quality_score(event)
        # Key fields (0.4) + taxonomy confidence (0.9 * 0.2 = 0.18)
        assert score >= 0.5

    def test_quality_penalizes_errors(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should penalize validation errors."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        event = create_event(
            title="Test Event",
            normalization_errors=[
                "Error 1",
                "Error 2",
                "Error 3",
                "Error 4",
                "Error 5",
            ],
        )
        score = pipeline._calculate_quality_score(event)
        # Penalty is capped at 0.1 (5 * 0.02 = 0.1)
        assert score <= 0.4

    def test_quality_bounded_0_to_1(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should always return score between 0 and 1."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        # Event with errors
        event = create_event(
            title="",
            location=LocationInfo(city="", venue_name=""),
            normalization_errors=["Error"] * 20,
        )
        score = pipeline._calculate_quality_score(event)
        assert 0.0 <= score <= 1.0


class TestExecute:
    """Tests for execute method."""

    def test_execute_success(self, sample_pipeline_config, mock_adapter, create_event):
        """Should return success status for successful execution."""
        fetch_result = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"title": "Event 1"}, {"title": "Event 2"}],
            total_fetched=2,
            metadata={},
        )
        mock_adapter.fetch.return_value = fetch_result

        events = [
            create_event(title="Event 1"),
            create_event(title="Event 2"),
        ]

        pipeline = ConcretePipeline(
            sample_pipeline_config, mock_adapter, return_events=events
        )
        result = pipeline.execute()

        assert result.status == PipelineStatus.SUCCESS
        assert result.total_events_processed == 2
        assert result.successful_events == 2

    def test_execute_fetch_failure(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should return failed status when fetch fails."""
        fetch_result = FetchResult(
            success=False,
            source_type=SourceType.API,
            raw_data=[],
            total_fetched=0,
            errors=["Connection failed"],
            metadata={},
        )
        mock_adapter.fetch.return_value = fetch_result

        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        result = pipeline.execute()

        assert result.status == PipelineStatus.FAILED
        assert len(result.errors) > 0
        assert "Connection failed" in result.errors[0]["error"]

    def test_execute_partial_success(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should return partial success when some events fail."""
        fetch_result = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"title": "Event 1"}, {"title": "Event 2"}],
            total_fetched=2,
            metadata={},
        )
        mock_adapter.fetch.return_value = fetch_result

        # Only one event will be processed successfully
        events = [create_event(title="Event 1")]

        # Create pipeline that will raise exception on second event
        pipeline = ConcretePipeline(
            sample_pipeline_config, mock_adapter, return_events=events
        )
        # Mock normalize_to_schema to fail on second call
        original_normalize = pipeline.normalize_to_schema
        call_count = [0]

        def mock_normalize(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise ValueError("Processing error")
            return original_normalize(*args, **kwargs)

        pipeline.normalize_to_schema = mock_normalize
        result = pipeline.execute()

        assert result.status == PipelineStatus.PARTIAL_SUCCESS
        assert result.successful_events < result.total_events_processed

    def test_execute_generates_execution_id(
        self, sample_pipeline_config, mock_adapter, sample_event
    ):
        """Should generate unique execution ID."""
        fetch_result = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"title": "Event 1"}],
            total_fetched=1,
            metadata={},
        )
        mock_adapter.fetch.return_value = fetch_result

        events = [sample_event]
        pipeline = ConcretePipeline(
            sample_pipeline_config, mock_adapter, return_events=events
        )
        result = pipeline.execute()

        assert result.execution_id is not None
        assert "test_source" in result.execution_id

    def test_execute_with_deduplication(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should deduplicate events when enabled."""
        fetch_result = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[
                {"title": "Event 1"},
                {"title": "Event 1"},  # Duplicate
                {"title": "Event 2"},
            ],
            total_fetched=3,
            metadata={},
        )
        mock_adapter.fetch.return_value = fetch_result

        base_time = datetime.utcnow() + timedelta(days=1)
        # All events have same title/venue so exact match will dedupe
        events = [
            create_event(
                title="Event 1",
                venue_name="Venue A",
                start_datetime=base_time,
            ),
            create_event(
                title="Event 1",
                venue_name="Venue A",
                start_datetime=base_time,
            ),
            create_event(
                title="Event 2",
                venue_name="Venue B",
                start_datetime=base_time,
            ),
        ]

        pipeline = ConcretePipeline(
            sample_pipeline_config, mock_adapter, return_events=events
        )
        result = pipeline.execute()

        # Should have 2 unique events after deduplication
        assert result.successful_events == 2

    def test_execute_without_deduplication(self, mock_adapter, create_event):
        """Should not deduplicate when disabled."""
        config = PipelineConfig(source_name="test", deduplicate=False)

        fetch_result = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"title": "Event 1"}, {"title": "Event 1"}],
            total_fetched=2,
            metadata={},
        )
        mock_adapter.fetch.return_value = fetch_result

        base_time = datetime.utcnow() + timedelta(days=1)
        events = [
            create_event(
                title="Event 1",
                venue_name="Venue A",
                start_datetime=base_time,
            ),
            create_event(
                title="Event 1",
                venue_name="Venue A",
                start_datetime=base_time,
            ),
        ]

        pipeline = ConcretePipeline(config, mock_adapter, return_events=events)
        result = pipeline.execute()

        # Should keep both duplicates
        assert result.successful_events == 2

    def test_execute_exception_handling(self, sample_pipeline_config, mock_adapter):
        """Should handle exceptions gracefully."""
        mock_adapter.fetch.side_effect = Exception("Unexpected error")

        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        result = pipeline.execute()

        assert result.status == PipelineStatus.FAILED
        assert len(result.errors) > 0
        assert "Unexpected error" in result.errors[0]["error"]


class TestProcessEventsBatch:
    """Tests for _process_events_batch method."""

    def test_process_batch_success(
        self, sample_pipeline_config, mock_adapter, sample_event
    ):
        """Should process all events in batch."""
        pipeline = ConcretePipeline(
            sample_pipeline_config,
            mock_adapter,
            return_events=[sample_event, sample_event],
        )

        raw_events = [{"title": "Event 1"}, {"title": "Event 2"}]
        result = pipeline._process_events_batch(raw_events)

        assert len(result) == 2

    def test_process_batch_continues_on_error(
        self, sample_pipeline_config, mock_adapter, sample_event
    ):
        """Should continue processing after individual event error."""
        pipeline = ConcretePipeline(
            sample_pipeline_config, mock_adapter, return_events=[sample_event]
        )

        # First event will raise exception (no more return_events)
        raw_events = [{"title": "Event 1"}, {"title": "Event 2"}]
        result = pipeline._process_events_batch(raw_events)

        # Only the first event succeeded before return_events ran out
        assert len(result) >= 1

    def test_process_batch_calculates_quality(
        self, sample_pipeline_config, mock_adapter, sample_event
    ):
        """Should calculate quality score for each event."""
        pipeline = ConcretePipeline(
            sample_pipeline_config, mock_adapter, return_events=[sample_event]
        )

        raw_events = [{"title": "Event 1"}]
        result = pipeline._process_events_batch(raw_events)

        assert len(result) == 1
        assert result[0].data_quality_score is not None
        assert 0.0 <= result[0].data_quality_score <= 1.0


class TestToDataFrame:
    """Tests for to_dataframe method."""

    def test_dataframe_columns(
        self, sample_pipeline_config, mock_adapter, sample_event
    ):
        """Should have all expected columns."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)

        df = pipeline.to_dataframe([sample_event])

        expected_columns = [
            "event_id",
            "title",
            "venue_name",
            "city",
            "start_datetime",
            "primary_category",
            "data_quality_score",
        ]
        for col in expected_columns:
            assert col in df.columns

    def test_dataframe_flattens_location(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should flatten location fields."""
        from src.schemas.event import Coordinates

        event = create_event(
            title="Test Event",
            location=LocationInfo(
                city="Barcelona",
                venue_name="Test Venue",
                street_address="123 Main St",
                coordinates=Coordinates(latitude=41.38, longitude=2.17),
            ),
        )

        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        df = pipeline.to_dataframe([event])

        assert df["city"].iloc[0] == "Barcelona"
        assert df["venue_name"].iloc[0] == "Test Venue"
        assert df["latitude"].iloc[0] == 41.38
        assert df["longitude"].iloc[0] == 2.17

    def test_dataframe_flattens_price(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should flatten price fields."""
        from src.schemas.event import PriceInfo
        from decimal import Decimal

        event = create_event(
            title="Test Event",
            price=PriceInfo(
                currency="EUR",
                minimum_price=Decimal("15.00"),
                maximum_price=Decimal("25.00"),
            ),
        )

        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        df = pipeline.to_dataframe([event])

        assert df["price_currency"].iloc[0] == "EUR"
        assert df["price_minimum"].iloc[0] == 15.00
        assert df["price_maximum"].iloc[0] == 25.00

    def test_dataframe_handles_empty_list(self, sample_pipeline_config, mock_adapter):
        """Should handle empty event list."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        df = pipeline.to_dataframe([])

        assert len(df) == 0

    def test_dataframe_handles_none_values(
        self, sample_pipeline_config, mock_adapter, create_event
    ):
        """Should handle None values gracefully."""
        event = create_event(title="Test Event")

        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        df = pipeline.to_dataframe([event])

        assert len(df) == 1
        # Verify the dataframe was created successfully
        assert df["title"].iloc[0] == "Test Event"


class TestClose:
    """Tests for close method."""

    def test_close_calls_adapter_close(self, sample_pipeline_config, mock_adapter):
        """Should call adapter close method."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        pipeline.close()

        mock_adapter.close.assert_called_once()

    def test_close_handles_none_adapter(self, sample_pipeline_config, mock_adapter):
        """Should handle None adapter gracefully."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)
        pipeline.adapter = None

        # Should not raise
        pipeline.close()


class TestGenerateExecutionId:
    """Tests for _generate_execution_id method."""

    def test_generates_unique_ids(self, sample_pipeline_config, mock_adapter):
        """Should generate unique execution IDs."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)

        id1 = pipeline._generate_execution_id()
        id2 = pipeline._generate_execution_id()

        assert id1 != id2

    def test_includes_source_name(self, sample_pipeline_config, mock_adapter):
        """Should include source name in ID."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)

        exec_id = pipeline._generate_execution_id()

        assert "test_source" in exec_id

    def test_includes_timestamp(self, sample_pipeline_config, mock_adapter):
        """Should include timestamp in ID."""
        pipeline = ConcretePipeline(sample_pipeline_config, mock_adapter)

        exec_id = pipeline._generate_execution_id()
        today = datetime.utcnow().strftime("%Y%m%d")

        assert today in exec_id
