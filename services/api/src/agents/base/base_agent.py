"""
Abstract BaseAgent interface for all enrichment agents.

Every enrichment agent subclasses BaseAgent and implements run().
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generator

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

        loc = event.location
        if loc:
            if loc.venue_name:
                ctx["venue_name"] = loc.venue_name
            if loc.city:
                ctx["city"] = loc.city
            if loc.country_code:
                ctx["country_code"] = loc.country_code

        if event.artists:
            ctx["artists"] = [a.name for a in event.artists if a.name][:5]

        if event.price:
            if event.price.is_free:
                ctx["is_free"] = True
            elif event.price.price_raw_text:
                ctx["price_raw"] = event.price.price_raw_text

        if event.tags:
            ctx["existing_tags"] = event.tags[:10]
        if event.event_type:
            ctx["event_type"] = (
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            )
        if event.custom_fields:
            ctx["source_context"] = event.custom_fields

        return ctx

    def _build_batch_context(self, events: list["EventSchema"]) -> dict[str, Any]:
        """
        Build a compact JSON context for a chunk of events.

        Returns a dict with `events_json` (JSON string) and `event_count`
        suitable for rendering a batch_user_prompt template.

        Each event entry includes source_event_id as the match key plus the
        most enrichment-relevant fields.  Description is capped at 400 chars
        to keep token cost predictable.
        """
        items = []
        for event in events:
            loc = event.location
            item: dict[str, Any] = {
                "source_event_id": str(event.source.source_event_id),
                "title": event.title or "",
            }
            if event.description:
                item["description"] = event.description[:400]
            if loc:
                if loc.venue_name:
                    item["venue_name"] = loc.venue_name
                if loc.city:
                    item["city"] = loc.city
            if event.event_type:
                item["event_type"] = (
                    event.event_type.value
                    if hasattr(event.event_type, "value")
                    else str(event.event_type)
                )
            if event.artists:
                item["artists"] = [a.name for a in event.artists if a.name][:3]
            if event.price:
                if event.price.is_free:
                    item["price"] = "free"
                elif event.price.price_raw_text:
                    item["price"] = event.price.price_raw_text
            if event.tags:
                item["existing_tags"] = event.tags[:5]
            if event.start_datetime:
                item["start_datetime"] = str(event.start_datetime)[:16]
            if event.custom_fields:
                item["source_context"] = event.custom_fields
            items.append(item)

        return {
            "event_count": len(events),
            "events_json": json.dumps(items, ensure_ascii=False, indent=2),
        }

    @staticmethod
    def _chunk(lst: list, size: int) -> Generator[list, None, None]:
        """Yield successive non-overlapping chunks of `size` from `lst`."""
        for i in range(0, len(lst), size):
            yield lst[i : i + size]
