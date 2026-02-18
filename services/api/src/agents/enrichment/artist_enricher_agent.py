"""
ArtistEnricherAgent — STUB.

Requires an external artist metadata API (e.g., MusicBrainz, Spotify).
Currently disabled in agents.yaml (enabled: false).

# TODO: Implement when artist metadata API is integrated.
"""

import logging
from typing import Any

from src.agents.base.base_agent import BaseAgent
from src.agents.base.task import AgentResult, AgentTask

logger = logging.getLogger(__name__)


class ArtistEnricherAgent(BaseAgent):
    """
    STUB — enriches artist metadata for music events.

    Links artists to genres, popularity, and audio embeddings (future).
    Requires external artist metadata API — not yet integrated.
    """

    name = "artist_enricher"
    prompt_name = "artist_enrichment"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}

    async def run(self, task: AgentTask) -> AgentResult:
        logger.info(f"{self.name}: STUB — artist enrichment not yet implemented")
        return AgentResult(
            agent_name=self.name,
            prompt_name=self.prompt_name,
            prompt_version="stub",
            events=task.events,
            errors=["ArtistEnricherAgent is a stub — requires external artist metadata API"],
        )
