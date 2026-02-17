"""
Pipeline Orchestrator.

Coordinates execution, scheduling, persistence, and management of all event ingestion pipelines.
Supports both API and scraper-based sources through the adapter pattern.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.ingestion.adapters import SourceType
from src.ingestion.base_pipeline import (
    BasePipeline,
    PipelineConfig,
    PipelineExecutionResult,
    PipelineStatus,
)
from src.ingestion.deduplication import EventDeduplicator, ExactMatchDeduplicator
from src.ingestion.persist import EventDataWriter
from src.ingestion.taxonomy_loader import get_connection
from src.schemas.event import EventSchema

logger = logging.getLogger(__name__)


@dataclass
class ScheduledPipeline:
    """Configuration for a scheduled pipeline execution."""

    pipeline_name: str
    schedule_type: str  # 'interval', 'cron', 'manual'
    interval_hours: int | None = None
    cron_expression: str | None = None
    enabled: bool = True
    last_execution: datetime | None = None
    next_execution: datetime | None = None


# Pipeline registry - maps source names to pipeline factory functions
PipelineFactory = Callable[[PipelineConfig], BasePipeline]
PIPELINE_REGISTRY: dict[str, PipelineFactory] = {}


def register_pipeline(source_name: str):
    """
    Decorate a function to register it as a pipeline factory.

    Usage:
        @register_pipeline("ra_co")
        def create_ra_co_pipeline(config: PipelineConfig) -> RaCoPipeline:
            return RaCoPipeline(config)
    """

    def decorator(factory: PipelineFactory) -> PipelineFactory:
        PIPELINE_REGISTRY[source_name] = factory
        return factory

    return decorator


class PipelineOrchestrator:
    """
    Coordinates all event ingestion pipelines.

    Responsibilities:
    - Register and manage pipeline instances
    - Execute pipelines on demand or on schedule
    - Track execution history and results
    - Handle errors and retries
    - Coordinate deduplication across sources
    """

    def __init__(self, deduplicator: EventDeduplicator | None = None):
        """Initialize the orchestrator."""
        self.logger = logging.getLogger("orchestrator")
        self.pipelines: dict[str, BasePipeline] = {}
        self.scheduled_pipelines: dict[str, ScheduledPipeline] = {}
        self.execution_history: list[PipelineExecutionResult] = []
        self.deduplicator = deduplicator or ExactMatchDeduplicator()

    # ========================================================================
    # PIPELINE MANAGEMENT
    # ========================================================================

    def register_pipeline(
        self,
        source_name: str,
        pipeline: BasePipeline,
    ) -> None:
        """
        Register a pipeline instance.

        Args:
            source_name: Unique identifier for the source
            pipeline: Configured BasePipeline instance
        """
        self.pipelines[source_name] = pipeline
        self.logger.info(f"Registered pipeline: {source_name} (type: {pipeline.source_type.value})")

    def get_pipeline(self, source_name: str) -> BasePipeline | None:
        """Get a registered pipeline by name."""
        return self.pipelines.get(source_name)

    def list_pipelines(self) -> list[dict[str, str]]:
        """List all registered pipelines with their types."""
        return [{"name": name, "type": p.source_type.value} for name, p in self.pipelines.items()]

    def deduplicate_results(self, results: dict[str, PipelineExecutionResult]) -> list[EventSchema]:
        """Deduplicate events from multiple pipeline results."""
        all_events = []
        for result in results.values():
            all_events.extend(result.events)
        return self.deduplicator.deduplicate(all_events)

    # ========================================================================
    # EXECUTION
    # ========================================================================

    async def execute_pipeline(self, source_name: str, **kwargs) -> PipelineExecutionResult:
        """
        Execute a single pipeline.

        Args:
            source_name: Name of the pipeline to execute
            **kwargs: Parameters passed to pipeline.execute()

        Returns:
            PipelineExecutionResult
        """
        pipeline = self.get_pipeline(source_name)
        if not pipeline:
            raise ValueError(f"Pipeline '{source_name}' not found")

        self.logger.info(f"Executing pipeline: {source_name}")

        try:
            result = await pipeline.execute(**kwargs)
            self.execution_history.append(result)
            self._store_execution_result(result)
            return result

        except Exception:
            self.logger.error(f"Pipeline execution failed: {source_name}", exc_info=True)
            raise

    async def execute_all_pipelines(self, **kwargs) -> dict[str, PipelineExecutionResult]:
        """
        Execute all registered pipelines sequentially.

        Returns:
            Dictionary mapping source_name -> PipelineExecutionResult
        """
        results = {}

        for source_name in self.pipelines:
            try:
                result = await self.execute_pipeline(source_name, **kwargs)
                results[source_name] = result
            except Exception as e:
                self.logger.error(f"Failed to execute {source_name}: {e}")

        return results

    async def execute_by_type(self, source_type: SourceType, **kwargs) -> dict[str, PipelineExecutionResult]:
        """
        Execute all pipelines of a specific type (API or scraper).

        Args:
            source_type: SourceType.API or SourceType.SCRAPER
            **kwargs: Parameters passed to pipelines

        Returns:
            Dictionary mapping source_name -> PipelineExecutionResult
        """
        results = {}

        for name, pipeline in self.pipelines.items():
            if pipeline.source_type == source_type:
                try:
                    result = await self.execute_pipeline(name, **kwargs)
                    results[name] = result
                except Exception as e:
                    self.logger.error(f"Failed to execute {name}: {e}")

        return results

    # ========================================================================
    # SCHEDULING
    # ========================================================================

    def schedule_pipeline(self, source_name: str, schedule_config: dict) -> ScheduledPipeline:
        """
        Schedule a pipeline for recurring execution.

        Args:
            source_name: Pipeline to schedule
            schedule_config: Dict with schedule parameters
        """
        pipeline = self.get_pipeline(source_name)
        if not pipeline:
            raise ValueError(f"Pipeline '{source_name}' not found")

        scheduled = ScheduledPipeline(
            pipeline_name=source_name,
            schedule_type=schedule_config.get("type", "interval"),
            interval_hours=schedule_config.get("interval_hours"),
            cron_expression=schedule_config.get("cron_expression"),
            enabled=schedule_config.get("enabled", True),
            next_execution=datetime.now(UTC),
        )

        self.scheduled_pipelines[source_name] = scheduled
        self.logger.info(f"Scheduled pipeline: {source_name}")

        return scheduled

    # ========================================================================
    # HISTORY & STATS
    # ========================================================================

    def get_execution_history(self, source_name: str | None = None, limit: int = 10) -> list[PipelineExecutionResult]:
        """Get execution history, optionally filtered by source."""
        results = self.execution_history

        if source_name:
            results = [r for r in results if r.source_name == source_name]

        return results[-limit:]

    def get_execution_stats(self, source_name: str | None = None) -> dict:
        """Get aggregate statistics about pipeline executions."""
        results = self.execution_history
        if source_name:
            results = [r for r in results if r.source_name == source_name]

        if not results:
            return {"total_executions": 0}

        successful = sum(1 for r in results if r.status == PipelineStatus.SUCCESS)
        total_events = sum(r.total_events_processed for r in results)
        total_successful = sum(r.successful_events for r in results)

        return {
            "total_executions": len(results),
            "successful_executions": successful,
            "success_rate": (successful / len(results) * 100) if results else 0,
            "total_events_processed": total_events,
            "total_successful_events": total_successful,
            "average_events_per_run": total_events / len(results) if results else 0,
        }

    def _store_execution_result(self, result: PipelineExecutionResult) -> None:
        """Store execution result (placeholder for database storage)."""
        self.logger.info(f"Storing {result.successful_events} events from {result.source_name}")

    # ========================================================================
    # END-TO-END EXECUTION & PERSISTENCE
    # ========================================================================
    async def run_full_ingestion(self, **kwargs) -> dict[str, Any]:
        """
        Execute all registered pipelines, deduplicate, and persist.

        Returns:
            Dict containing stats about the ingestion run.
        """
        self.logger.info("Starting full ingestion run...")
        start_time = datetime.now(UTC)

        # 1. Execute all pipelines
        pipeline_results = await self.execute_all_pipelines(**kwargs)

        # 2. Extract and Deduplicate
        unique_events = self.deduplicate_results(pipeline_results)
        total_raw_events = sum(r.total_events_processed for r in pipeline_results.values())

        self.logger.info(
            f"Deduplication complete: {len(unique_events)} unique events found from {total_raw_events} raw results."
        )

        # 3. Persist to Database (sync psycopg2, run in thread)
        saved_count = 0
        if unique_events:
            try:

                def _persist():
                    conn = get_connection()
                    writer = EventDataWriter(conn)
                    count = writer.persist_batch(unique_events)
                    conn.close()
                    return count

                self.logger.info(f"Persisting {len(unique_events)} events to Postgres...")
                saved_count = await asyncio.to_thread(_persist)
                self.logger.info(f"Successfully saved {saved_count} events.")
            except Exception as e:
                self.logger.error(f"Critical error during persistence: {e}")
        else:
            self.logger.warning("No unique events found to persist.")

        duration = (datetime.now(UTC) - start_time).total_seconds()

        return {
            "timestamp": start_time.isoformat(),
            "duration_seconds": duration,
            "total_raw_fetched": total_raw_events,
            "total_unique_found": len(unique_events),
            "total_saved_to_db": saved_count,
            "pipelines_executed": list(pipeline_results.keys()),
        }


def load_orchestrator_from_config(config_path: str) -> PipelineOrchestrator:
    """
    Create an orchestrator from YAML config.

    Uses PipelineFactory to create all enabled pipelines from configuration.
    No hardcoded source names — fully config-driven.

    Args:
        config_path: Path to ingestion.yaml

    Returns:
        Configured PipelineOrchestrator
    """
    from src.ingestion.factory import PipelineFactory

    factory = PipelineFactory(config_path)
    orchestrator = PipelineOrchestrator()

    pipelines = factory.create_all_enabled_pipelines()
    for source_name, pipeline in pipelines.items():
        orchestrator.register_pipeline(source_name, pipeline)

        # Schedule if configured
        source_config = factory.get_source_config(source_name) or {}
        schedule_config = source_config.get("schedule")
        if schedule_config and schedule_config.get("enabled", True):
            orchestrator.schedule_pipeline(source_name, schedule_config)

    return orchestrator
