"""Declarative action runner for browser pages.

The goal:
- Make browser behavior configurable via JSON:
  actions: [
    {"type":"close_popup","selector":"button.cookie-close"},
    {"type":"scroll","params":{"repeat":6,"min_px":250,"max_px":600}},
    {"type":"click","selector":"button.load-more","params":{"repeat":2}},
    {"type":"wait_for","selector":".results","params":{"timeout_s":10}}
  ]

This runner supports Playwright page today. Later we can add adapters
for SeleniumBase with the same action schema.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .human_like import HumanLike, HumanLikeOptions


@dataclass
class ActionResult:
    """Hold the result of a single browser action."""

    type: str
    ok: bool = True
    elapsed_ms: float = 0.0
    error: str | None = None
    screenshot_path: str | None = None


@dataclass
class ActionRunnerOptions:
    """Behavior for how strictly we treat failures."""

    strict: bool = False  # if True, unknown actions or failures raise
    default_timeout_s: float = 20.0

    # human-like behavior settings
    human: HumanLikeOptions = field(default_factory=HumanLikeOptions)


class BrowserActionRunner:
    """Execute browser actions from a declarative action list."""

    def __init__(self, *, options: ActionRunnerOptions | None = None) -> None:
        """Initialize the instance."""
        self.options = options or ActionRunnerOptions()
        self.human = HumanLike(self.options.human)

    async def arun(self, page: Any, actions: Sequence[dict[str, Any]]) -> list[ActionResult]:
        """Execute a list of action dicts on an Async Playwright `page`."""
        results = []
        for idx, act in enumerate(actions):
            atype = str(act.get("type", "")).strip()
            selector = act.get("selector")
            params = act.get("params") or {}
            timeout_s = float(act.get("timeout_s", self.options.default_timeout_s))

            t0 = time.time()
            res = ActionResult(type=atype)

            try:
                if atype == "wait_for":
                    if selector:
                        await page.wait_for_selector(selector, timeout=int(timeout_s * 1000))

                elif atype == "click":
                    if selector:
                        repeat = int(params.get("repeat", 1))
                        pause = float(params.get("pause_s", 0.0))
                        for _ in range(max(1, repeat)):
                            await asyncio.sleep(self.human.opts.micro_pause_s)
                            await page.click(selector, timeout=int(timeout_s * 1000))
                            if pause > 0:
                                await asyncio.sleep(self.human.jitter(pause, 0.25))

                elif atype == "hover":
                    if selector:
                        await asyncio.sleep(self.human.opts.micro_pause_s)
                        await page.hover(selector, timeout=int(timeout_s * 1000))

                elif atype == "type":
                    if selector:
                        text = str(params.get("text", ""))
                        clear = bool(params.get("clear", True))
                        if clear:
                            await page.fill(selector, "")
                        await page.type(selector, text)
                        await asyncio.sleep(self.human.opts.short_pause_s)

                elif atype == "close_popup":
                    if selector:
                        try:
                            await page.click(selector, timeout=1500)
                        except Exception:
                            pass

                elif atype == "scroll":
                    repeat = int(params.get("repeat", 5))
                    direction = str(params.get("direction", "down"))
                    mode = str(params.get("mode", "random"))
                    if mode == "fixed":
                        fixed_px = int(params.get("fixed_px", 500))
                        for _ in range(max(1, repeat)):
                            delta = fixed_px if direction != "up" else -fixed_px
                            await page.mouse.wheel(0, delta)
                            await asyncio.sleep(self.human.opts.micro_pause_s)
                    else:
                        # random
                        for _ in range(max(1, repeat)):
                            delta = random.randint(
                                self.human.opts.scroll_min_px,
                                self.human.opts.scroll_max_px,
                            )
                            if direction == "up":
                                delta = -delta
                            await page.mouse.wheel(0, delta)
                            await asyncio.sleep(self.human.opts.micro_pause_s)

                elif atype == "sleep":
                    seconds = float(params.get("seconds", 0.0))
                    if seconds > 0:
                        await asyncio.sleep(self.human.jitter(seconds, 0.25))

                else:
                    self._unknown(atype, idx)

            except Exception as e:
                res.ok = False
                res.error = str(e)
                if self.options.strict:
                    res.elapsed_ms = (time.time() - t0) * 1000
                    results.append(res)
                    raise
                await asyncio.sleep(self.human.opts.micro_pause_s)

            res.elapsed_ms = (time.time() - t0) * 1000
            results.append(res)
        return results

    def run(self, page: Any, actions: Sequence[dict[str, Any]]) -> list[ActionResult]:
        """Execute a list of action dicts on a Playwright-like page."""
        results = []
        for idx, act in enumerate(actions):
            atype = str(act.get("type", "")).strip()
            selector = act.get("selector")
            params = act.get("params") or {}
            timeout_s = float(act.get("timeout_s", self.options.default_timeout_s))

            t0 = time.time()
            res = ActionResult(type=atype)

            try:
                if atype == "wait_for":
                    self._wait_for(page, selector, params, timeout_s)

                elif atype == "click":
                    self._click(page, selector, params, timeout_s)

                elif atype == "hover":
                    self._hover(page, selector, timeout_s)

                elif atype == "type":
                    self._type(page, selector, params)

                elif atype == "close_popup":
                    self._close_popup(page, selector)

                elif atype == "scroll":
                    self._scroll(page, params)

                elif atype == "sleep":
                    self._sleep(params)

                elif atype == "mouse_drift":
                    self._mouse_drift(page, params)

                else:
                    self._unknown(atype, idx)

            except Exception as e:
                res.ok = False
                res.error = str(e)
                if self.options.strict:
                    res.elapsed_ms = (time.time() - t0) * 1000
                    results.append(res)
                    raise

                # best-effort mode: swallow, but keep a tiny delay to reduce aggressive retries
                self.human.micro_pause()

            res.elapsed_ms = (time.time() - t0) * 1000
            results.append(res)
        return results

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _wait_for(
        self, page: Any, selector: str | None, params: dict[str, Any], timeout_s: float
    ) -> None:
        if not selector:
            if self.options.strict:
                raise ValueError("wait_for requires selector")
            return
        page.wait_for_selector(selector, timeout=int(timeout_s * 1000))

    def _click(
        self, page: Any, selector: str | None, params: dict[str, Any], timeout_s: float
    ) -> None:
        if not selector:
            if self.options.strict:
                raise ValueError("click requires selector")
            return
        repeat = int(params.get("repeat", 1))
        pause = float(params.get("pause_s", 0.0))

        for _ in range(max(1, repeat)):
            # slight human delay before clicking
            self.human.micro_pause()
            page.click(selector, timeout=int(timeout_s * 1000))
            if pause > 0:
                import time

                time.sleep(self.human.jitter(pause, 0.25))

    def _hover(self, page: Any, selector: str | None, timeout_s: float) -> None:
        if not selector:
            if self.options.strict:
                raise ValueError("hover requires selector")
            return
        self.human.micro_pause()
        page.hover(selector, timeout=int(timeout_s * 1000))

    def _type(self, page: Any, selector: str | None, params: dict[str, Any]) -> None:
        if not selector:
            if self.options.strict:
                raise ValueError("type requires selector")
            return
        text = str(params.get("text", ""))
        clear = bool(params.get("clear", True))
        self.human.type_text(page, selector, text, clear=clear)
        self.human.short_pause()

    def _close_popup(self, page: Any, selector: str | None) -> None:
        """Click a popup selector with best-effort; ignore if not found.

        Useful for cookie banners.
        """
        if not selector:
            if self.options.strict:
                raise ValueError("close_popup requires selector")
            return
        try:
            page.click(selector, timeout=1500)
            self.human.micro_pause()
        except Exception:
            return

    def _scroll(self, page: Any, params: dict[str, Any]) -> None:
        """Scroll the page with configurable parameters.

        params:
          - repeat: int
          - direction: down|up
          - mode: random|fixed
          - min_px/max_px for random
          - fixed_px for fixed
        """
        repeat = int(params.get("repeat", 5))
        direction = str(params.get("direction", "down"))

        mode = str(params.get("mode", "random"))
        if mode == "fixed":
            fixed_px = int(params.get("fixed_px", 500))
            try:
                for _ in range(max(1, repeat)):
                    delta = fixed_px if direction != "up" else -fixed_px
                    page.mouse.wheel(0, delta)
                    self.human.micro_pause()
                return
            except Exception:
                pass

        # random mode
        # allow overriding the default ranges
        min_px = int(params.get("min_px", self.human.opts.scroll_min_px))
        max_px = int(params.get("max_px", self.human.opts.scroll_max_px))
        old_min, old_max = self.human.opts.scroll_min_px, self.human.opts.scroll_max_px
        self.human.opts.scroll_min_px, self.human.opts.scroll_max_px = min_px, max_px
        try:
            self.human.scroll_wheel(page, repeats=repeat, direction=direction)
        finally:
            self.human.opts.scroll_min_px, self.human.opts.scroll_max_px = (
                old_min,
                old_max,
            )

    def _sleep(self, params: dict[str, Any]) -> None:
        """Sleep for a specified duration.

        params:
          - seconds: float (exact)
          - range_s: [lo,hi] (random range)
          - preset: micro|short|medium
        """
        import time

        if "preset" in params:
            preset = str(params["preset"])
            if preset == "micro":
                self.human.micro_pause()
            elif preset == "short":
                self.human.short_pause()
            else:
                self.human.medium_pause()
            return

        if (
            "range_s" in params
            and isinstance(params["range_s"], list | tuple)
            and len(params["range_s"]) == 2
        ):
            lo, hi = float(params["range_s"][0]), float(params["range_s"][1])
            self.human.sleep_range((lo, hi))
            return

        seconds = float(params.get("seconds", 0.0))
        if seconds > 0:
            time.sleep(self.human.jitter(seconds, 0.25))

    def _mouse_drift(self, page: Any, params: dict[str, Any]) -> None:
        """Drift the mouse cursor randomly.

        params:
          - bounds: [w,h] optional
        """
        bounds = None
        b = params.get("bounds")
        if isinstance(b, list | tuple) and len(b) == 2:
            bounds = (int(b[0]), int(b[1]))
        self.human.mouse_drift(page, bounds=bounds)

    def _unknown(self, atype: str, idx: int) -> None:
        if self.options.strict:
            raise ValueError(f"Unknown action type at index {idx}: {atype}")
        # ignore unknown actions for forward compatibility
        return
