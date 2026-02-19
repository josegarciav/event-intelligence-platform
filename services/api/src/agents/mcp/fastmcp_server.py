"""
Pulsecity FastMCP Server.

Exposes enrichment read/write operations as MCP tools.
Can run in two modes (set via agents.yaml: global.mcp_mode):

  local  — in-process via FastMCP in-memory transport (no network)
  server — HTTP SSE server (separate process, connects over network)

In both modes, all event data is stored in the module-level _event_store dict.
For the "server" mode, load events into the store before starting the server.

Entry points:
  # Start HTTP server (server mode)
  python -m src.agents.mcp.fastmcp_server --host localhost --port 8001

  # Get server instance (local mode — used by LocalMCPClient)
  from src.agents.mcp.fastmcp_server import get_server, load_events

Tools exposed:
  READ:  fetch_event_row, fetch_missing_features, list_events, fetch_taxonomy_enums
  WRITE: write_features, write_taxonomy, write_emotions, write_tags, load_events_tool
"""

import json
import logging
from typing import Any

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# =============================================================================
# Shared in-memory event store
# Keyed by source_event_id (str). Values are model_dump() dicts.
# =============================================================================
_event_store: dict[str, dict[str, Any]] = {}
_taxonomy_enums: dict[str, list[str]] = {
    "energy_level": ["low", "medium", "high"],
    "social_intensity": ["solo", "small_group", "large_group"],
    "cognitive_load": ["low", "medium", "high"],
    "physical_involvement": ["none", "light", "moderate"],
    "environment": ["indoor", "outdoor", "digital", "mixed"],
    "risk_level": ["none", "very_low", "low", "medium"],
    "age_accessibility": ["all", "teens+", "adults"],
    "repeatability": ["high", "medium", "low"],
    "cost_level": ["free", "low", "medium", "high"],
    "time_scale": ["short", "long", "recurring"],
}

# =============================================================================
# FastMCP server instance
# =============================================================================
mcp = FastMCP(
    name="pulsecity-enrichment",
    instructions=(
        "Pulsecity MCP server for event enrichment. "
        "Provides read/write access to the event store used by enrichment agents. "
        "All event data is keyed by source_event_id."
    ),
)


# =============================================================================
# Helpers
# =============================================================================


def load_events(events: list[Any]) -> int:
    """
    Load EventSchema objects (or dicts) into the server's event store.

    Args:
        events: List of EventSchema instances or plain dicts

    Returns:
        Number of events loaded
    """
    global _event_store
    loaded = 0
    for event in events:
        if hasattr(event, "model_dump"):
            data = event.model_dump()
        elif isinstance(event, dict):
            data = event
        else:
            logger.warning(f"Skipping unrecognised event type: {type(event)}")
            continue

        event_id = str(data.get("source_event_id") or id(event))
        _event_store[event_id] = data
        loaded += 1

    logger.info(
        f"FastMCP server: loaded {loaded} events into store (total: {len(_event_store)})"
    )
    return loaded


def get_enriched_events() -> list[dict[str, Any]]:
    """Return all events from the store (after enrichment)."""
    return list(_event_store.values())


def clear_store() -> None:
    """Clear the event store (useful between pipeline runs)."""
    global _event_store
    _event_store.clear()


def get_server() -> FastMCP:
    """Return the FastMCP server instance (used by LocalMCPClient)."""
    return mcp


# =============================================================================
# READ TOOLS
# =============================================================================


@mcp.tool()
def fetch_event_row(event_id: str) -> str:
    """
    Fetch a single event row from the store by its source_event_id.

    Returns a JSON string of the event dict, or '{}' if not found.
    """
    event = _event_store.get(event_id, {})
    return json.dumps(event, default=str)


@mcp.tool()
def fetch_missing_features(event_id: str, target_fields: list[str]) -> str:
    """
    Check which of the target_fields are missing (None or empty) for an event.

    Returns JSON: {"event_id": str, "missing": [field_names], "total": int}
    """
    event = _event_store.get(event_id, {})
    if not event:
        return json.dumps(
            {
                "event_id": event_id,
                "missing": target_fields,
                "total": len(target_fields),
                "error": "Event not found",
            }
        )

    missing = []
    for field in target_fields:
        value = event.get(field)
        # Check nested taxonomy fields
        if value is None and "." in field:
            parts = field.split(".", 1)
            nested = event.get(parts[0], {})
            value = (nested or {}).get(parts[1])
        if value is None or value == [] or value == "":
            missing.append(field)

    return json.dumps({"event_id": event_id, "missing": missing, "total": len(missing)})


@mcp.tool()
def list_events() -> str:
    """
    List all event IDs currently in the store.

    Returns JSON: {"event_ids": [...], "count": int}
    """
    return json.dumps(
        {"event_ids": list(_event_store.keys()), "count": len(_event_store)}
    )


@mcp.tool()
def fetch_taxonomy_enums() -> str:
    """
    Fetch valid enum values for all taxonomy fields.

    Returns JSON dict mapping field_name → list of valid values.
    """
    return json.dumps(_taxonomy_enums)


# =============================================================================
# WRITE TOOLS
# =============================================================================


@mcp.tool()
def write_features(event_id: str, fields_json: str) -> str:
    """
    Write structured feature fields to an event.

    Args:
        event_id: source_event_id of the event to update
        fields_json: JSON string of {field_name: value} pairs to write

    Returns JSON: {"success": bool, "fields_written": [...], "error": str|null}
    """
    if event_id not in _event_store:
        return json.dumps(
            {
                "success": False,
                "fields_written": [],
                "error": f"Event '{event_id}' not found",
            }
        )

    try:
        fields = json.loads(fields_json)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"success": False, "fields_written": [], "error": f"Invalid JSON: {e}"}
        )

    _event_store[event_id].update(fields)
    return json.dumps(
        {"success": True, "fields_written": list(fields.keys()), "error": None}
    )


@mcp.tool()
def write_taxonomy(event_id: str, taxonomy_json: str) -> str:
    """
    Write taxonomy dimension fields to an event's taxonomy sub-object.

    Args:
        event_id: source_event_id of the event
        taxonomy_json: JSON string of taxonomy fields to write

    Returns JSON: {"success": bool, "fields_written": [...], "error": str|null}
    """
    if event_id not in _event_store:
        return json.dumps(
            {
                "success": False,
                "fields_written": [],
                "error": f"Event '{event_id}' not found",
            }
        )

    try:
        taxonomy_data = json.loads(taxonomy_json)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"success": False, "fields_written": [], "error": f"Invalid JSON: {e}"}
        )

    event = _event_store[event_id]
    if "taxonomy" not in event or event["taxonomy"] is None:
        event["taxonomy"] = {}
    event["taxonomy"].update(taxonomy_data)

    return json.dumps(
        {"success": True, "fields_written": list(taxonomy_data.keys()), "error": None}
    )


@mcp.tool()
def write_emotions(event_id: str, emotional_output_json: str) -> str:
    """
    Write emotional output tags to an event's taxonomy.emotional_output field.

    Args:
        event_id: source_event_id of the event
        emotional_output_json: JSON array of emotion strings, e.g. '["joy", "excitement"]'

    Returns JSON: {"success": bool, "error": str|null}
    """
    if event_id not in _event_store:
        return json.dumps({"success": False, "error": f"Event '{event_id}' not found"})

    try:
        emotions = json.loads(emotional_output_json)
        if not isinstance(emotions, list):
            raise ValueError("Expected a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"success": False, "error": f"Invalid input: {e}"})

    event = _event_store[event_id]
    if "taxonomy" not in event or event["taxonomy"] is None:
        event["taxonomy"] = {}
    event["taxonomy"]["emotional_output"] = emotions

    return json.dumps({"success": True, "error": None})


@mcp.tool()
def write_tags(event_id: str, tags_json: str) -> str:
    """
    Merge enriched tags into an event's tags list (deduplicates).

    Args:
        event_id: source_event_id of the event
        tags_json: JSON array of tag strings, e.g. '["techno", "nightlife"]'

    Returns JSON: {"success": bool, "tags_count": int, "error": str|null}
    """
    if event_id not in _event_store:
        return json.dumps(
            {
                "success": False,
                "tags_count": 0,
                "error": f"Event '{event_id}' not found",
            }
        )

    try:
        new_tags = json.loads(tags_json)
        if not isinstance(new_tags, list):
            raise ValueError("Expected a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps(
            {"success": False, "tags_count": 0, "error": f"Invalid input: {e}"}
        )

    event = _event_store[event_id]
    existing = set(event.get("tags") or [])
    merged = list(existing | set(new_tags))
    event["tags"] = merged

    return json.dumps({"success": True, "tags_count": len(merged), "error": None})


@mcp.tool()
def load_events_tool(events_json: str) -> str:
    """
    Load events into the server store from a JSON string.

    Used in server mode to initialise the store after the server starts.

    Args:
        events_json: JSON array of event dicts

    Returns JSON: {"loaded": int, "total": int}
    """
    global _event_store
    try:
        events = json.loads(events_json)
        if not isinstance(events, list):
            raise ValueError("Expected a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"loaded": 0, "total": 0, "error": str(e)})

    loaded = 0
    for event in events:
        event_id = str(event.get("source_event_id") or id(event))
        _event_store[event_id] = event
        loaded += 1

    return json.dumps({"loaded": loaded, "total": len(_event_store)})


# =============================================================================
# SERVER RUNNER (server mode)
# =============================================================================


def run_server(host: str = "localhost", port: int = 8001) -> None:
    """
    Start the FastMCP server in HTTP SSE mode.

    Used when mcp_mode = "server". Run as:
        python -m src.agents.mcp.fastmcp_server
        python -m src.agents.mcp.fastmcp_server --host 0.0.0.0 --port 8001
    """
    logger.info(f"Starting Pulsecity FastMCP server at http://{host}:{port}")
    mcp.run(transport="streamable-http", host=host, port=port)


# =============================================================================
# CLI entry point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pulsecity FastMCP Enrichment Server")
    parser.add_argument(
        "--host", default="localhost", help="Bind host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=8001, help="Bind port (default: 8001)"
    )
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)
