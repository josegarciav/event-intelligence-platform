"""
PostIngestionTrigger — called after pipeline.execute() completes.

Cleanly separates enrichment from ingestion. The trigger receives the
PipelineExecutionResult and kicks off BatchEnrichmentRunner on the events.

Usage in notebook:
    trigger = PostIngestionTrigger(agents_config)
    enrichment_result = await trigger.on_pipeline_complete(gyg_result, agents_config)
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.ingestion.pipelines.base_pipeline import PipelineExecutionResult

from src.agents.orchestration.agent_runner import (
    BatchEnrichmentRunner,
    EnrichmentRunResult,
)

logger = logging.getLogger(__name__)


class PostIngestionTrigger:
    """
    Triggers the enrichment pipeline after ingestion completes.

    Designed to be called post-execute() in notebooks and production pipelines.
    Agents skip gracefully if disabled or if no API key is present.
    """

    def __init__(self, agents_config: dict[str, Any] | None = None):
        """
        Args:
            agents_config: Full agents.yaml config dict (loaded via load_agents_config()).
                          If None, all agents run with defaults.
        """
        self._agents_config = agents_config or {}
        self._runner = BatchEnrichmentRunner(agents_config=self._agents_config)

    async def on_pipeline_complete(
        self,
        pipeline_result: "PipelineExecutionResult",
        prompt_version: str = "active",
    ) -> EnrichmentRunResult:
        """
        Run enrichment on all successfully ingested events.

        Args:
            pipeline_result: Result from BasePipeline.execute()
            prompt_version: "active" or explicit version string

        Returns:
            EnrichmentRunResult with enriched events and per-agent metadata
        """
        events = pipeline_result.events if hasattr(pipeline_result, "events") else []

        if not events:
            logger.info("PostIngestionTrigger: no events to enrich (empty pipeline result)")
            return EnrichmentRunResult(
                events=[],
                agent_results=[],
                total_duration_seconds=0.0,
            )

        source = getattr(pipeline_result, "source_name", "unknown")
        logger.info(f"PostIngestionTrigger: starting enrichment of {len(events)} events from '{source}'")

        result = await self._runner.run(events=events, prompt_version=prompt_version)

        logger.info(
            f"PostIngestionTrigger: enrichment complete — "
            f"{len(result.events)} events, "
            f"{result.total_token_usage.get('total', 0)} tokens, "
            f"{result.total_duration_seconds:.1f}s, "
            f"{result.total_errors} errors"
        )

        return result


def load_agents_config(config_path: str | None = None) -> dict[str, Any]:
    """
    Load agents.yaml config from disk.

    Args:
        config_path: Explicit path to agents.yaml. Defaults to
                     services/api/src/configs/agents.yaml relative to this file.

    Returns:
        Parsed config dict
    """
    from pathlib import Path

    import yaml

    if config_path is None:
        config_path = str(Path(__file__).parent.parent.parent / "configs" / "agents.yaml")

    try:
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"agents.yaml not found at {config_path}, using defaults")
        return {}
    except Exception as e:
        logger.error(f"Failed to load agents.yaml: {e}")
        return {}
