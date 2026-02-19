"""
MCP Read Operations.

These functions wrap the MCPClient.read() interface for common read patterns.
They route to DirectMCPClient (in-memory) for mcp_mode = "direct"/"local",
or to a FastMCP HTTP server when mcp_mode = "server".
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.agents.mcp.mcp_client import MCPClient


async def fetch_event_row(client: "MCPClient", event_id: str) -> dict[str, Any]:
    """Fetch a single event row by ID."""
    return await client.read("fetch_event_row", {"event_id": event_id})


async def fetch_missing_features(
    client: "MCPClient",
    event_id: str,
    target_fields: list[str],
) -> dict[str, Any]:
    """
    Fetch which target fields are missing for a given event.

    Returns:
        {"event_id": ..., "missing": [...], "total": N}
    """
    return await client.read(
        "fetch_missing_features",
        {
            "event_id": event_id,
            "target_fields": target_fields,
        },
    )


async def list_events(client: "MCPClient") -> dict[str, Any]:
    """List all event IDs in the current MCP store."""
    return await client.read("list_events", {})
