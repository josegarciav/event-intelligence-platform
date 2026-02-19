# src/schemas/taxonomy.py
"""
Builds and provides access to the Human Experience Taxonomy index.

Provides functions to:
- Load and cache the taxonomy
- Build indexes for category/subcategory lookups
- Get activity-level details by ID
- Find best activity matches for events
"""

import json
from functools import lru_cache
from typing import Any

from src.configs.config import Config

TAXONOMY_PATH = Config.get_taxonomy_path()


def _normalize_primary_key(label: str) -> str:
    """Normalize category label to index key (lowercase, symbols removed, spaces -> '_')."""
    return (
        label.lower()
        .replace(" & ", "_")
        .replace(",", "")
        .replace("-", "_")
        .replace(" ", "_")
    )


@lru_cache
def load_taxonomy() -> dict:
    """Load and cache the Human Experience Taxonomy."""
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_taxonomy_index() -> dict[str, set[str]]:
    """
    Build a mapping of primary_category to set of subcategory_ids.

    Returns:
        Dict mapping primary category key to set of subcategory IDs.
    """
    taxonomy = load_taxonomy()
    index: dict[str, set[str]] = {}

    for cat in taxonomy["categories"]:
        primary = _normalize_primary_key(cat["category"])
        index[primary] = {sub["id"] for sub in cat.get("subcategories", [])}

    return index


# =============================================================================
# PRIMARY CATEGORY ID MAPPING (dynamically built from taxonomy JSON)
# =============================================================================


@lru_cache
def _build_primary_category_id_map() -> dict[str, str]:
    """Build mapping from numeric category ID to normalized category value from taxonomy JSON."""
    taxonomy = load_taxonomy()
    id_map: dict[str, str] = {}
    for cat in taxonomy["categories"]:
        cat_id = cat["category_id"]
        cat_value = _normalize_primary_key(cat["category"])
        id_map[cat_id] = cat_value
    return id_map


@lru_cache
def _build_primary_category_value_to_id() -> dict[str, str]:
    """Build reverse mapping from normalized category value to numeric ID."""
    return {v: k for k, v in _build_primary_category_id_map().items()}


def get_primary_category_id_map() -> dict[str, str]:
    """
    Get mapping from numeric ID to primary category value.

    Returns:
        Dict mapping "0" -> "other", "1" -> "play_pure_fun", etc.
    """
    return _build_primary_category_id_map().copy()


def get_primary_category_value_to_id_map() -> dict[str, str]:
    """
    Get mapping from primary category value to numeric ID.

    Returns:
        Dict mapping "other" -> "0", "play_pure_fun" -> "1", etc.
    """
    return _build_primary_category_value_to_id().copy()


def get_primary_category_mappings() -> tuple[dict[str, str], dict[str, str]]:
    """
    Build bidirectional ID <-> value mappings for primary categories.

    Returns:
        Tuple of (id_to_value, value_to_id) dicts.
    """
    return get_primary_category_id_map(), get_primary_category_value_to_id_map()


def resolve_primary_category(value: str) -> str:
    """
    Resolve any primary category representation to its normalized value.

    Accepts numeric ID ("1"), normalized value ("play_and_pure_fun"),
    or raw label ("PLAY & PURE FUN"). Returns the normalized value.

    Falls back to "other" if the value cannot be resolved.

    Example:
        >>> resolve_primary_category("1")
        'play_pure_fun'
        >>> resolve_primary_category("0")
        'other'
        >>> resolve_primary_category("play_pure_fun")
        'play_pure_fun'
    """
    id_map = _build_primary_category_id_map()
    value_to_id = _build_primary_category_value_to_id()

    # Try as numeric ID
    if value in id_map:
        return id_map[value]

    # Try as already-normalized value
    if value in value_to_id:
        return value

    # Try normalizing as a raw label
    normalized = _normalize_primary_key(value)
    if normalized in value_to_id:
        return normalized

    return "other"


def primary_category_to_id(value: str) -> str:
    """
    Convert a normalized primary category value to its numeric ID.

    Falls back to "0" (Other) if value not found.

    Example:
        >>> primary_category_to_id("play_pure_fun")
        '1'
        >>> primary_category_to_id("other")
        '0'
    """
    value_to_id = _build_primary_category_value_to_id()
    return value_to_id.get(value, "0")


def build_primary_to_subcategory_index() -> dict[str, set[str]]:
    """
    Map primary_id -> set of valid subcategory_ids.

    Returns:
        Dict mapping primary category numeric ID to set of subcategory IDs.
        E.g., "1" -> {"1.1", "1.2", "1.3", "1.4", "1.5"}

    Example:
        >>> index = build_primary_to_subcategory_index()
        >>> "1.4" in index["1"]
        True
        >>> "2.1" in index["1"]
        False
    """
    taxonomy_index = build_taxonomy_index()
    id_map = _build_primary_category_id_map()
    result: dict[str, set[str]] = {}

    for primary_id, primary_value in id_map.items():
        subcats = taxonomy_index.get(primary_value, set())
        result[primary_id] = subcats

    return result


def validate_subcategory_for_primary(subcategory_id: str, primary_id: str) -> bool:
    """
    Validate that a subcategory ID belongs to a primary category ID.

    Args:
        subcategory_id: Subcategory ID (e.g., "1.4")
        primary_id: Primary category ID (e.g., "1") or value (e.g., "play_and_fun")

    Returns:
        True if subcategory belongs to primary category, False otherwise.

    Example:
        >>> validate_subcategory_for_primary("1.4", "1")
        True
        >>> validate_subcategory_for_primary("2.1", "1")
        False
        >>> validate_subcategory_for_primary("1.4", "play_and_fun")
        True
    """
    # If primary_id is a value, convert to numeric ID
    value_to_id = _build_primary_category_value_to_id()
    if primary_id in value_to_id:
        primary_id = value_to_id[primary_id]

    # Simple validation: subcategory should start with primary_id + "."
    expected_prefix = f"{primary_id}."
    return subcategory_id.startswith(expected_prefix)


@lru_cache
def get_all_subcategory_options() -> list[dict[str, Any]]:
    """
    Return a flat list of all subcategory options from the taxonomy.

    Each option is a dict with:
      - "id": subcategory id (e.g. "1.4")
      - "name": human-readable name (e.g. "Music & Rhythm Play")
      - "primary_category": taxonomy primary key (e.g. "play_and_pure_fun")
    """
    taxonomy = load_taxonomy()
    out: list[dict[str, Any]] = []
    for cat in taxonomy["categories"]:
        primary = _normalize_primary_key(cat["category"])
        for sub in cat.get("subcategories", []):
            out.append(
                {
                    "id": sub["id"],
                    "name": sub["name"],
                    "primary_category": primary,
                }
            )
    return out


def get_all_subcategory_ids() -> set[str]:
    """Return the set of all valid subcategory ids."""
    return {opt["id"] for opt in get_all_subcategory_options()}


# =============================================================================
# ACTIVITY-LEVEL ACCESS FUNCTIONS
# =============================================================================


@lru_cache
def _build_activity_index() -> dict[str, dict[str, Any]]:
    """
    Build an index mapping activity_id -> full activity dict with context.

    Returns:
        Dict mapping activity_id to activity data including:
        - All activity fields (name, energy_level, etc.)
        - _primary_category: normalized primary category key
        - _primary_category_name: original category name
        - _subcategory_id: subcategory id (e.g. "1.4")
        - _subcategory_name: subcategory name
        - _subcategory_values: subcategory values list
    """
    taxonomy = load_taxonomy()
    index: dict[str, dict[str, Any]] = {}

    for cat in taxonomy["categories"]:
        primary_key = _normalize_primary_key(cat["category"])
        primary_name = cat["category"]

        for sub in cat.get("subcategories", []):
            sub_id = sub["id"]
            sub_name = sub["name"]
            sub_values = sub.get("values", [])

            for activity in sub.get("activities", []):
                activity_id = activity.get("activity_id")
                if activity_id:
                    index[activity_id] = {
                        **activity,
                        "_primary_category": primary_key,
                        "_primary_category_name": primary_name,
                        "_subcategory_id": sub_id,
                        "_subcategory_name": sub_name,
                        "_subcategory_values": sub_values,
                    }

    return index


@lru_cache
def _build_subcategory_index() -> dict[str, dict[str, Any]]:
    """
    Build an index mapping subcategory_id -> subcategory dict with context.

    Returns:
        Dict mapping subcategory_id to subcategory data including:
        - All subcategory fields (name, values, activities)
        - _primary_category: normalized primary category key
        - _primary_category_name: original category name
    """
    taxonomy = load_taxonomy()
    index: dict[str, dict[str, Any]] = {}

    for cat in taxonomy["categories"]:
        primary_key = _normalize_primary_key(cat["category"])
        primary_name = cat["category"]

        for sub in cat.get("subcategories", []):
            sub_id = sub["id"]
            index[sub_id] = {
                **sub,
                "_primary_category": primary_key,
                "_primary_category_name": primary_name,
            }

    return index


def get_activity_by_id(activity_id: str) -> dict[str, Any] | None:
    """
    Get full activity details by UUID.

    Args:
        activity_id: UUID of the activity (e.g., "e902519d-b316-465e-8955-d10240430281")

    Returns:
        Full activity dict with all fields including:
        - name, energy_level, social_intensity, cognitive_load, etc.
        - _primary_category, _subcategory_id, _subcategory_name, _subcategory_values
        Returns None if not found.

    Example:
        >>> activity = get_activity_by_id("e902519d-b316-465e-8955-d10240430281")
        >>> print(activity["name"])  # "Board games"
        >>> print(activity["_subcategory_id"])  # "1.1"
    """
    index = _build_activity_index()
    return index.get(activity_id)


def get_subcategory_by_id(subcategory_id: str) -> dict[str, Any] | None:
    """
    Get full subcategory details by ID.

    Args:
        subcategory_id: Subcategory ID (e.g., "1.4")

    Returns:
        Full subcategory dict with all fields including:
        - id, name, values, activities
        - _primary_category, _primary_category_name
        Returns None if not found.
    """
    index = _build_subcategory_index()
    return index.get(subcategory_id)


def get_activities_for_subcategory(subcategory_id: str) -> list[dict[str, Any]]:
    """
    Get all activities for a subcategory.

    Args:
        subcategory_id: Subcategory ID (e.g., "1.4")

    Returns:
        List of activity dicts for the subcategory.
        Empty list if subcategory not found.

    Example:
        >>> activities = get_activities_for_subcategory("1.4")
        >>> for a in activities:
        ...     print(a["name"])
    """
    sub = get_subcategory_by_id(subcategory_id)
    if not sub:
        return []
    return sub.get("activities", [])


def find_best_activity_match(
    event_context: str,
    subcategory_id: str,
    threshold: float = 0.3,
) -> dict[str, Any] | None:
    """
    Find best matching activity for event text within a subcategory.

    Uses simple keyword matching to find the most relevant activity.
    For more sophisticated matching, use FeatureExtractor with LLM.

    Args:
        event_context: Event title + description text
        subcategory_id: Subcategory ID to search within (e.g., "1.4")
        threshold: Minimum match score (0.0-1.0) to return a result

    Returns:
        Best matching activity dict with match_score, or None if no match.

    Example:
        >>> match = find_best_activity_match("Electronic DJ Night", "1.4")
        >>> if match:
        ...     print(match["name"], match["_match_score"])
    """
    activities = get_activities_for_subcategory(subcategory_id)
    if not activities:
        return None

    event_lower = event_context.lower()
    event_words = set(event_lower.split())

    best_match = None
    best_score = 0.0

    for activity in activities:
        activity_name = activity.get("name", "").lower()
        activity_words = set(activity_name.split())

        # Calculate simple overlap score
        if activity_words:
            # Check for exact name match
            if activity_name in event_lower:
                score = 1.0
            else:
                # Word overlap score
                overlap = len(event_words & activity_words)
                score = overlap / len(activity_words) if activity_words else 0.0

            if score > best_score:
                best_score = score
                best_match = {**activity, "_match_score": score}

    if best_match and best_score >= threshold:
        return best_match
    return None


def get_primary_category_for_subcategory(subcategory_id: str) -> str | None:
    """
    Get the primary category key for a subcategory.

    Args:
        subcategory_id: Subcategory ID (e.g., "1.4")

    Returns:
        Primary category key (e.g., "play_and_pure_fun") or None.
    """
    sub = get_subcategory_by_id(subcategory_id)
    if sub:
        return sub.get("_primary_category")
    return None


def get_full_taxonomy_dimension(
    primary_category: str,
    subcategory_id: str,
    activity_id: str | None = None,
    confidence: float = 0.5,
    values: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build complete TaxonomyDimension dict with all fields from schema example.

    This creates a rich taxonomy dimension structure that can be used
    to populate EventSchema.taxonomy_dimension.

    Args:
        primary_category: Normalized primary category key (e.g., "play_and_fun")
        subcategory_id: Subcategory ID (e.g., "1.4")
        activity_id: Optional activity UUID for specific activity details
        confidence: Confidence score (0.0-1.0)
        values: Optional override for subcategory values

    Returns:
        Dict with all taxonomy dimension fields:
        - primary_category
        - subcategory, subcategory_name, subcategory_values
        - activity_id, activity_name (if activity_id provided)
        - energy_level, social_intensity, cognitive_load, etc. (from activity)
        - confidence

    Example:
        >>> dim = get_full_taxonomy_dimension(
        ...     "play_and_fun", "1.4",
        ...     activity_id="35e5f715-5f31-43e0-8906-e408f198d72b",
        ...     confidence=0.9
        ... )
        >>> print(dim["activity_name"])  # "Party games"
    """
    result: dict[str, Any] = {
        "primary_category": primary_category,
        "subcategory": subcategory_id,
        "confidence": confidence,
    }

    # Add subcategory details
    sub = get_subcategory_by_id(subcategory_id)
    if sub:
        result["subcategory_name"] = sub.get("name")
        result["subcategory_values"] = values or sub.get("values", [])

    # Add activity details if provided
    if activity_id:
        activity = get_activity_by_id(activity_id)
        if activity:
            result["activity_id"] = activity_id
            result["activity_name"] = activity.get("name")
            result["energy_level"] = activity.get("energy_level")
            result["social_intensity"] = activity.get("social_intensity")
            result["cognitive_load"] = activity.get("cognitive_load")
            result["physical_involvement"] = activity.get("physical_involvement")
            result["cost_level"] = activity.get("cost_level")
            result["time_scale"] = activity.get("time_scale")
            result["environment"] = activity.get("environment")
            result["emotional_output"] = activity.get("emotional_output", [])
            result["risk_level"] = activity.get("risk_level")
            result["age_accessibility"] = activity.get("age_accessibility")
            result["repeatability"] = activity.get("repeatability")
    else:
        # Set default values for activity-level fields
        result["values"] = values or (sub.get("values", []) if sub else [])

    return result


def list_all_activities() -> list[dict[str, Any]]:
    """
    Get a list of all activities across all subcategories.

    Returns:
        List of activity dicts with context (_primary_category, _subcategory_id, etc.)
    """
    index = _build_activity_index()
    return list(index.values())


def search_activities_by_name(
    query: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Search activities by name.

    Args:
        query: Search query string
        limit: Maximum results to return

    Returns:
        List of matching activity dicts with _match_score
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    results = []

    for activity in list_all_activities():
        name = activity.get("name", "").lower()
        name_words = set(name.split())

        # Exact substring match
        if query_lower in name:
            score = 1.0
        elif name_words & query_words:
            # Partial word match
            overlap = len(name_words & query_words)
            score = overlap / max(len(query_words), 1)
        else:
            continue

        results.append({**activity, "_match_score": score})

    # Sort by score and return top results
    results.sort(key=lambda x: x["_match_score"], reverse=True)
    return results[:limit]
