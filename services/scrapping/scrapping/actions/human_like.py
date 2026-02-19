"""Human-like interaction helpers.

These helpers are intentionally dependency-light and should work with:
- Playwright Page/Mouse/Keyboard
- Selenium-like drivers (if adapted)

They avoid "magic stealth claims" and focus on realistic pacing and variability.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class HumanLikeOptions:
    """Controls how "human" the interactions feel."""

    seed: int | None = None

    # delay ranges
    micro_delay_s: tuple[float, float] = (0.06, 0.25)
    short_delay_s: tuple[float, float] = (0.2, 0.9)
    medium_delay_s: tuple[float, float] = (0.8, 2.0)

    # scroll
    scroll_min_px: int = 180
    scroll_max_px: int = 700
    scroll_pause_s: tuple[float, float] = (0.12, 0.45)

    # mouse drift
    drift_steps: tuple[int, int] = (8, 22)
    drift_step_px: tuple[int, int] = (2, 18)
    drift_pause_s: tuple[float, float] = (0.01, 0.05)

    # typing
    type_delay_s: tuple[float, float] = (0.02, 0.09)
    typo_rate: float = 0.00  # keep 0 by default (typos can break forms)


class HumanLike:
    """Provide human-like timing and interaction patterns."""

    def __init__(self, opts: HumanLikeOptions | None = None) -> None:
        """Initialize the instance."""
        self.opts = opts or HumanLikeOptions()
        self._rnd = random.Random(self.opts.seed)

    # -------------------------
    # Delay helpers
    # -------------------------

    def sleep_range(self, lo_hi: tuple[float, float]) -> None:
        """Sleep for a random duration within the given range."""
        lo, hi = lo_hi
        if hi <= 0:
            return
        time.sleep(self._rnd.uniform(max(0.0, lo), max(0.0, hi)))

    def micro_pause(self) -> None:
        """Pause for a very short random duration."""
        self.sleep_range(self.opts.micro_delay_s)

    def short_pause(self) -> None:
        """Pause for a short random duration."""
        self.sleep_range(self.opts.short_delay_s)

    def medium_pause(self) -> None:
        """Pause for a medium random duration."""
        self.sleep_range(self.opts.medium_delay_s)

    def jitter(self, base_s: float, jitter_frac: float = 0.25) -> float:
        """Return base_s with +- jitter_frac randomness."""
        if base_s <= 0:
            return 0.0
        j = (self._rnd.random() * 2 - 1) * jitter_frac
        return max(0.0, base_s * (1.0 + j))

    # -------------------------
    # Scrolling
    # -------------------------

    def random_scroll_delta(self) -> int:
        """Generate a random scroll delta within configured range."""
        return self._rnd.randint(self.opts.scroll_min_px, self.opts.scroll_max_px)

    def scroll_wheel(
        self, page: Any, *, repeats: int = 5, direction: str = "down"
    ) -> None:
        """Scroll using mouse wheel events.

        Uses Playwright page.mouse.wheel(0, delta).
        For other drivers, wrap/adapter later.
        """
        repeats = max(1, int(repeats))
        for _ in range(repeats):
            delta = self.random_scroll_delta()
            if direction == "up":
                delta = -delta
            try:
                page.mouse.wheel(0, delta)
            except Exception:
                # fallback to JS scroll if mouse wheel isn't supported
                try:
                    page.evaluate("window.scrollBy(0, arguments[0])", delta)
                except Exception:
                    pass
            self.sleep_range(self.opts.scroll_pause_s)

    # -------------------------
    # Mouse drift
    # -------------------------

    def mouse_drift(self, page: Any, *, bounds: tuple[int, int] | None = None) -> None:
        """
        Small random drift to mimic human mouse movement.

        bounds: optional (width,height). If not provided we just move relative.
        """
        steps = self._rnd.randint(*self.opts.drift_steps)
        for _ in range(steps):
            dx = self._rnd.randint(*self.opts.drift_step_px) * (
                1 if self._rnd.random() > 0.5 else -1
            )
            dy = self._rnd.randint(*self.opts.drift_step_px) * (
                1 if self._rnd.random() > 0.5 else -1
            )

            try:
                # Playwright mouse.move expects absolute coords, so we do relative using current pos if available.
                # Playwright doesn't expose current position directly. We'll approximate by moving to a random location
                # if bounds are available, else do a tiny move around (0,0) which still triggers events sometimes.
                if bounds:
                    w, h = bounds
                    x = self._rnd.randint(0, max(1, w - 1))
                    y = self._rnd.randint(0, max(1, h - 1))
                    page.mouse.move(x, y)
                else:
                    page.mouse.move(max(0, dx), max(0, dy))
            except Exception:
                pass

            self.sleep_range(self.opts.drift_pause_s)

    # -------------------------
    # Typing
    # -------------------------

    def type_text(
        self, page: Any, selector: str, text: str, *, clear: bool = True
    ) -> None:
        """
        Types text with per-character delays.

        Playwright: page.fill / page.type
        """
        if clear:
            try:
                page.fill(selector, "")
                self.micro_pause()
            except Exception:
                pass

        # Prefer type() because it triggers key events more naturally than fill()
        try:
            for ch in text:
                page.type(
                    selector,
                    ch,
                    delay=int(self._rnd.uniform(*self.opts.type_delay_s) * 1000),
                )
            return
        except Exception:
            # fallback
            try:
                page.fill(selector, text)
            except Exception:
                pass
