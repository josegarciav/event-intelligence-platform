"""
scrapping.engines.base

Engine interfaces + shared primitives.

Goals:
- One standard response shape across HTTP and Browser engines.
- Built-in rate limiting + retry helpers (stdlib-only).
- Engines remain swappable: http | browser | hybrid.
"""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

Headers = Dict[str, str]


@dataclass
class FetchTimings:
    started_at_s: float
    ended_at_s: float

    @property
    def elapsed_s(self) -> float:
        return max(0.0, self.ended_at_s - self.started_at_s)


@dataclass
class FetchResult:
    ok: bool
    final_url: str
    status_code: Optional[int]
    text: Optional[str]
    headers: Headers
    timings: FetchTimings
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    def short_error(self) -> str:
        if self.ok:
            return ""
        return f"{self.error_type or 'Error'}: {self.error_message or ''}".strip()


@dataclass
class EngineContext:
    """
    The minimum execution context engines may need.
    Keep it small. If you need more, add fields deliberately.
    """

    timeout_s: float = 15.0
    verify_ssl: bool = True
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    headers: Optional[Headers] = None
    cookies: Optional[Dict[str, str]] = None


class BaseEngine(ABC):
    """
    Common interface for all engines.

    - `get` is for normal fetches (HTTP or browser-based GET if engine chooses).
    - `get_rendered` is for JS rendering with an optional action DSL.
    """

    def __init__(self, *, name: str = "base") -> None:
        self.name = name

    @abstractmethod
    def get(self, url: str, *, ctx: Optional[EngineContext] = None) -> FetchResult:
        raise NotImplementedError

    def get_rendered(
        self,
        url: str,
        *,
        ctx: Optional[EngineContext] = None,
        actions: Optional[Sequence[Dict[str, Any]]] = None,
        wait_for: Optional[str] = None,
    ) -> FetchResult:
        """
        Engines that don't support rendering can override or raise.
        """
        return self.get(url, ctx=ctx)

    def close(self) -> None:
        """
        Allow engines to release resources (sessions, browser contexts).
        """
        return


# ---------------------------------------------------------------------
# Rate limiting + retries helpers
# ---------------------------------------------------------------------


class RateLimiter:
    """
    Simple process-local leaky bucket.

    - rps: requests per second (float)
    - min_delay_s + jitter_s are enforced between calls (per limiter)
    """

    def __init__(
        self,
        *,
        rps: Optional[float] = None,
        min_delay_s: Optional[float] = None,
        jitter_s: Optional[float] = None,
        burst: Optional[int] = None,
    ) -> None:
        self.rps = rps
        self.min_delay_s = min_delay_s or 0.0
        self.jitter_s = jitter_s or 0.0
        self.burst = burst or 1

        self._last_call_s: float = 0.0
        self._tokens: float = float(self.burst)
        self._last_refill_s: float = time.time()

    def _refill(self) -> None:
        now = time.time()
        if self.rps and self.rps > 0:
            dt = now - self._last_refill_s
            self._tokens = min(float(self.burst), self._tokens + dt * float(self.rps))
        self._last_refill_s = now

    def wait(self) -> None:
        # Enforce min delay + jitter between calls
        now = time.time()
        since_last = now - self._last_call_s
        target_delay = self.min_delay_s + (
            random.random() * self.jitter_s if self.jitter_s else 0.0
        )
        if target_delay > since_last:
            time.sleep(target_delay - since_last)

        # Token bucket throttle (if rps set)
        if self.rps and self.rps > 0:
            while True:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    break
                time.sleep(0.05)

        self._last_call_s = time.time()


def compute_backoff_s(
    attempt: int,
    *,
    mode: str = "exp",
    base_s: float = 0.5,
    max_s: float = 30.0,
    jitter: float = 0.25,
) -> float:
    """
    attempt: 1..N
    """
    if mode == "none":
        return 0.0
    if mode == "fixed":
        delay = base_s
    else:
        # exponential
        delay = base_s * (2 ** max(0, attempt - 1))

    delay = min(delay, max_s)
    if jitter > 0:
        delay = delay * (1.0 + (random.random() * 2 - 1) * jitter)  # +- jitter
    return max(0.0, delay)


def should_retry(status_code: Optional[int], retry_on_status: Sequence[int]) -> bool:
    if status_code is None:
        return True
    return int(status_code) in set(int(x) for x in retry_on_status)
