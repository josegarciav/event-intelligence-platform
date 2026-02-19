"""
FastMCP client implementations for local and server modes.

LocalMCPClient   — in-process FastMCP (mcp_mode: "local")
  Uses FastMCP's in-memory transport. No network. Same Python process.
  FastMCP Client connects directly to the server instance.

ServerMCPClient  — HTTP FastMCP (mcp_mode: "server")
  Connects to a running FastMCP HTTP server via SSE transport.
  The server must be started separately:
    python -m src.agents.mcp.fastmcp_server --host localhost --port 8001

Both implement the MCPClient abstract interface so they are drop-in
replacements for DirectMCPClient with no changes to calling code.
"""

import json
import logging
from typing import TYPE_CHECKING, Any

from src.agents.mcp.mcp_client import MCPClient, WriteResult

if TYPE_CHECKING:
    from src.schemas.event import EventSchema

logger = logging.getLogger(__name__)


# =============================================================================
# LOCAL MODE — in-process FastMCP (no network)
# =============================================================================


class LocalMCPClient(MCPClient):
    """
    In-process FastMCP client.

    Uses FastMCP's in-memory transport — the server and client run in the same
    Python process with no network overhead and no serialization to disk.

    How it works:
      1. Events are loaded into the fastmcp_server module-level store via load_events()
      2. A FastMCP Client(server_instance) opens an in-process session
      3. Tools are called via the MCP protocol (JSON round-trip in memory)

    Compared to DirectMCPClient:
      - Goes through the full MCP protocol (tool definitions, JSON serialization)
      - Validates tool call schemas just like a real client would
      - Useful for testing the server tools without starting an HTTP server
    """

    def __init__(self, events: list["EventSchema"] | None = None):
        from src.agents.mcp.fastmcp_server import get_server, load_events

        self._server = get_server()
        if events:
            load_events(events)

    def load(self, events: list["EventSchema"]) -> None:
        """Load additional events into the server store."""
        from src.agents.mcp.fastmcp_server import load_events

        load_events(events)

    async def read(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call a read tool on the in-process FastMCP server."""
        return await self._call_tool(operation, params)

    async def write(self, operation: str, payload: dict[str, Any]) -> WriteResult:
        """Call a write tool on the in-process FastMCP server."""
        data = await self._call_tool(operation, payload)
        return WriteResult(
            success=data.get("success", False),
            operation=operation,
            event_id=payload.get("event_id"),
            fields_written=data.get("fields_written", []),
            error=data.get("error"),
        )

    async def _call_tool(
        self, tool_name: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Open an in-process client session and call a tool."""
        try:
            from fastmcp import Client

            # Serialize dict/list params that the FastMCP server expects as JSON strings
            serialized = _serialize_params(params)

            async with Client(self._server) as client:
                result = await client.call_tool(tool_name, serialized)

            if result and hasattr(result[0], "text"):
                return json.loads(result[0].text)
            return {}

        except ImportError:
            logger.error("fastmcp package not installed — pip install fastmcp")
            return {}
        except Exception as e:
            logger.warning(f"LocalMCPClient tool call '{tool_name}' failed: {e}")
            return {}


# =============================================================================
# SERVER MODE — HTTP FastMCP (separate process)
# =============================================================================


class ServerMCPClient(MCPClient):
    """
    HTTP FastMCP client for server mode.

    Connects to a running FastMCP server via HTTP SSE transport.

    Start the server first:
        python -m src.agents.mcp.fastmcp_server --host localhost --port 8001

    The server_url should point to the FastMCP SSE endpoint.
    Default: http://localhost:8001

    Compared to LocalMCPClient:
      - Crosses a network boundary (TCP)
      - Server can run on a separate machine or container
      - Production-ready when backed by a persistent DB instead of in-memory store
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8001",
        events: list["EventSchema"] | None = None,
    ):
        self._server_url = server_url
        if events:
            # In server mode, events must be loaded into the remote server
            # This is done asynchronously — call await self.load(events) instead
            logger.info(
                f"ServerMCPClient: events provided at init — call await client.load(events) "
                f"to push them to the server at {server_url}"
            )

    async def load(self, events: list["EventSchema"]) -> int:
        """
        Push events to the remote FastMCP server via the load_events_tool.

        Args:
            events: EventSchema instances to send to the server store

        Returns:
            Number of events loaded on the server
        """
        events_data = []
        for event in events:
            if hasattr(event, "model_dump"):
                events_data.append(event.model_dump(mode="json"))
            elif isinstance(event, dict):
                events_data.append(event)

        result = await self._call_tool(
            "load_events_tool", {"events_json": json.dumps(events_data, default=str)}
        )
        loaded = result.get("loaded", 0)
        logger.info(
            f"ServerMCPClient: loaded {loaded} events on remote server ({self._server_url})"
        )
        return loaded

    async def read(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call a read tool on the remote FastMCP server."""
        return await self._call_tool(operation, params)

    async def write(self, operation: str, payload: dict[str, Any]) -> WriteResult:
        """Call a write tool on the remote FastMCP server."""
        data = await self._call_tool(operation, payload)
        return WriteResult(
            success=data.get("success", False),
            operation=operation,
            event_id=payload.get("event_id"),
            fields_written=data.get("fields_written", []),
            error=data.get("error"),
        )

    async def _call_tool(
        self, tool_name: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Open an HTTP client session and call a tool on the remote server."""
        try:
            from fastmcp import Client

            serialized = _serialize_params(params)

            async with Client(self._server_url) as client:
                result = await client.call_tool(tool_name, serialized)

            if result and hasattr(result[0], "text"):
                return json.loads(result[0].text)
            return {}

        except ImportError:
            logger.error("fastmcp package not installed — pip install fastmcp")
            return {}
        except ConnectionRefusedError:
            logger.error(
                f"ServerMCPClient: cannot connect to FastMCP server at {self._server_url}. "
                "Is the server running? Start with: python -m src.agents.mcp.fastmcp_server"
            )
            return {}
        except Exception as e:
            logger.warning(f"ServerMCPClient tool call '{tool_name}' failed: {e}")
            return {}


# =============================================================================
# Helpers
# =============================================================================


def _serialize_params(params: dict[str, Any]) -> dict[str, Any]:
    """
    Convert dict/list values in params to JSON strings.

    FastMCP tools that take complex types (dicts, lists) as JSON string args
    need serialization at the call site.
    """
    result = {}
    for k, v in params.items():
        if isinstance(v, dict | list):
            result[k] = json.dumps(v, default=str)
        else:
            result[k] = v
    return result
