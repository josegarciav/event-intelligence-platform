"""
MCP Write Operations.

These functions wrap the MCPClient.write() interface for common write patterns.
They route to DirectMCPClient (in-memory) for mcp_mode = "direct"/"local",
or to a FastMCP HTTP server when mcp_mode = "server".
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.agents.mcp.mcp_client import MCPClient, WriteResult


async def write_features(
    client: "MCPClient",
    event_id: str,
    fields: dict[str, Any],
) -> "WriteResult":
    """Write structured feature fields back to the event."""
    return await client.write("write_features", {"event_id": event_id, "fields": fields})


async def write_taxonomy(
    client: "MCPClient",
    event_id: str,
    taxonomy: dict[str, Any],
) -> "WriteResult":
    """Write taxonomy classification results back to the event."""
    return await client.write("write_taxonomy", {"event_id": event_id, "taxonomy": taxonomy})


async def write_emotions(
    client: "MCPClient",
    event_id: str,
    emotional_output: list[str],
) -> "WriteResult":
    """Write emotional output tags back to the event."""
    return await client.write("write_emotions", {"event_id": event_id, "emotional_output": emotional_output})


async def write_tags(
    client: "MCPClient",
    event_id: str,
    tags: list[str],
) -> "WriteResult":
    """Write enriched tags back to the event."""
    return await client.write("write_tags", {"event_id": event_id, "tags": tags})
