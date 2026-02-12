"""Structured logging with context injection.

Features:
- console handler
- file handler (per run + per source optional)
- JSON logs optional (easy ingestion)
- context injection (run_id/source_id) without needing a big framework
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scrapping.storage.layouts import Layout, ensure_parent

# ---------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Perform the operation."""
        base = {
            "ts": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # standard extras
        for k in ("run_id", "source_id", "stage", "event"):
            if hasattr(record, k):
                base[k] = getattr(record, k)

        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)

        # allow structured payload
        payload = getattr(record, "payload", None)
        if isinstance(payload, dict):
            base["payload"] = payload

        return json.dumps(base, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Format log records as human-readable text."""

    def format(self, record: logging.LogRecord) -> str:
        """Perform the operation."""
        parts = [record.levelname, record.name]

        run_id = getattr(record, "run_id", None)
        source_id = getattr(record, "source_id", None)
        stage = getattr(record, "stage", None)

        ctx = []
        if run_id:
            ctx.append(f"run={run_id}")
        if source_id:
            ctx.append(f"source={source_id}")
        if stage:
            ctx.append(f"stage={stage}")

        if ctx:
            parts.append("[" + " ".join(ctx) + "]")

        parts.append(record.getMessage())
        s = " ".join(parts)

        if record.exc_info:
            s += "\n" + self.formatException(record.exc_info)

        return s


# ---------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class LoggingOptions:
    """Configure logging behavior for runs."""

    level: str = "INFO"
    json_logs: bool = False

    # file logging
    enable_file: bool = True
    per_source_file: bool = True

    # console logging
    enable_console: bool = True


def setup_run_logger(
    layout: Layout,
    *,
    run_id: str,
    options: LoggingOptions | None = None,
) -> logging.Logger:
    """Create a base logger for the run."""
    options = options or LoggingOptions()
    logger = logging.getLogger("scrapping")
    logger.setLevel(getattr(logging, options.level.upper(), logging.INFO))
    logger.propagate = False

    # Prevent duplicate handlers in repeated calls
    if getattr(logger, "_scrapping_run_id", None) == run_id:
        return logger

    # Clear old handlers if re-configuring for a new run
    for h in list(logger.handlers):
        logger.removeHandler(h)

    fmt = JsonFormatter() if options.json_logs else TextFormatter()

    if options.enable_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logger.level)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    if options.enable_file:
        run_log_path = layout.run_dir(run_id) / "run.log"
        ensure_parent(run_log_path)
        fh = logging.FileHandler(run_log_path, encoding="utf-8")
        fh.setLevel(logger.level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    logger._scrapping_run_id = run_id
    return logger


def get_source_log_path(layout: Layout, run_id: str, source_id: str) -> Path:
    """Return the log file path for a specific source."""
    return layout.source_dir(run_id, source_id) / "source.log"


def add_source_file_handler(
    logger: logging.Logger,
    layout: Layout,
    *,
    run_id: str,
    source_id: str,
    options: LoggingOptions | None = None,
) -> logging.Handler | None:
    """Add a per-source file handler to an existing logger."""
    options = options or LoggingOptions()
    if not options.enable_file or not options.per_source_file:
        return None

    fmt = JsonFormatter() if options.json_logs else TextFormatter()
    p = get_source_log_path(layout, run_id, source_id)
    ensure_parent(p)

    # Avoid duplicate handlers for the same file
    abs_path = str(p.resolve())
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename == abs_path:
            return h

    fh = logging.FileHandler(p, encoding="utf-8")
    fh.setLevel(logger.level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return fh


# ---------------------------------------------------------------------
# Context injection
# ---------------------------------------------------------------------


class ContextAdapter(logging.LoggerAdapter):
    """Inject context fields into log records."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Perform the operation."""
        extra = kwargs.get("extra", {})
        merged = dict(self.extra)
        merged.update(extra)
        kwargs["extra"] = merged
        return msg, kwargs


def with_context(
    logger: logging.Logger,
    *,
    run_id: str | None = None,
    source_id: str | None = None,
    stage: str | None = None,
) -> ContextAdapter:
    """Create a context adapter with run, source, and stage info."""
    extra: dict[str, Any] = {}
    if run_id:
        extra["run_id"] = run_id
    if source_id:
        extra["source_id"] = source_id
    if stage:
        extra["stage"] = stage
    return ContextAdapter(logger, extra)
