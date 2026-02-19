"""
MCP Client abstraction layer.

MCPClient       — abstract interface (read/write)
DirectMCPClient — pure in-memory, no FastMCP (mcp_mode: "direct")
LocalMCPClient  — FastMCP in-process via in-memory transport (mcp_mode: "local")
ServerMCPClient — FastMCP over HTTP SSE (mcp_mode: "server")

Factory:
    client = create_mcp_client(mode="local", events=events)

Mode is set in configs/agents.yaml under global.mcp_mode.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.event import EventSchema

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    """Result of an MCP write operation."""

    success: bool
    operation: str
    event_id: str | None = None
    fields_written: list[str] = field(default_factory=list)
    error: str | None = None


class MCPClient(ABC):
    """
    Abstract MCP interface.

    All enrichment agents interact with events exclusively through this interface.
    Concrete implementations: DirectMCPClient (in-memory), LocalMCPClient (FastMCP
    in-process), ServerMCPClient (FastMCP over HTTP SSE).
    """

    @abstractmethod
    async def read(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Read data from the MCP layer.

        Args:
            operation: read operation name (e.g., "fetch_event_row", "fetch_html")
            params: operation parameters

        Returns:
            Dict with requested data
        """
        ...

    @abstractmethod
    async def write(self, operation: str, payload: dict[str, Any]) -> WriteResult:
        """
        Write enriched data back through the MCP layer.

        Args:
            operation: write operation name (e.g., "write_features", "write_taxonomy")
            payload: data to write

        Returns:
            WriteResult indicating success/failure
        """
        ...


class DirectMCPClient(MCPClient):
    """
    In-memory MCP client (mcp_mode: "direct").

    Operations act directly on EventSchema objects held in memory.
    No network calls, no database writes. Use LocalMCPClient or ServerMCPClient
    for FastMCP-backed modes.
    """

    def __init__(self, events: list["EventSchema"] | None = None):
        self._events: dict[str, EventSchema] = {}
        if events:
            for event in events:
                key = str(event.source_event_id or id(event))
                self._events[key] = event

    def load_events(self, events: list["EventSchema"]) -> None:
        """Load events into the in-memory store."""
        for event in events:
            key = str(event.source_event_id or id(event))
            self._events[key] = event

    async def read(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Dispatch read operation to appropriate handler."""
        handlers = {
            "fetch_event_row": self._fetch_event_row,
            "fetch_missing_features": self._fetch_missing_features,
            "list_events": self._list_events,
        }
        handler = handlers.get(operation)
        if handler:
            return await handler(params)
        logger.warning(f"DirectMCPClient: unknown read operation '{operation}'")
        return {}

    async def write(self, operation: str, payload: dict[str, Any]) -> WriteResult:
        """Dispatch write operation to appropriate handler."""
        handlers = {
            "write_features": self._write_features,
            "write_taxonomy": self._write_taxonomy,
            "write_emotions": self._write_emotions,
            "write_tags": self._write_tags,
        }
        handler = handlers.get(operation)
        if handler:
            return await handler(payload)
        logger.warning(f"DirectMCPClient: unknown write operation '{operation}'")
        return WriteResult(
            success=False, operation=operation, error=f"Unknown operation: {operation}"
        )

    # -------------------------------------------------------------------------
    # Read handlers
    # -------------------------------------------------------------------------

    async def _fetch_event_row(self, params: dict[str, Any]) -> dict[str, Any]:
        event_id = str(params.get("event_id", ""))
        event = self._events.get(event_id)
        if event is None:
            return {}
        return event.model_dump()

    async def _fetch_missing_features(self, params: dict[str, Any]) -> dict[str, Any]:
        event_id = str(params.get("event_id", ""))
        target_fields: list[str] = params.get("target_fields", [])
        event = self._events.get(event_id)
        if event is None:
            return {"missing": target_fields}
        event_dict = event.model_dump()
        missing = [f for f in target_fields if not event_dict.get(f)]
        return {"event_id": event_id, "missing": missing, "total": len(missing)}

    async def _list_events(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"event_ids": list(self._events.keys()), "count": len(self._events)}

    # -------------------------------------------------------------------------
    # Write handlers (in-memory mutations)
    # -------------------------------------------------------------------------

    async def _write_features(self, payload: dict[str, Any]) -> WriteResult:
        event_id = str(payload.get("event_id", ""))
        event = self._events.get(event_id)
        if event is None:
            return WriteResult(
                success=False,
                operation="write_features",
                event_id=event_id,
                error="Event not found",
            )
        fields = payload.get("fields", {})
        written = []
        for field_name, value in fields.items():
            if hasattr(event, field_name):
                setattr(event, field_name, value)
                written.append(field_name)
        return WriteResult(
            success=True,
            operation="write_features",
            event_id=event_id,
            fields_written=written,
        )

    async def _write_taxonomy(self, payload: dict[str, Any]) -> WriteResult:
        event_id = str(payload.get("event_id", ""))
        event = self._events.get(event_id)
        if event is None:
            return WriteResult(
                success=False,
                operation="write_taxonomy",
                event_id=event_id,
                error="Event not found",
            )
        taxonomy_data = payload.get("taxonomy", {})
        if taxonomy_data and event.taxonomy:
            for field_name, value in taxonomy_data.items():
                if hasattr(event.taxonomy, field_name):
                    setattr(event.taxonomy, field_name, value)
        return WriteResult(success=True, operation="write_taxonomy", event_id=event_id)

    async def _write_emotions(self, payload: dict[str, Any]) -> WriteResult:
        event_id = str(payload.get("event_id", ""))
        event = self._events.get(event_id)
        if event is None:
            return WriteResult(
                success=False,
                operation="write_emotions",
                event_id=event_id,
                error="Event not found",
            )
        emotions = payload.get("emotional_output", [])
        if event.taxonomy and emotions:
            event.taxonomy.emotional_output = emotions
        return WriteResult(success=True, operation="write_emotions", event_id=event_id)

    async def _write_tags(self, payload: dict[str, Any]) -> WriteResult:
        event_id = str(payload.get("event_id", ""))
        event = self._events.get(event_id)
        if event is None:
            return WriteResult(
                success=False,
                operation="write_tags",
                event_id=event_id,
                error="Event not found",
            )
        tags = payload.get("tags", [])
        if tags:
            existing = set(event.tags or [])
            event.tags = list(existing | set(tags))
        return WriteResult(success=True, operation="write_tags", event_id=event_id)


# =============================================================================
# Factory
# =============================================================================


def create_mcp_client(
    mode: str = "local",
    events: "list[EventSchema] | None" = None,
    server_url: str = "http://localhost:8001",
) -> MCPClient:
    """
    Create the appropriate MCP client for the given mode.

    Args:
        mode: "direct" | "local" | "server"
              direct — pure in-memory DirectMCPClient (no FastMCP dependency)
              local  — FastMCP in-process via in-memory transport
              server — FastMCP over HTTP SSE (requires running server)
        events: EventSchema objects to pre-load into the store
        server_url: Base URL of the FastMCP server (server mode only)

    Returns:
        Configured MCPClient instance

    Example:
        # Local mode (default — no network)
        client = create_mcp_client("local", events=pipeline_result.events)

        # Server mode (FastMCP HTTP)
        client = create_mcp_client("server", server_url="http://localhost:8001")
        await client.load(events)
    """
    if mode == "direct":
        return DirectMCPClient(events=events)

    elif mode == "local":
        from src.agents.mcp.fastmcp_client import LocalMCPClient

        return LocalMCPClient(events=events)

    elif mode == "server":
        from src.agents.mcp.fastmcp_client import ServerMCPClient

        client = ServerMCPClient(server_url=server_url, events=events)
        return client

    else:
        logger.warning(f"Unknown mcp_mode '{mode}', defaulting to 'local'")
        from src.agents.mcp.fastmcp_client import LocalMCPClient

        return LocalMCPClient(events=events)
