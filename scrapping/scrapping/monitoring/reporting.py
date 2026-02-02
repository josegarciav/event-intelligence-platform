"""
scrapping.monitoring.reporting

Builds run + per-source reports.

A report is a JSON-friendly dict that contains:
- run metadata (timestamps, run_id)
- per-source summary (stats, errors, artifact paths)
- overall metrics (counters/gauges/timers)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scrapping.monitoring.metrics import MetricsRegistry


@dataclass
class SourceReport:
    source_id: str
    ok: bool
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)


@dataclass
class RunReportBuilder:
    run_id: str
    started_at_s: float = field(default_factory=lambda: time.time())
    finished_at_s: Optional[float] = None

    sources: List[SourceReport] = field(default_factory=list)
    metrics: MetricsRegistry = field(default_factory=MetricsRegistry)

    meta: Dict[str, Any] = field(default_factory=dict)

    def add_source(self, sr: SourceReport) -> None:
        self.sources.append(sr)

    def finish(self) -> None:
        if self.finished_at_s is None:
            self.finished_at_s = time.time()

    def as_dict(self) -> Dict[str, Any]:
        self.finish()

        total = len(self.sources)
        ok = sum(1 for s in self.sources if s.ok)
        failed = total - ok

        # Useful top-level quick stats
        agg = {
            "sources_total": total,
            "sources_ok": ok,
            "sources_failed": failed,
        }

        # Aggregate a few common counters if available
        # (not mandatory; your pipeline will populate gradually)
        return {
            "run_id": self.run_id,
            "started_at_s": self.started_at_s,
            "finished_at_s": self.finished_at_s,
            "elapsed_s": (self.finished_at_s - self.started_at_s) if self.finished_at_s else None,
            "meta": dict(self.meta),
            "summary": agg,
            "sources": [
                {
                    "source_id": s.source_id,
                    "ok": s.ok,
                    "stats": s.stats,
                    "errors": s.errors,
                    "artifacts": s.artifacts,
                    "timings": s.timings,
                }
                for s in self.sources
            ],
            "metrics": self.metrics.as_dict(),
        }


def exception_to_error_dict(e: Exception) -> Dict[str, Any]:
    return {"type": type(e).__name__, "message": str(e)}
