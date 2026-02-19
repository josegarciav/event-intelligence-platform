"""
Unit tests for the orchestrator module.

Tests for PipelineOrchestrator pipeline management and execution.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from src.ingestion.adapters import SourceType
from src.ingestion.deduplication import ExactMatchDeduplicator
from src.ingestion.orchestrator import (
    PIPELINE_REGISTRY,
    PipelineOrchestrator,
    ScheduledPipeline,
    load_orchestrator_from_config,
    register_pipeline,
)
from src.ingestion.pipelines.base_pipeline import (
    BasePipeline,
    PipelineExecutionResult,
    PipelineStatus,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def orchestrator():
    """Create a fresh PipelineOrchestrator."""
    return PipelineOrchestrator()


@pytest.fixture
def mock_pipeline():
    """Create a mock pipeline."""
    pipeline = MagicMock(spec=BasePipeline)
    pipeline.source_type = SourceType.API
    return pipeline


@pytest.fixture
def sample_result():
    """Create a sample PipelineExecutionResult."""
    return PipelineExecutionResult(
        status=PipelineStatus.SUCCESS,
        source_name="test_source",
        source_type=SourceType.API,
        execution_id="test_123",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow() + timedelta(seconds=5),
        total_events_processed=10,
        successful_events=10,
        failed_events=0,
        events=[],
    )


@pytest.fixture
def sample_events(create_event):
    """Create sample events for testing."""
    return [create_event(title=f"Event {i}") for i in range(3)]


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestScheduledPipeline:
    """Tests for ScheduledPipeline dataclass."""

    def test_create_with_interval(self):
        """Should create scheduled pipeline with interval."""
        scheduled = ScheduledPipeline(
            pipeline_name="test",
            schedule_type="interval",
            interval_hours=6,
        )
        assert scheduled.pipeline_name == "test"
        assert scheduled.schedule_type == "interval"
        assert scheduled.interval_hours == 6

    def test_create_with_cron(self):
        """Should create scheduled pipeline with cron."""
        scheduled = ScheduledPipeline(
            pipeline_name="test",
            schedule_type="cron",
            cron_expression="0 */6 * * *",
        )
        assert scheduled.schedule_type == "cron"
        assert scheduled.cron_expression == "0 */6 * * *"

    def test_default_values(self):
        """Should have sensible defaults."""
        scheduled = ScheduledPipeline(
            pipeline_name="test",
            schedule_type="interval",
        )
        assert scheduled.enabled is True
        assert scheduled.last_execution is None
        assert scheduled.next_execution is None


class TestRegisterPipelineDecorator:
    """Tests for register_pipeline decorator."""

    def test_register_pipeline(self):
        """Should register pipeline factory."""
        # Clear registry for test
        original_registry = PIPELINE_REGISTRY.copy()
        PIPELINE_REGISTRY.clear()

        @register_pipeline("test_decorator")
        def create_test_pipeline(config):
            return MagicMock()

        assert "test_decorator" in PIPELINE_REGISTRY

        # Restore registry
        PIPELINE_REGISTRY.clear()
        PIPELINE_REGISTRY.update(original_registry)


class TestOrchestratorInit:
    """Tests for PipelineOrchestrator initialization."""

    def test_init_default_deduplicator(self):
        """Should create with default deduplicator."""
        orch = PipelineOrchestrator()
        assert isinstance(orch.deduplicator, ExactMatchDeduplicator)

    def test_init_custom_deduplicator(self):
        """Should accept custom deduplicator."""
        custom_dedup = MagicMock()
        orch = PipelineOrchestrator(deduplicator=custom_dedup)
        assert orch.deduplicator == custom_dedup

    def test_init_empty_pipelines(self):
        """Should start with empty pipeline dict."""
        orch = PipelineOrchestrator()
        assert orch.pipelines == {}

    def test_init_empty_history(self):
        """Should start with empty history."""
        orch = PipelineOrchestrator()
        assert orch.execution_history == []


class TestRegisterPipeline:
    """Tests for register_pipeline method."""

    def test_register_pipeline(self, orchestrator, mock_pipeline):
        """Should register pipeline."""
        orchestrator.register_pipeline("test", mock_pipeline)
        assert "test" in orchestrator.pipelines
        assert orchestrator.pipelines["test"] == mock_pipeline

    def test_register_multiple_pipelines(self, orchestrator):
        """Should register multiple pipelines."""
        pipe1 = MagicMock(spec=BasePipeline)
        pipe1.source_type = SourceType.API
        pipe2 = MagicMock(spec=BasePipeline)
        pipe2.source_type = SourceType.SCRAPER

        orchestrator.register_pipeline("api_pipe", pipe1)
        orchestrator.register_pipeline("scraper_pipe", pipe2)

        assert len(orchestrator.pipelines) == 2

    def test_register_overwrites(self, orchestrator, mock_pipeline):
        """Should overwrite existing pipeline with same name."""
        pipe1 = MagicMock(spec=BasePipeline)
        pipe1.source_type = SourceType.API
        pipe2 = MagicMock(spec=BasePipeline)
        pipe2.source_type = SourceType.API

        orchestrator.register_pipeline("test", pipe1)
        orchestrator.register_pipeline("test", pipe2)

        assert orchestrator.pipelines["test"] == pipe2


class TestGetPipeline:
    """Tests for get_pipeline method."""

    def test_get_existing(self, orchestrator, mock_pipeline):
        """Should return existing pipeline."""
        orchestrator.register_pipeline("test", mock_pipeline)
        result = orchestrator.get_pipeline("test")
        assert result == mock_pipeline

    def test_get_nonexistent(self, orchestrator):
        """Should return None for nonexistent pipeline."""
        result = orchestrator.get_pipeline("nonexistent")
        assert result is None


class TestListPipelines:
    """Tests for list_pipelines method."""

    def test_list_empty(self, orchestrator):
        """Should return empty list when no pipelines."""
        result = orchestrator.list_pipelines()
        assert result == []

    def test_list_with_pipelines(self, orchestrator):
        """Should list all registered pipelines."""
        pipe1 = MagicMock(spec=BasePipeline)
        pipe1.source_type = SourceType.API
        pipe2 = MagicMock(spec=BasePipeline)
        pipe2.source_type = SourceType.SCRAPER

        orchestrator.register_pipeline("api_pipe", pipe1)
        orchestrator.register_pipeline("scraper_pipe", pipe2)

        result = orchestrator.list_pipelines()

        assert len(result) == 2
        names = [p["name"] for p in result]
        assert "api_pipe" in names
        assert "scraper_pipe" in names

    def test_list_includes_type(self, orchestrator, mock_pipeline):
        """Should include pipeline type."""
        orchestrator.register_pipeline("test", mock_pipeline)
        result = orchestrator.list_pipelines()

        assert result[0]["type"] == "api"


class TestExecutePipeline:
    """Tests for execute_pipeline method."""

    def test_execute_success(self, orchestrator, mock_pipeline, sample_result):
        """Should execute pipeline and store result."""
        mock_pipeline.execute.return_value = sample_result
        orchestrator.register_pipeline("test", mock_pipeline)

        result = orchestrator.execute_pipeline("test")

        assert result == sample_result
        mock_pipeline.execute.assert_called_once()
        assert len(orchestrator.execution_history) == 1

    def test_execute_with_kwargs(self, orchestrator, mock_pipeline, sample_result):
        """Should pass kwargs to pipeline."""
        mock_pipeline.execute.return_value = sample_result
        orchestrator.register_pipeline("test", mock_pipeline)

        orchestrator.execute_pipeline("test", area_id=20, limit=50)

        mock_pipeline.execute.assert_called_with(area_id=20, limit=50)

    def test_execute_nonexistent_raises(self, orchestrator):
        """Should raise ValueError for nonexistent pipeline."""
        with pytest.raises(ValueError, match="not found"):
            orchestrator.execute_pipeline("nonexistent")

    def test_execute_propagates_error(self, orchestrator, mock_pipeline):
        """Should propagate pipeline execution errors."""
        mock_pipeline.execute.side_effect = Exception("Execution failed")
        orchestrator.register_pipeline("test", mock_pipeline)

        with pytest.raises(Exception, match="Execution failed"):
            orchestrator.execute_pipeline("test")


class TestExecuteAllPipelines:
    """Tests for execute_all_pipelines method."""

    def test_execute_all(self, orchestrator, sample_result):
        """Should execute all registered pipelines."""
        pipe1 = MagicMock(spec=BasePipeline)
        pipe1.source_type = SourceType.API
        pipe1.execute.return_value = sample_result

        pipe2 = MagicMock(spec=BasePipeline)
        pipe2.source_type = SourceType.API
        pipe2.execute.return_value = sample_result

        orchestrator.register_pipeline("pipe1", pipe1)
        orchestrator.register_pipeline("pipe2", pipe2)

        results = orchestrator.execute_all_pipelines()

        assert len(results) == 2
        assert "pipe1" in results
        assert "pipe2" in results

    def test_execute_all_continues_on_error(self, orchestrator, sample_result):
        """Should continue executing other pipelines on error."""
        pipe1 = MagicMock(spec=BasePipeline)
        pipe1.source_type = SourceType.API
        pipe1.execute.side_effect = Exception("Failed")

        pipe2 = MagicMock(spec=BasePipeline)
        pipe2.source_type = SourceType.API
        pipe2.execute.return_value = sample_result

        orchestrator.register_pipeline("pipe1", pipe1)
        orchestrator.register_pipeline("pipe2", pipe2)

        results = orchestrator.execute_all_pipelines()

        # pipe1 failed but pipe2 succeeded
        assert "pipe2" in results
        assert "pipe1" not in results

    def test_execute_all_empty(self, orchestrator):
        """Should return empty dict when no pipelines."""
        results = orchestrator.execute_all_pipelines()
        assert results == {}


class TestExecuteByType:
    """Tests for execute_by_type method."""

    def test_execute_api_only(self, orchestrator, sample_result):
        """Should execute only API pipelines."""
        api_pipe = MagicMock(spec=BasePipeline)
        api_pipe.source_type = SourceType.API
        api_pipe.execute.return_value = sample_result

        scraper_pipe = MagicMock(spec=BasePipeline)
        scraper_pipe.source_type = SourceType.SCRAPER

        orchestrator.register_pipeline("api", api_pipe)
        orchestrator.register_pipeline("scraper", scraper_pipe)

        results = orchestrator.execute_by_type(SourceType.API)

        assert "api" in results
        assert "scraper" not in results
        api_pipe.execute.assert_called_once()
        scraper_pipe.execute.assert_not_called()

    def test_execute_scraper_only(self, orchestrator, sample_result):
        """Should execute only scraper pipelines."""
        api_pipe = MagicMock(spec=BasePipeline)
        api_pipe.source_type = SourceType.API

        scraper_pipe = MagicMock(spec=BasePipeline)
        scraper_pipe.source_type = SourceType.SCRAPER
        scraper_pipe.execute.return_value = sample_result

        orchestrator.register_pipeline("api", api_pipe)
        orchestrator.register_pipeline("scraper", scraper_pipe)

        results = orchestrator.execute_by_type(SourceType.SCRAPER)

        assert "scraper" in results
        assert "api" not in results


class TestSchedulePipeline:
    """Tests for schedule_pipeline method."""

    def test_schedule_interval(self, orchestrator, mock_pipeline):
        """Should schedule pipeline with interval."""
        orchestrator.register_pipeline("test", mock_pipeline)

        scheduled = orchestrator.schedule_pipeline(
            "test",
            {"type": "interval", "interval_hours": 6},
        )

        assert scheduled.schedule_type == "interval"
        assert scheduled.interval_hours == 6
        assert "test" in orchestrator.scheduled_pipelines

    def test_schedule_cron(self, orchestrator, mock_pipeline):
        """Should schedule pipeline with cron."""
        orchestrator.register_pipeline("test", mock_pipeline)

        scheduled = orchestrator.schedule_pipeline(
            "test",
            {"type": "cron", "cron_expression": "0 */6 * * *"},
        )

        assert scheduled.schedule_type == "cron"
        assert scheduled.cron_expression == "0 */6 * * *"

    def test_schedule_nonexistent_raises(self, orchestrator):
        """Should raise ValueError for nonexistent pipeline."""
        with pytest.raises(ValueError, match="not found"):
            orchestrator.schedule_pipeline("nonexistent", {})

    def test_schedule_sets_next_execution(self, orchestrator, mock_pipeline):
        """Should set next_execution time."""
        orchestrator.register_pipeline("test", mock_pipeline)

        scheduled = orchestrator.schedule_pipeline("test", {"type": "interval"})

        assert scheduled.next_execution is not None


class TestDeduplicateResults:
    """Tests for deduplicate_results method."""

    def test_deduplicate_combines_events(self, orchestrator, sample_events):
        """Should combine events from multiple results."""
        result1 = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source1",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            events=sample_events[:2],
        )
        result2 = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source2",
            source_type=SourceType.API,
            execution_id="2",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            events=sample_events[2:],
        )

        results = {"source1": result1, "source2": result2}
        deduped = orchestrator.deduplicate_results(results)

        # All unique events should be present
        assert len(deduped) == 3

    def test_deduplicate_removes_duplicates(self, orchestrator, create_event):
        """Should remove duplicate events across sources."""
        base_time = datetime.utcnow() + timedelta(days=1)
        event = create_event(
            title="Same Event",
            venue_name="Venue",
            start_datetime=base_time,
        )

        result1 = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source1",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            events=[event],
        )
        result2 = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source2",
            source_type=SourceType.API,
            execution_id="2",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            events=[event],  # Same event
        )

        results = {"source1": result1, "source2": result2}
        deduped = orchestrator.deduplicate_results(results)

        # Duplicate should be removed
        assert len(deduped) == 1


class TestGetExecutionHistory:
    """Tests for get_execution_history method."""

    def test_get_all_history(self, orchestrator, sample_result):
        """Should return all history."""
        orchestrator.execution_history = [sample_result, sample_result]

        history = orchestrator.get_execution_history()

        assert len(history) == 2

    def test_get_history_filtered_by_source(self, orchestrator):
        """Should filter by source name."""
        result1 = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source1",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
        )
        result2 = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source2",
            source_type=SourceType.API,
            execution_id="2",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
        )

        orchestrator.execution_history = [result1, result2]

        history = orchestrator.get_execution_history(source_name="source1")

        assert len(history) == 1
        assert history[0].source_name == "source1"

    def test_get_history_respects_limit(self, orchestrator, sample_result):
        """Should respect limit parameter."""
        orchestrator.execution_history = [sample_result] * 20

        history = orchestrator.get_execution_history(limit=5)

        assert len(history) == 5

    def test_get_history_empty(self, orchestrator):
        """Should return empty list when no history."""
        history = orchestrator.get_execution_history()
        assert history == []


class TestGetExecutionStats:
    """Tests for get_execution_stats method."""

    def test_stats_no_executions(self, orchestrator):
        """Should return zero stats when no executions."""
        stats = orchestrator.get_execution_stats()
        assert stats["total_executions"] == 0

    def test_stats_all_success(self, orchestrator):
        """Should calculate stats for successful executions."""
        result = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=100,
            successful_events=100,
        )
        orchestrator.execution_history = [result, result]

        stats = orchestrator.get_execution_stats()

        assert stats["total_executions"] == 2
        assert stats["successful_executions"] == 2
        assert stats["success_rate"] == 100.0
        assert stats["total_events_processed"] == 200
        assert stats["total_successful_events"] == 200
        assert stats["average_events_per_run"] == 100.0

    def test_stats_partial_success(self, orchestrator):
        """Should calculate stats with partial success."""
        success = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=50,
            successful_events=50,
        )
        failure = PipelineExecutionResult(
            status=PipelineStatus.FAILED,
            source_name="test",
            source_type=SourceType.API,
            execution_id="2",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=50,
            successful_events=0,
        )
        orchestrator.execution_history = [success, failure]

        stats = orchestrator.get_execution_stats()

        assert stats["total_executions"] == 2
        assert stats["successful_executions"] == 1
        assert stats["success_rate"] == 50.0

    def test_stats_filtered_by_source(self, orchestrator):
        """Should filter stats by source."""
        result1 = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source1",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=100,
            successful_events=100,
        )
        result2 = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source2",
            source_type=SourceType.API,
            execution_id="2",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=50,
            successful_events=50,
        )
        orchestrator.execution_history = [result1, result2]

        stats = orchestrator.get_execution_stats(source_name="source1")

        assert stats["total_executions"] == 1
        assert stats["total_events_processed"] == 100


# =============================================================================
# TESTS: load_orchestrator_from_config
# =============================================================================


class TestLoadOrchestratorFromConfig:
    """Tests for the load_orchestrator_from_config factory function."""

    def test_loads_orchestrator_from_real_config(self):
        """Should create orchestrator from the real ingestion.yaml."""
        from src.ingestion.factory import DEFAULT_CONFIG_PATH

        orchestrator = load_orchestrator_from_config(str(DEFAULT_CONFIG_PATH))

        # Should have registered the enabled pipelines
        assert len(orchestrator.pipelines) >= 1
        assert "ra_co" in orchestrator.pipelines

    def test_excludes_disabled_pipelines(self):
        """Should not register disabled pipelines."""
        from src.ingestion.factory import DEFAULT_CONFIG_PATH

        orchestrator = load_orchestrator_from_config(str(DEFAULT_CONFIG_PATH))

        assert "ticketmaster" not in orchestrator.pipelines

    def test_schedules_enabled_pipelines(self):
        """Should schedule pipelines with enabled schedules."""
        import tempfile

        import yaml

        config = {
            "sources": {
                "test_src": {
                    "enabled": True,
                    "pipeline_type": "api",
                    "connection": {
                        "endpoint": "https://api.example.com",
                        "protocol": "rest",
                    },
                    "schedule": {
                        "type": "cron",
                        "cron_expression": "0 */6 * * *",
                        "enabled": True,
                    },
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        orchestrator = load_orchestrator_from_config(config_path)

        assert "test_src" in orchestrator.scheduled_pipelines
        scheduled = orchestrator.scheduled_pipelines["test_src"]
        assert scheduled.schedule_type == "cron"

    def test_does_not_schedule_disabled_schedules(self):
        """Pipelines with schedule.enabled=false should not be scheduled."""
        from src.ingestion.factory import DEFAULT_CONFIG_PATH

        orchestrator = load_orchestrator_from_config(str(DEFAULT_CONFIG_PATH))

        # ra_co has schedule.enabled: false in the real config
        assert "ra_co" not in orchestrator.scheduled_pipelines


# =============================================================================
# TESTS: run_full_ingestion
# =============================================================================


class TestRunFullIngestion:
    """Tests for the run_full_ingestion end-to-end method."""

    def test_run_full_ingestion_with_no_events(self, orchestrator):
        """Should handle case where pipelines return no events."""
        pipe = MagicMock(spec=BasePipeline)
        pipe.source_type = SourceType.API
        pipe.execute.return_value = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=0,
            events=[],
        )
        orchestrator.register_pipeline("test", pipe)

        stats = orchestrator.run_full_ingestion()

        assert stats["total_raw_fetched"] == 0
        assert stats["total_unique_found"] == 0
        assert stats["total_saved_to_db"] == 0

    def test_run_full_ingestion_with_events(self, orchestrator, create_event):
        """Should execute, deduplicate, and persist events."""
        events = [create_event(title=f"Event {i}") for i in range(5)]

        pipe = MagicMock(spec=BasePipeline)
        pipe.source_type = SourceType.API
        pipe.execute.return_value = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=5,
            successful_events=5,
            events=events,
        )
        orchestrator.register_pipeline("test", pipe)

        # Mock database persistence
        with (
            patch("src.ingestion.orchestrator.get_connection"),
            patch("src.ingestion.orchestrator.EventDataWriter") as mock_writer,
        ):
            mock_writer_instance = MagicMock()
            mock_writer_instance.persist_batch.return_value = 5
            mock_writer.return_value = mock_writer_instance

            stats = orchestrator.run_full_ingestion()

        assert stats["total_raw_fetched"] == 5
        assert stats["total_unique_found"] == 5
        assert stats["total_saved_to_db"] == 5
        assert "test" in stats["pipelines_executed"]

    def test_run_full_ingestion_deduplicates_across_sources(
        self, orchestrator, create_event
    ):
        """Should deduplicate events across multiple sources."""
        base_time = datetime.utcnow() + timedelta(days=1)
        shared_event = create_event(
            title="Shared Event",
            venue_name="Same Venue",
            start_datetime=base_time,
        )
        unique_event = create_event(
            title="Unique Event",
            venue_name="Other Venue",
            start_datetime=base_time,
        )

        # Two pipelines returning overlapping events
        pipe1 = MagicMock(spec=BasePipeline)
        pipe1.source_type = SourceType.API
        pipe1.execute.return_value = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source1",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=2,
            events=[shared_event, unique_event],
        )

        pipe2 = MagicMock(spec=BasePipeline)
        pipe2.source_type = SourceType.API
        pipe2.execute.return_value = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="source2",
            source_type=SourceType.API,
            execution_id="2",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=1,
            events=[shared_event],  # duplicate
        )

        orchestrator.register_pipeline("source1", pipe1)
        orchestrator.register_pipeline("source2", pipe2)

        with (
            patch("src.ingestion.orchestrator.get_connection"),
            patch("src.ingestion.orchestrator.EventDataWriter") as mock_writer,
        ):
            mock_writer_instance = MagicMock()
            mock_writer_instance.persist_batch.return_value = 2
            mock_writer.return_value = mock_writer_instance

            stats = orchestrator.run_full_ingestion()

        assert stats["total_raw_fetched"] == 3
        assert stats["total_unique_found"] == 2  # deduplicated
        assert stats["total_saved_to_db"] == 2
        assert len(stats["pipelines_executed"]) == 2

    def test_run_full_ingestion_handles_persistence_error(
        self, orchestrator, create_event
    ):
        """Should handle persistence errors gracefully."""
        events = [create_event(title="Test Event")]

        pipe = MagicMock(spec=BasePipeline)
        pipe.source_type = SourceType.API
        pipe.execute.return_value = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            total_events_processed=1,
            events=events,
        )
        orchestrator.register_pipeline("test", pipe)

        # Simulate database connection failure
        with patch("src.ingestion.orchestrator.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("DB connection failed")

            stats = orchestrator.run_full_ingestion()

        # Should still return stats even if persistence failed
        assert stats["total_raw_fetched"] == 1
        assert stats["total_unique_found"] == 1
        assert stats["total_saved_to_db"] == 0

    def test_run_full_ingestion_returns_timing(self, orchestrator):
        """Should include timing information in stats."""
        pipe = MagicMock(spec=BasePipeline)
        pipe.source_type = SourceType.API
        pipe.execute.return_value = PipelineExecutionResult(
            status=PipelineStatus.SUCCESS,
            source_name="test",
            source_type=SourceType.API,
            execution_id="1",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            events=[],
        )
        orchestrator.register_pipeline("test", pipe)

        stats = orchestrator.run_full_ingestion()

        assert "timestamp" in stats
        assert "duration_seconds" in stats
        assert stats["duration_seconds"] >= 0
