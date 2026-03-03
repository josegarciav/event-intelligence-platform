"""
TaxonomyClassifierAgent — classifies events into the Human Experience Taxonomy.

Two-pass RAG architecture:

  Pass 1 (batch LLM):
    Events → primary_category, subcategory, behavioral dimensions
    (energy_level, social_intensity, cognitive_load, physical_involvement,
     repeatability, unconstrained_* fields)

  Pass 2 (RAG activity selection, per subcategory group):
    For each resolved subcategory, activities are retrieved from the taxonomy
    JSON index and injected into a compact LLM prompt.  The LLM returns the
    best-matching activity_id + activity_name for each event in the group.
"""

import json
import logging
import time
from typing import Any

from src.agents.base.base_agent import BaseAgent
from src.agents.base.output_models import (
    ActivitySelectionBatch,
    TaxonomyAttributesExtractionBatch,
)
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry
from src.schemas.taxonomy import (
    find_best_activity_match,
    get_activities_for_subcategory,
    get_subcategory_by_id,
    resolve_primary_category,
    validate_subcategory_for_primary,
)

logger = logging.getLogger(__name__)


class TaxonomyClassifierAgent(BaseAgent):
    """
    Classifies events into the Pulsecity Human Experience Taxonomy.

    Pass 1: LLM batch → primary_category, subcategory, behavioral dimensions.
    Pass 2: RAG activity selection — activities for each resolved subcategory
            are retrieved from the taxonomy index and injected into the prompt
            so the LLM can pick the best activity_id per event.
    """

    name = "taxonomy_classifier"
    prompt_name = "taxonomy_classifier"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the TaxonomyClassifierAgent with optional config overrides."""
        self._config = config or {}
        self._llm = get_llm_client(
            provider=self._config.get("provider", "anthropic"),
            model_name=self._config.get("model", "claude-haiku-4-5-20251001"),
            temperature=self._config.get("temperature", 0.1),
        )
        self._registry = get_prompt_registry()

    async def run(self, task: AgentTask) -> AgentResult:
        """Run taxonomy classification on the task's event batch and return enriched results."""
        if not self._config.get("enabled", True):
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
                errors=["Agent disabled in config"],
            )

        if not self._llm.is_available:
            logger.warning(f"{self.name}: LLM unavailable, skipping")
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
                errors=["LLM not available — check API key"],
            )

        prompt_version = self._registry.get_active_version(self.prompt_name)
        batch_size = self._config.get("batch_size", 8)
        start = time.monotonic()
        errors: list[str] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }
        enriched_events = list(task.events)
        event_index = {
            str(e.source.source_event_id): i for i, e in enumerate(enriched_events)
        }

        # ------------------------------------------------------------------
        # Pass 1 — classify primary_category, subcategory + attributes
        # ------------------------------------------------------------------
        for chunk in self._chunk(enriched_events, batch_size):
            batch_ctx = self._build_batch_context(chunk)
            chunk_ids = [str(e.source.source_event_id) for e in chunk]
            try:
                system_prompt, user_prompt = self._registry.render(
                    self.prompt_name,
                    version=task.prompt_version,
                    variables=batch_ctx,
                    agent_name=self.name,
                    batch=True,
                )
                result: TaxonomyAttributesExtractionBatch = (
                    await self._llm.complete_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        output_schema=TaxonomyAttributesExtractionBatch,
                        temperature=self._config.get("temperature", 0.1),
                    )
                )

                for item in result.items:
                    sid = item.source_event_id
                    idx = event_index.get(sid)
                    if idx is None:
                        continue

                    tax = enriched_events[idx].taxonomy_dimension
                    if tax is None:
                        continue

                    # --- primary_category ---
                    if item.primary_category is not None:
                        resolved = resolve_primary_category(str(item.primary_category))
                        tax.primary_category = resolved

                    # --- subcategory (validate it belongs to the primary) ---
                    if item.subcategory:
                        primary_id = (
                            str(item.primary_category)
                            if item.primary_category is not None
                            else None
                        )
                        if primary_id and validate_subcategory_for_primary(
                            item.subcategory, primary_id
                        ):
                            try:
                                tax.subcategory = item.subcategory
                                sub = get_subcategory_by_id(item.subcategory)
                                if sub:
                                    tax.subcategory_name = sub.get("name")
                                    tax.values = sub.get("values", [])
                            except Exception:
                                pass  # invalid subcategory — leave as-is

                    # --- behavioral dimensions ---
                    if item.energy_level:
                        tax.energy_level = item.energy_level
                    if item.social_intensity:
                        tax.social_intensity = item.social_intensity
                    if item.cognitive_load:
                        tax.cognitive_load = item.cognitive_load
                    if item.physical_involvement:
                        tax.physical_involvement = item.physical_involvement
                    if item.repeatability:
                        tax.repeatability = item.repeatability

                    # --- unconstrained gap detection ---
                    tax.unconstrained_primary_category = (
                        item.unconstrained_primary_category
                    )
                    tax.unconstrained_subcategory = item.unconstrained_subcategory
                    tax.unconstrained_activity = item.unconstrained_activity

                    enriched_events[idx].taxonomy_dimension = tax

                usage = self._llm.get_token_usage()
                for k in total_tokens:
                    total_tokens[k] += usage.get(k, 0)

            except Exception as e:
                msg = f"batch {chunk_ids}: {e}"
                logger.warning(f"{self.name} pass-1 batch error: {msg}")
                errors.append(msg)

        # ------------------------------------------------------------------
        # Pass 2 — RAG activity selection grouped by subcategory
        # ------------------------------------------------------------------
        activity_errors = await self._run_activity_selection_pass(
            enriched_events, event_index, total_tokens
        )
        errors.extend(activity_errors)

        return AgentResult(
            agent_name=self.name,
            prompt_name=self.prompt_name,
            prompt_version=prompt_version,
            events=enriched_events,
            token_usage=total_tokens,
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )

    def _resolve_activity_by_name(
        self, name: str, activities: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Case-insensitive exact match of activity name against taxonomy activities list."""
        if not name:
            return None
        name_lower = name.lower().strip()
        for a in activities:
            if a.get("name", "").lower().strip() == name_lower:
                return a
        return None

    def _render_template(self, raw: str, variables: dict[str, Any]) -> str:
        """Render a Jinja2 template string with silent undefined handling."""
        try:
            from jinja2 import Template, Undefined

            class _Silent(Undefined):
                def __str__(self) -> str:
                    return f"[{self._undefined_name}]"

            return Template(raw, undefined=_Silent).render(**variables)
        except Exception:
            result = raw
            for k, v in variables.items():
                result = result.replace(f"{{{{ {k} }}}}", str(v))
            return result

    async def _run_activity_selection_pass(
        self,
        events: list,
        event_index: dict[str, int],
        total_tokens: dict[str, int],
    ) -> list[str]:
        """
        RAG second pass: inject taxonomy activity names per subcategory and ask
        the LLM to pick the best matching name for each event.

        After the LLM responds, activity_id is resolved automatically by
        looking up the canonical activity in the taxonomy index via an exact
        name match — the LLM never sees internal UUIDs.

        If the LLM returns a name that is not in the available list for the
        resolved subcategory, a retry call is made with a stricter prompt that
        lists only the exact valid names.  Events still unresolved after the
        retry fall through to a keyword-match fallback.

        Returns a list of error strings (empty on full success).
        """
        errors: list[str] = []

        # Load prompt templates from YAML
        resolved_version = self._registry.get_active_version(self.prompt_name)
        try:
            from pathlib import Path

            import yaml

            template_path = (
                Path(__file__).parent.parent
                / "prompts"
                / self.prompt_name
                / f"{resolved_version}.yaml"
            )
            with template_path.open() as f:
                template_data = yaml.safe_load(f)
            system_raw = template_data.get("activity_selection_system_prompt", "")
            user_raw = template_data.get("activity_selection_batch_prompt", "")
            retry_system_raw = template_data.get(
                "activity_selection_retry_system_prompt", ""
            )
            retry_user_raw = template_data.get("activity_selection_retry_prompt", "")
        except Exception as e:
            logger.warning(
                f"{self.name}: could not load activity selection prompt: {e}"
            )
            return [f"activity selection prompt load error: {e}"]

        batch_size = self._config.get("batch_size", 8)

        # Group events by subcategory
        subcat_groups: dict[str, list] = {}
        for event in events:
            tax = event.taxonomy_dimension
            if tax and tax.subcategory:
                subcat_groups.setdefault(tax.subcategory, []).append(event)

        for subcategory_id, group_events in subcat_groups.items():
            activities = get_activities_for_subcategory(subcategory_id)
            if not activities:
                logger.debug(
                    f"{self.name}: no activities found for subcategory {subcategory_id}"
                )
                continue

            sub = get_subcategory_by_id(subcategory_id)
            subcategory_name = sub["name"] if sub else subcategory_id

            # Build name-only list — keep UUIDs out of the LLM prompt entirely
            valid_names = [a["name"] for a in activities if a.get("name")]
            activity_names_json = json.dumps(valid_names, ensure_ascii=False, indent=2)

            # Chunk the subcategory group to avoid overwhelming small models
            for chunk in self._chunk(group_events, batch_size):
                event_items = []
                for ev in chunk:
                    stub: dict[str, Any] = {
                        "source_event_id": str(ev.source.source_event_id),
                        "title": ev.title or "",
                    }
                    if ev.description:
                        stub["description"] = ev.description[:200]
                    event_items.append(stub)

                variables = {
                    "subcategory_id": subcategory_id,
                    "subcategory_name": subcategory_name,
                    "activity_names_json": activity_names_json,
                    "events_json": json.dumps(
                        event_items, ensure_ascii=False, indent=2
                    ),
                    "event_count": len(chunk),
                }
                system_prompt = self._render_template(system_raw, variables)
                user_prompt = self._render_template(user_raw, variables)

                chunk_ids = [str(e.source.source_event_id) for e in chunk]
                # Events whose LLM-returned name had no taxonomy match → retry
                retry_events: list[tuple[int, dict[str, Any]]] = (
                    []
                )  # (global_idx, event_stub)

                try:
                    result: ActivitySelectionBatch = (
                        await self._llm.complete_structured(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            output_schema=ActivitySelectionBatch,
                            temperature=self._config.get("temperature", 0.1),
                        )
                    )

                    for item in result.items:
                        idx = event_index.get(item.source_event_id)
                        if idx is None or not item.activity_name:
                            continue
                        tax = events[idx].taxonomy_dimension
                        if not tax:
                            continue

                        matched = self._resolve_activity_by_name(
                            item.activity_name, activities
                        )
                        if matched:
                            tax.activity_id = matched["activity_id"]
                            tax.activity_name = matched["name"]
                            events[idx].taxonomy_dimension = tax
                        else:
                            # LLM returned a name not in the taxonomy list — schedule retry
                            logger.debug(
                                f"{self.name}: activity name '{item.activity_name}' not in "
                                f"taxonomy for subcategory {subcategory_id}; scheduling retry"
                            )
                            retry_events.append(
                                (
                                    idx,
                                    next(
                                        s
                                        for s in event_items
                                        if s["source_event_id"] == item.source_event_id
                                    ),
                                )
                            )

                    usage = self._llm.get_token_usage()
                    for k in total_tokens:
                        total_tokens[k] += usage.get(k, 0)

                except Exception as e:
                    msg = f"activity selection {subcategory_id} {chunk_ids}: {e}"
                    logger.warning(f"{self.name} pass-2 error: {msg}")
                    errors.append(msg)
                    continue

                # ----------------------------------------------------------
                # Retry pass — events whose name wasn't in the taxonomy list
                # ----------------------------------------------------------
                if retry_events and retry_user_raw:
                    retry_stubs = [stub for _, stub in retry_events]
                    retry_variables = {
                        **variables,
                        "events_json": json.dumps(
                            retry_stubs, ensure_ascii=False, indent=2
                        ),
                        "event_count": len(retry_stubs),
                    }
                    retry_system = self._render_template(
                        retry_system_raw, retry_variables
                    )
                    retry_user = self._render_template(retry_user_raw, retry_variables)
                    try:
                        retry_result: ActivitySelectionBatch = (
                            await self._llm.complete_structured(
                                system_prompt=retry_system,
                                user_prompt=retry_user,
                                output_schema=ActivitySelectionBatch,
                                temperature=0.0,  # greedy for constrained selection
                            )
                        )

                        for item in retry_result.items:
                            idx = event_index.get(item.source_event_id)
                            if idx is None or not item.activity_name:
                                continue
                            tax = events[idx].taxonomy_dimension
                            if not tax:
                                continue

                            matched = self._resolve_activity_by_name(
                                item.activity_name, activities
                            )
                            if matched:
                                tax.activity_id = matched["activity_id"]
                                tax.activity_name = matched["name"]
                                events[idx].taxonomy_dimension = tax
                            else:
                                logger.debug(
                                    f"{self.name}: retry still returned unmatched name "
                                    f"'{item.activity_name}' for {item.source_event_id}"
                                )

                        usage = self._llm.get_token_usage()
                        for k in total_tokens:
                            total_tokens[k] += usage.get(k, 0)

                    except Exception as e:
                        msg = f"activity selection retry {subcategory_id}: {e}"
                        logger.warning(f"{self.name} pass-2 retry error: {msg}")
                        errors.append(msg)

        # ------------------------------------------------------------------
        # Keyword fallback — events that have a subcategory but no activity_id
        # after both LLM passes (dropped by model or both passes failed).
        # ------------------------------------------------------------------
        for event in events:
            tax = event.taxonomy_dimension
            if not (tax and tax.subcategory and not tax.activity_id):
                continue
            event_context = f"{event.title or ''} {event.description or ''}"
            match = find_best_activity_match(
                event_context, tax.subcategory, threshold=0.3
            )
            if match:
                tax.activity_id = match["activity_id"]
                tax.activity_name = match.get("name")
                event.taxonomy_dimension = tax

        return errors
