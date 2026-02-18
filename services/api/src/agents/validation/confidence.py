"""
Confidence scoring for enrichment outputs.

Computes per-field and overall confidence scores for EventSchema enrichment.
Events below the threshold (agents.yaml: global.confidence_threshold) are
flagged for human review.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.event import EventSchema

# Fields that contribute to enrichment confidence
_ENRICHMENT_FIELDS = [
    "event_type",
    "tags",
    "event_format",
]

_TAXONOMY_FIELDS = [
    "primary_category",
    "subcategory",
    "energy_level",
    "social_intensity",
    "cognitive_load",
    "physical_involvement",
    "environment",
    "emotional_output",
    "cost_level",
    "time_scale",
    "risk_level",
    "age_accessibility",
    "repeatability",
]


def compute_confidence_score(
    event: "EventSchema",
    agent_scores: dict[str, float] | None = None,
) -> float:
    """
    Compute an overall confidence score for an enriched event.

    Combines:
    - Field completeness (60% weight): how many enrichment fields are populated
    - Agent-reported scores (40% weight): confidence from agent results

    Args:
        event: The enriched EventSchema
        agent_scores: Optional per-agent confidence scores from AgentResult

    Returns:
        Confidence score in [0.0, 1.0]
    """
    event_dict = event.model_dump()

    # Completeness score from event-level fields
    filled = sum(1 for f in _ENRICHMENT_FIELDS if event_dict.get(f))
    completeness_score = filled / len(_ENRICHMENT_FIELDS)

    # Taxonomy field completeness
    if event.taxonomy:
        tax_dict: dict[str, Any] = event.taxonomy.model_dump()
        tax_filled = sum(1 for f in _TAXONOMY_FIELDS if tax_dict.get(f))
        taxonomy_completeness = tax_filled / len(_TAXONOMY_FIELDS)
    else:
        taxonomy_completeness = 0.0

    field_score = (completeness_score + taxonomy_completeness) / 2.0

    # Agent-reported confidence (if available)
    if agent_scores:
        avg_agent_score = sum(agent_scores.values()) / len(agent_scores)
    else:
        avg_agent_score = field_score  # fallback to field score if no agent scores

    overall = 0.6 * field_score + 0.4 * avg_agent_score
    return round(overall, 4)


def flag_low_confidence(
    events: list["EventSchema"],
    threshold: float = 0.6,
    agent_scores: dict[str, dict[str, float]] | None = None,
) -> list[tuple["EventSchema", float]]:
    """
    Return events below the confidence threshold for human review.

    Args:
        events: List of enriched events
        threshold: Minimum confidence score (default from agents.yaml)
        agent_scores: Optional dict mapping source_event_id → per-agent scores

    Returns:
        List of (event, score) tuples for events below threshold
    """
    flagged = []
    for event in events:
        event_id = str(event.source_event_id)
        scores = (agent_scores or {}).get(event_id)
        score = compute_confidence_score(event, scores)
        if score < threshold:
            flagged.append((event, score))
    return flagged
