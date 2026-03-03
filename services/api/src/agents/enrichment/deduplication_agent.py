"""
DeduplicationAgent — detects duplicates, groups recurring events, aligns cross-source events.

Two deduplication passes (applied in order):

  1. Rule-based exact match (fast, no LLM):
     Events sharing the same (title_slug, date, venue_slug) are immediately grouped.
     Group IDs are deterministic UUID5s derived from the match key.
     Catches the majority of duplicates without any LLM call.

  2. LLM fuzzy analysis (when Ollama is available):
     Remaining events are passed to the 'deduplication' prompt.
     Only groups with confidence >= 0.80 are accepted.
     Detects near-duplicates and recurring series.

Output written to event.custom_fields (consumed by the persistence layer to write to DB):
  duplicate_group_id   — UUID matching event_groups.duplicate_group_id (PK)
  group_type           — "duplicate" | "recurring" | "near_duplicate"
                         maps to event_groups.group_type
  is_primary           — True for the canonical event in each group
  duplicate_of         — source_event_id of the primary (non-primaries only)
  similarity_score     — confidence score (0–1), maps to event_groups.similarity_score
  reason               — short LLM explanation, maps to event_groups.reason

The persistence layer (not this agent) is responsible for:
  - Inserting rows into event_groups
  - Setting events.duplicate_group_id FK on all member events
"""

import json
import logging
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from src.agents.base.base_agent import BaseAgent
from src.agents.base.task import AgentResult, AgentTask

logger = logging.getLogger(__name__)


# =============================================================================
# Output models
# =============================================================================


class DuplicateGroup(BaseModel):
    """A group of events identified as duplicates or a recurring series."""

    group_id: str = Field(description="UUID string identifying this group")
    group_type: str = Field(description="duplicate | recurring | near_duplicate")
    primary_event_id: str = Field(description="source_event_id of the canonical event")
    member_event_ids: list[str] = Field(description="All event IDs in this group")
    confidence: float = Field(
        ge=0, le=1, description="Confidence this is a valid group"
    )
    reason: str = Field(description="Brief explanation")


class DeduplicationOutput(BaseModel):
    """Structured LLM output containing all detected duplicate groups."""

    groups: list[DuplicateGroup] = Field(default_factory=list)


# =============================================================================
# Agent
# =============================================================================


class DeduplicationAgent(BaseAgent):
    """
    Detects duplicate events, groups recurring series, and aligns cross-source events.

    Runs a two-pass analysis:
      Pass 1 — Rule-based exact matching (no LLM, always runs)
      Pass 2 — LLM fuzzy analysis on remaining candidates (when LLM is available)
    """

    name = "deduplication"
    prompt_name = "deduplication"  # rules_v1_llama3_threshold_0.8

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the DeduplicationAgent with optional config overrides."""
        self._config = config or {}
        self._min_confidence = self._config.get("min_confidence", 0.8)

        from src.agents.llm.provider_router import get_llm_client
        from src.agents.registry.prompt_registry import get_prompt_registry

        self._llm = get_llm_client(
            provider=self._config.get("provider", "ollama"),
            model_name=self._config.get("model", "llama3.2:3b"),
            temperature=0.0,  # always deterministic for deduplication
        )
        self._registry = get_prompt_registry()

    async def run(self, task: AgentTask) -> AgentResult:
        """Run deduplication on the task's event batch and return enriched results."""
        if not self._config.get("enabled", True):
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
                errors=["Agent disabled in config"],
            )

        if len(task.events) < 2:
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
            )

        start = time.monotonic()
        enriched_events = list(task.events)
        all_groups: list[DuplicateGroup] = []
        errors: list[str] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }

        # ------------------------------------------------------------------
        # Pass 1: Rule-based exact duplicate detection
        # ------------------------------------------------------------------
        exact_groups = self._detect_exact_duplicates(enriched_events)
        all_groups.extend(exact_groups)

        # Collect event IDs already grouped in pass 1
        already_grouped = {eid for g in exact_groups for eid in g.member_event_ids}

        # ------------------------------------------------------------------
        # Pass 2: LLM fuzzy analysis on remaining candidates
        # ------------------------------------------------------------------
        remaining = [
            e
            for e in enriched_events
            if str(e.source.source_event_id) not in already_grouped
        ]

        if len(remaining) >= 2 and self._llm.is_available:
            try:
                llm_groups, usage = await self._llm_deduplication(
                    remaining, task.prompt_version
                )
                all_groups.extend(
                    [g for g in llm_groups if g.confidence >= self._min_confidence]
                )
                for k in total_tokens:
                    total_tokens[k] += usage.get(k, 0)
            except Exception as e:
                msg = f"LLM deduplication pass failed: {e}"
                logger.warning(msg)
                errors.append(msg)

        # ------------------------------------------------------------------
        # Write group metadata back to events
        # ------------------------------------------------------------------
        enriched_events = self._apply_groups(enriched_events, all_groups)

        prompt_version = (
            self._registry.get_active_version(self.prompt_name)
            if self._llm.is_available
            else "rule-based"
        )

        return AgentResult(
            agent_name=self.name,
            prompt_name=self.prompt_name,
            prompt_version=prompt_version,
            events=enriched_events,
            token_usage=total_tokens,
            errors=errors,
            duration_seconds=time.monotonic() - start,
            confidence_scores={
                "groups_found": float(len(all_groups)),
                "exact_matches": float(len(exact_groups)),
            },
        )

    # -------------------------------------------------------------------------
    # Pass 1 — Rule-based exact matching
    # -------------------------------------------------------------------------

    def _detect_exact_duplicates(self, events: list) -> list[DuplicateGroup]:
        """
        Group events that share the same (title_slug, date_slug, venue_slug).
        No LLM needed — pure string normalization.
        """
        buckets: dict[str, list[str]] = {}

        for event in events:
            key = self._exact_key(event)
            event_id = str(event.source.source_event_id)
            buckets.setdefault(key, []).append(event_id)

        groups = []
        for key, event_ids in buckets.items():
            if len(event_ids) < 2:
                continue

            # Pick primary: prefer the event with more fields filled
            primary = self._pick_primary(events, event_ids)
            groups.append(
                DuplicateGroup(
                    group_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, key)),
                    group_type="duplicate",
                    primary_event_id=primary,
                    member_event_ids=event_ids,
                    confidence=1.0,
                    reason=f"Exact match on title + date + venue (key={key[:40]})",
                )
            )

        return groups

    def _exact_key(self, event) -> str:
        """Build a normalized key for exact duplicate detection."""
        title = _slugify(event.title or "")
        date = str(event.start_datetime)[:10] if event.start_datetime else ""
        venue = _slugify(event.location.venue_name or event.location.city or "")
        return f"{title}|{date}|{venue}"

    def _pick_primary(self, events: list, event_ids: list[str]) -> str:
        """Pick the most complete event as the primary in a group."""
        scored: list[tuple[int, str]] = []
        event_map = {str(e.source.source_event_id): e for e in events}

        for eid in event_ids:
            event = event_map.get(eid)
            if not event:
                continue
            score = sum(
                [
                    bool(event.description),
                    bool(event.media_assets),
                    bool(event.location.venue_name),
                    bool(event.price and event.price.min_price is not None),
                    bool(event.tags),
                    bool(event.taxonomy_dimension),
                    bool(event.organizer),
                ]
            )
            scored.append((score, eid))

        scored.sort(reverse=True)
        return scored[0][1] if scored else event_ids[0]

    # -------------------------------------------------------------------------
    # Pass 2 — LLM fuzzy deduplication
    # -------------------------------------------------------------------------

    async def _llm_deduplication(
        self,
        events: list,
        prompt_version: str,
    ) -> tuple[list[DuplicateGroup], dict[str, int]]:
        """Run LLM analysis on remaining events to find fuzzy duplicates and recurring series."""

        # Build compact event summaries for the prompt (keep token budget low)
        event_summaries = []
        for event in events:
            event_summaries.append(
                {
                    "source_event_id": str(event.source.source_event_id),
                    "title": event.title or "",
                    "start_datetime": (
                        str(event.start_datetime)[:16] if event.start_datetime else ""
                    ),
                    "venue_name": event.location.venue_name or "",
                    "city": event.location.city or "",
                    "organizer": event.organizer.name if event.organizer else "",
                    "source": str(event.source.source_name) if event.source else "",
                }
            )

        events_json = json.dumps(event_summaries, indent=2, ensure_ascii=False)
        # Cap to avoid blowing the context window
        if len(events_json) > 8000:
            events_json = events_json[:8000] + "\n... (truncated)"

        system_prompt, user_prompt = self._registry.render(
            self.prompt_name,
            version=prompt_version,
            variables={
                "event_count": len(events),
                "events_json": events_json,
            },
            agent_name=self.name,
        )

        result: DeduplicationOutput = await self._llm.complete_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=DeduplicationOutput,
            temperature=0.0,
        )
        usage = self._llm.get_token_usage()
        return result.groups, usage

    # -------------------------------------------------------------------------
    # Apply groups → write to event.custom_fields
    # -------------------------------------------------------------------------

    def _apply_groups(self, events: list, groups: list[DuplicateGroup]) -> list:
        """Write group metadata into each event's custom_fields."""
        # Build lookup: event_id → group
        id_to_group: dict[str, DuplicateGroup] = {}
        for group in groups:
            for eid in group.member_event_ids:
                id_to_group[eid] = group

        for event in events:
            event_id = str(event.source.source_event_id)
            group = id_to_group.get(event_id)  # type: ignore[assignment]
            if not group:
                continue

            if not event.custom_fields:
                event.custom_fields = {}

            is_primary = event_id == group.primary_event_id
            event.custom_fields["duplicate_group_id"] = group.group_id
            event.custom_fields["group_type"] = group.group_type
            event.custom_fields["is_primary"] = is_primary
            event.custom_fields["similarity_score"] = group.confidence
            event.custom_fields["reason"] = group.reason

            if not is_primary:
                event.custom_fields["duplicate_of"] = group.primary_event_id

        return events


# =============================================================================
# Helpers
# =============================================================================


def _slugify(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation, collapse spaces."""
    import re

    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text
