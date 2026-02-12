"""Standardized run events for better traceability."""

from __future__ import annotations

import logging
from typing import Any


def emit_event(
    logger: logging.Logger | logging.LoggerAdapter,
    event: str,
    payload: dict[str, Any] | None = None,
    *,
    level: str = "info",
    stage: str | None = None,
) -> None:
    """Emit a structured event to the logger."""
    lvl = getattr(logging, level.upper(), logging.INFO)

    # We use 'extra' to pass structured data to the formatter
    # The JsonFormatter will pick up run_id, source_id from the record
    # if they were provided via ContextAdapter.

    extra = {
        "event": event,
        "payload": payload or {},
    }
    if stage:
        extra["stage"] = stage

    logger.log(lvl, f"Event: {event}", extra=extra)
