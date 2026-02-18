"""
Agent registry — maps agent name → class for the orchestrator.

Used by BatchEnrichmentRunner to instantiate agents from agents.yaml config.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.agents.base.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Registry mapping agent config name → module + class path (lazy imports)
_AGENT_MAP: dict[str, str] = {
    "feature_alignment": "src.agents.enrichment.feature_alignment_agent.FeatureAlignmentAgent",
    "taxonomy_classifier": "src.agents.enrichment.taxonomy_classifier_agent.TaxonomyClassifierAgent",
    "emotion_mapper": "src.agents.enrichment.emotion_mapper_agent.EmotionMapperAgent",
    "data_quality": "src.agents.enrichment.data_quality_agent.DataQualityAgent",
    "deduplication": "src.agents.enrichment.deduplication_agent.DeduplicationAgent",
    "artist_enricher": "src.agents.enrichment.artist_enricher_agent.ArtistEnricherAgent",
}


class AgentRegistry:
    """
    Instantiates agents by name using agents.yaml config.

    Agents are created lazily on first request and reused.
    """

    def __init__(self):
        self._instances: dict[str, BaseAgent] = {}

    def get(self, agent_name: str, agent_config: dict[str, Any]) -> "BaseAgent":
        """
        Return an agent instance for the given name + config.

        Args:
            agent_name: Config key (e.g., "feature_alignment")
            agent_config: Agent config dict from agents.yaml

        Returns:
            Configured BaseAgent instance
        """
        if agent_name in self._instances:
            return self._instances[agent_name]

        class_path = _AGENT_MAP.get(agent_name)
        if not class_path:
            raise ValueError(f"Unknown agent: '{agent_name}'. Add it to AgentRegistry._AGENT_MAP")

        module_path, class_name = class_path.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        instance = cls(config=agent_config)
        self._instances[agent_name] = instance
        return instance

    def list_registered(self) -> list[str]:
        """Return all registered agent names."""
        return list(_AGENT_MAP.keys())
