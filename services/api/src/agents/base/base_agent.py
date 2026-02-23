"""
Abstract BaseAgent interface for all enrichment agents.

Every enrichment agent subclasses BaseAgent and implements run().
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.event import EventSchema

from src.agents.base.task import AgentResult, AgentTask

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all Pulsecity enrichment agents.

    Subclasses must set:
        name        — unique identifier used in logs and configs
        prompt_name — key into PromptRegistry

    Subclasses must implement:
        run(task: AgentTask) -> AgentResult
    """

    name: str = "base_agent"
    prompt_name: str = ""

    @abstractmethod
    async def run(self, task: AgentTask) -> AgentResult:
        """
        Process a batch of events and return enriched results.

        Args:
            task: AgentTask containing events and configuration

        Returns:
            AgentResult with enriched events, confidence scores, token usage
        """
        ...

    def _build_event_context(self, event: "EventSchema") -> dict[str, Any]:
        """
        Build a serializable context dict from an EventSchema for prompt injection.

        Only includes fields that are useful for LLM enrichment.
        """
        ctx: dict[str, Any] = {}

        if event.title:
            ctx["title"] = event.title
        if event.description:
            ctx["description"] = event.description[:800]
        if event.venue_name:
            ctx["venue_name"] = event.venue_name
        if event.city:
            ctx["city"] = event.city
        if event.country_code:
            ctx["country_code"] = event.country_code
        if event.artists:
            ctx["artists"] = [a.name for a in event.artists if a.name][:5]
        if event.price and event.price.cost:
            ctx["price_raw"] = event.price.cost
        if event.price and event.price.is_free is not None:
            ctx["is_free"] = event.price.is_free
        if event.tags:
            ctx["existing_tags"] = event.tags[:10]
        if event.event_type:
            ctx["event_type"] = (
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            )

        return ctx
