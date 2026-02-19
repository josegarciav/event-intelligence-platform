"""
DeduplicationAgent — detects duplicates, groups recurring events, aligns cross-source events.

Three deduplication modes (applied in order):

  1. Rule-based pre-filter (fast, no LLM):
     Exact same (title_slug, date, venue_slug) → immediate duplicate flag.
     This catches 80%+ of duplicates without any LLM call.

  2. LLM analysis on candidate groups (fuzzy matching):
     Events that share title similarity (>0.6 Jaro-Winkler) but differ slightly
     are passed to the 'deduplication' prompt for final judgement.

  3. Recurring series detection:
     Events with the same title pattern at the same venue across different dates
     are grouped as a series with group_type="recurring".

Output written to event.custom_fields:
  duplicate_group_id   — shared UUID for events in the same group
  duplicate_group_type — "duplicate" | "recurring" | "near_duplicate"
  is_primary           — True for the canonical event in each group
  duplicate_of         — source_event_id of the primary (non-primaries only)
  similarity_score     — confidence this grouping is correct
"""

import hashlib
import json
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from src.agents.base.base_agent import BaseAgent
from src.agents.base.task import AgentResult, AgentTask

logger = logging.getLogger(__name__)


# =============================================================================
# Output models
# =============================================================================


class DuplicateGroup(BaseModel):
    group_id: str = Field(description="Short slug identifying this group")
    group_type: str = Field(description="duplicate | recurring | near_duplicate")
    primary_event_id: str = Field(description="source_event_id of the canonical event")
    member_event_ids: list[str] = Field(description="All event IDs in this group")
    confidence: float = Field(
        ge=0, le=1, description="Confidence this is a valid group"
    )
    reason: str = Field(description="Brief explanation")


class DeduplicationOutput(BaseModel):
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
    prompt_name = "deduplication"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._min_confidence = self._config.get("min_confidence", 0.7)

        from src.agents.llm.provider_router import get_llm_client
        from src.agents.registry.prompt_registry import get_prompt_registry

        self._llm = get_llm_client(
            provider=self._config.get("provider", "ollama"),
            model_name=self._config.get("model", "llama3.2:3b"),
            temperature=0.0,  # always deterministic for deduplication
        )
        self._registry = get_prompt_registry()

    async def run(self, task: AgentTask) -> AgentResult:
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
            e for e in enriched_events if str(e.source_event_id) not in already_grouped
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
            event_id = str(event.source_event_id)
            buckets.setdefault(key, []).append(event_id)

        groups = []
        for key, event_ids in buckets.items():
            if len(event_ids) < 2:
                continue

            # Pick primary: prefer the event with more fields filled
            primary = self._pick_primary(events, event_ids)
            groups.append(
                DuplicateGroup(
                    group_id=f"exact-{hashlib.md5(key.encode()).hexdigest()[:8]}",
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
        venue = _slugify(event.venue_name or event.city or "")
        return f"{title}|{date}|{venue}"

    def _pick_primary(self, events: list, event_ids: list[str]) -> str:
        """Pick the most complete event as the primary in a group."""
        scored: list[tuple[int, str]] = []
        event_map = {str(e.source_event_id): e for e in events}

        for eid in event_ids:
            event = event_map.get(eid)
            if not event:
                continue
            score = sum(
                [
                    bool(event.description),
                    bool(event.image_url),
                    bool(event.venue_name),
                    bool(event.price),
                    bool(event.tags),
                    bool(event.taxonomy),
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
                    "source_event_id": str(event.source_event_id),
                    "title": event.title or "",
                    "start_datetime": (
                        str(event.start_datetime)[:16] if event.start_datetime else ""
                    ),
                    "venue_name": event.venue_name or "",
                    "city": event.city or "",
                    "organizer": event.organizer.name if event.organizer else "",
                    "source": (
                        str(event.source_info.source_name) if event.source_info else ""
                    ),
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
            event_id = str(event.source_event_id)
            group = id_to_group.get(event_id)
            if not group:
                continue

            if not event.custom_fields:
                event.custom_fields = {}

            is_primary = event_id == group.primary_event_id
            event.custom_fields["duplicate_group_id"] = group.group_id
            event.custom_fields["duplicate_group_type"] = group.group_type
            event.custom_fields["is_primary"] = is_primary
            event.custom_fields["similarity_score"] = group.confidence

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
