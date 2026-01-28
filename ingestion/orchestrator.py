"""
Pipeline Orchestrator.

Coordinates execution, scheduling, and management of all event ingestion pipelines.
Handles pipeline registration, execution, scheduling, error handling, and result storage.
"""

from typing import Dict, List, Optional, Type
from datetime import datetime
import logging
from dataclasses import dataclass

from ingestion.base_pipeline import (
    BasePipeline,
    PipelineConfig,
    PipelineExecutionResult,
    PipelineStatus,
)


@dataclass
class ScheduledPipeline:
    """
    Configuration for a scheduled pipeline execution.
    """

    pipeline_name: str
    schedule_type: str  # 'interval', 'cron', 'once'
    interval_hours: Optional[int] = None
    cron_expression: Optional[str] = None
    enabled: bool = True
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None


class PipelineOrchestrator:
    """
    Coordinates all event ingestion pipelines.

    Responsibilities:
    - Register and manage pipeline instances
    - Execute pipelines on demand or on schedule
    - Track execution history and results
    - Handle errors and retries
    - Coordinate storage of ingested events
    """

    def __init__(self):
        """Initialize the orchestrator."""
        self.logger = logging.getLogger("orchestrator")
        self.logger.setLevel(logging.INFO)

        self.pipelines: Dict[str, BasePipeline] = {}
        self.scheduled_pipelines: Dict[str, ScheduledPipeline] = {}
        self.execution_history: List[PipelineExecutionResult] = []

    # ========================================================================
    # PIPELINE MANAGEMENT
    # ========================================================================

    def register_pipeline(
        self,
        source_name: str,
        pipeline_class: Type[BasePipeline],
        config: PipelineConfig,
    ) -> None:
        """
        Register a pipeline instance.

        Args:
            source_name: Unique identifier for the source (e.g., 'ra_co', 'meetup')
            pipeline_class: The BasePipeline subclass
            config: PipelineConfig instance for this source
        """
        try:
            pipeline_instance = pipeline_class(config)
            self.pipelines[source_name] = pipeline_instance
            self.logger.info(f"Registered pipeline: {source_name}")
        except Exception as e:
            self.logger.error(f"Failed to register pipeline {source_name}: {e}")
            raise

    def get_pipeline(self, source_name: str) -> Optional[BasePipeline]:
        """
        Get a registered pipeline by name.
        """
        return self.pipelines.get(source_name)

    def list_pipelines(self) -> List[str]:
        """
        List all registered pipelines.
        """
        return list(self.pipelines.keys())

    # ========================================================================
    # EXECUTION
    # ========================================================================

    def execute_pipeline(self, source_name: str, **kwargs) -> PipelineExecutionResult:
        """
        Execute a single pipeline on demand.

        Args:
            source_name: Name of the pipeline to execute
            **kwargs: Parameters to pass to the pipeline's execute() method

        Returns:
            PipelineExecutionResult with summary and events
        """
        pipeline = self.get_pipeline(source_name)
        if not pipeline:
            raise ValueError(f"Pipeline '{source_name}' not found")

        self.logger.info(f"Executing pipeline: {source_name}")

        try:
            result = pipeline.execute(**kwargs)
            self.execution_history.append(result)

            # Store results (in real implementation, save to database)
            self._store_execution_result(result)

            return result

        except Exception as e:
            self.logger.error(
                f"Pipeline execution failed: {source_name}", exc_info=True
            )
            raise

    def execute_all_pipelines(self, **kwargs) -> Dict[str, PipelineExecutionResult]:
        """
        Execute all registered pipelines.

        Args:
            **kwargs: Parameters passed to all pipelines

        Returns:
            Dictionary mapping source_name -> PipelineExecutionResult
        """
        results = {}

        for source_name in self.list_pipelines():
            try:
                result = self.execute_pipeline(source_name, **kwargs)
                results[source_name] = result
            except Exception as e:
                self.logger.error(f"Failed to execute {source_name}: {e}")
                # Continue with other pipelines

        return results

    # ========================================================================
    # SCHEDULING (Skeleton - integrate with APScheduler for production)
    # ========================================================================

    def schedule_pipeline(
        self, source_name: str, schedule_config: Dict
    ) -> ScheduledPipeline:
        """
        Schedule a pipeline for recurring execution.

        Args:
            source_name: Pipeline to schedule
            schedule_config: Dict with 'type' (interval/cron) and schedule parameters

        Returns:
            ScheduledPipeline configuration

        Example:
            orchestrator.schedule_pipeline('ra_co', {
                'type': 'interval',
                'interval_hours': 6
            })
        """
        pipeline = self.get_pipeline(source_name)
        if not pipeline:
            raise ValueError(f"Pipeline '{source_name}' not found")

        scheduled = ScheduledPipeline(
            pipeline_name=source_name,
            schedule_type=schedule_config.get("type"),
            interval_hours=schedule_config.get("interval_hours"),
            cron_expression=schedule_config.get("cron_expression"),
            enabled=schedule_config.get("enabled", True),
            next_execution=datetime.utcnow(),
        )

        self.scheduled_pipelines[source_name] = scheduled
        self.logger.info(f"Scheduled pipeline: {source_name}")

        # TODO: Integrate with APScheduler for actual scheduling
        # from apscheduler.schedulers.background import BackgroundScheduler
        # self.scheduler.add_job(...)

        return scheduled

    # ========================================================================
    # HISTORY & RESULTS
    # ========================================================================

    def get_execution_history(
        self, source_name: Optional[str] = None, limit: int = 10
    ) -> List[PipelineExecutionResult]:
        """
        Get execution history.

        Args:
            source_name: Filter by source (optional)
            limit: Maximum number of results

        Returns:
            List of execution results
        """
        results = self.execution_history

        if source_name:
            results = [r for r in results if r.source_name == source_name]

        return results[-limit:]

    def get_latest_execution(
        self, source_name: str
    ) -> Optional[PipelineExecutionResult]:
        """Get the latest execution result for a pipeline."""
        history = self.get_execution_history(source_name, limit=1)
        return history[0] if history else None

    def get_execution_stats(self, source_name: Optional[str] = None) -> Dict:
        """
        Get aggregate statistics about pipeline executions.

        Args:
            source_name: Optional filter by source

        Returns:
            Dictionary with stats (total runs, success rate, etc.)
        """
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
            "average_success_rate": (
                (total_successful / total_events * 100) if total_events > 0 else 0
            ),
            "latest_execution": results[-1].ended_at if results else None,
        }

    # ========================================================================
    # INTERNAL METHODS
    # ========================================================================

    def _store_execution_result(self, result: PipelineExecutionResult) -> None:
        """
        Store execution result to database.

        In a real implementation, this would:
        - Save execution metadata to a 'pipeline_runs' table
        - Save events to 'raw_events' table
        - Update pipeline statistics
        - Trigger downstream processing
        """
        self.logger.info(
            f"Storing {result.successful_events} events from {result.source_name} "
            f"(execution {result.execution_id})"
        )

        # TODO: Implement actual storage
        # db.session.add(PipelineRun(...))
        # db.session.bulk_insert_mappings(Event, result.events)
        # db.session.commit()


# ============================================================================
# FACTORY FUNCTION FOR EASY SETUP
# ============================================================================


def create_orchestrator_from_config(config_dict: Dict) -> PipelineOrchestrator:
    """
    Factory function to create and configure an orchestrator from config dict.

    Args:
        config_dict: Configuration dictionary (typically loaded from YAML)

    Returns:
        Configured PipelineOrchestrator instance

    Example:
        config = yaml.safe_load(open('configs/ingestion.yaml'))
        orchestrator = create_orchestrator_from_config(config)
    """
    from ingestion.sources.ra_co import RaCoEventPipeline
    from ingestion.sources.meetup import MeetupEventPipeline

    # from ingestion.sources.ticketmaster import TicketmasterEventPipeline

    orchestrator = PipelineOrchestrator()

    sources_config = config_dict.get("sources", {})

    for source_name, source_config in sources_config.items():
        if not source_config.get("enabled", True):
            continue

        # Create config
        pipeline_config = PipelineConfig(
            source_name=source_name,
            base_url=source_config.get("base_url"),
            api_key=source_config.get("api_key"),
            request_timeout=source_config.get("request_timeout", 30),
            max_retries=source_config.get("max_retries", 3),
            batch_size=source_config.get("batch_size", 100),
            rate_limit_per_second=source_config.get("rate_limit_per_second", 1.0),
            custom_config=source_config.get("custom", {}),
        )

        # Register appropriate pipeline class
        pipeline_class = None
        if source_name == "ra_co":
            pipeline_class = RaCoEventPipeline
        elif source_name == "meetup":
            pipeline_class = MeetupEventPipeline
        # elif source_name == 'ticketmaster':
        #     pipeline_class = TicketmasterEventPipeline

        if pipeline_class:
            orchestrator.register_pipeline(source_name, pipeline_class, pipeline_config)

            # Schedule if configured
            schedule_config = source_config.get("schedule")
            if schedule_config:
                orchestrator.schedule_pipeline(source_name, schedule_config)

    return orchestrator
