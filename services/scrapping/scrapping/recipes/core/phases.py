from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from scrapping.monitoring.events import emit_event

logger = logging.getLogger("scrapping.recipes.core.phases")


class Phase(Protocol):
    name: str

    def run(self, ctx: Any) -> Any: ...


@dataclass
class PhaseResult:
    name: str
    ok: bool
    elapsed_ms: float
    error: str | None = None
    counts: dict[str, int] = field(default_factory=dict)


class PhaseRunner:
    def __init__(self, ctx: Any, log: Any = None):
        self.ctx = ctx
        self.log = log or logger
        self.results: list[PhaseResult] = []

    def run_phases(self, phases: Sequence[Phase], start_at: str | None = None):
        skip = start_at is not None
        for phase in phases:
            if skip:
                if phase.name == start_at:
                    skip = False
                else:
                    self.log.info(f"Skipping phase: {phase.name} (already done)")
                    continue

            emit_event(self.log, "phase.started", {"phase": phase.name})
            t0 = time.time()

            try:
                res = phase.run(self.ctx)
                elapsed = (time.time() - t0) * 1000

                # If phase returns a dict of counts or result, wrap it
                if not isinstance(res, PhaseResult):
                    res = PhaseResult(
                        name=phase.name,
                        ok=True,
                        elapsed_ms=elapsed,
                        counts=res if isinstance(res, dict) else {},
                    )

                self.results.append(res)
                emit_event(
                    self.log,
                    "phase.finished",
                    {"phase": phase.name, "ok": res.ok, "elapsed_ms": res.elapsed_ms},
                )

                if not res.ok:
                    self.log.error(f"Phase {phase.name} failed: {res.error}")
                    break

            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                res = PhaseResult(
                    name=phase.name, ok=False, elapsed_ms=elapsed, error=str(e)
                )
                self.results.append(res)
                emit_event(
                    self.log,
                    "phase.failed",
                    {"phase": phase.name, "error": str(e)},
                    level="error",
                )
                self.log.exception(f"Exception in phase {phase.name}")
                break
        return self.results
