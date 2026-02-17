"""Lightweight metrics system with counters, gauges, and timers.

Export to dict for run reporting.
Later can be adapted to Prometheus.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


def _key(name: str, labels: dict[str, str] | None) -> str:
    if not labels:
        return name
    parts = [name] + [f"{k}={v}" for k, v in sorted(labels.items())]
    return "|".join(parts)


@dataclass
class MetricsRegistry:
    """Registry for counters, gauges, and timers."""

    counters: dict[str, float] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    timers: dict[str, dict[str, float]] = field(default_factory=dict)  # sum, count, max, min

    def inc(self, name: str, value: float = 1.0, *, labels: dict[str, str] | None = None) -> None:
        """Increment a counter by the given value."""
        k = _key(name, labels)
        self.counters[k] = float(self.counters.get(k, 0.0)) + float(value)

    def set_gauge(self, name: str, value: float, *, labels: dict[str, str] | None = None) -> None:
        """Set a gauge to the given value."""
        k = _key(name, labels)
        self.gauges[k] = float(value)

    def observe(self, name: str, value: float, *, labels: dict[str, str] | None = None) -> None:
        """Record a timer observation."""
        k = _key(name, labels)
        d = self.timers.get(k)
        if d is None:
            d = {"sum": 0.0, "count": 0.0, "max": value, "min": value}
            self.timers[k] = d
        d["sum"] += float(value)
        d["count"] += 1.0
        d["max"] = max(d["max"], float(value))
        d["min"] = min(d["min"], float(value))

    @contextmanager
    def time(self, name: str, *, labels: dict[str, str] | None = None) -> Iterator[None]:
        """Time a block and record the elapsed duration as an observation."""
        t0 = time.time()
        try:
            yield
        finally:
            self.observe(name, time.time() - t0, labels=labels)

    def as_dict(self) -> dict[str, Any]:
        """Export all metrics as a JSON-friendly dictionary."""
        # shallow, json-friendly
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "timers": {k: dict(v) for k, v in self.timers.items()},
        }
