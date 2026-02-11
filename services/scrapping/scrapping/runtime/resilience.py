"""
scrapping.runtime.resilience

Shared resilience utilities: retries, rate limiting.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    backoff_mode: str = "exp"  # exp | fixed | none
    base_delay_s: float = 0.5
    max_delay_s: float = 30.0
    jitter: float = 0.25
    retry_on_status: tuple[int, ...] = (408, 429, 500, 502, 503, 504)

    def compute_backoff_s(self, attempt: int) -> float:
        """
        attempt: 1..N
        """
        if self.backoff_mode == "none":
            return 0.0
        if self.backoff_mode == "fixed":
            delay = self.base_delay_s
        else:
            # exponential
            delay = self.base_delay_s * (2 ** max(0, attempt - 1))

        delay = min(delay, self.max_delay_s)
        if self.jitter > 0:
            delay = delay * (1.0 + (random.random() * 2 - 1) * self.jitter)  # +- jitter
        return max(0.0, delay)


class RateLimiter:
    """
    Simple process-local leaky bucket.
    """

    def __init__(
        self,
        *,
        rps: float | None = None,
        min_delay_s: float | None = None,
        jitter_s: float | None = None,
        burst: int | None = None,
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

    async def await_wait(self) -> None:
        # Enforce min delay + jitter between calls
        now = time.time()
        since_last = now - self._last_call_s
        target_delay = self.min_delay_s + (
            random.random() * self.jitter_s if self.jitter_s else 0.0
        )
        if target_delay > since_last:
            await asyncio.sleep(target_delay - since_last)

        # Token bucket throttle (if rps set)
        if self.rps and self.rps > 0:
            while True:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    break
                await asyncio.sleep(0.05)

        self._last_call_s = time.time()
