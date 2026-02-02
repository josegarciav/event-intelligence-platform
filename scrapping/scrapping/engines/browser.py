"""
scrapping.engines.browser

Playwright-based browser engine for rendering JS-heavy pages.
Supports a simple action DSL (scroll/click/wait_for/close_popup/type/hover).

Notes:
- This module uses optional dependency: playwright
- If playwright isn't installed, a clear ImportError is raised at runtime.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from .base import BaseEngine, EngineContext, FetchResult, FetchTimings, Headers, RateLimiter, compute_backoff_s


@dataclass
class BrowserEngineOptions:
    browser_name: str = "chromium"  # chromium | firefox | webkit
    headless: bool = True
    timeout_s: float = 20.0

    # retry
    max_retries: int = 2
    backoff_mode: str = "exp"

    # throttling
    rps: Optional[float] = None
    burst: Optional[int] = None
    min_delay_s: Optional[float] = 0.0
    jitter_s: Optional[float] = 0.25

    # behavior
    user_agent: Optional[str] = None


class BrowserEngine(BaseEngine):
    def __init__(self, *, options: Optional[BrowserEngineOptions] = None) -> None:
        super().__init__(name="browser")
        self.options = options or BrowserEngineOptions()
        self._limiter = RateLimiter(
            rps=self.options.rps,
            burst=self.options.burst,
            min_delay_s=self.options.min_delay_s,
            jitter_s=self.options.jitter_s,
        )

        self._pw = None
        self._browser = None
        self._context = None

    # -------------------------
    # Lifecycle
    # -------------------------

    def _ensure_started(self) -> None:
        if self._browser is not None:
            return

        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as e:
            raise ImportError(
                "playwright is required for BrowserEngine. "
                "Install it with: pip install playwright && playwright install"
            ) from e

        self._pw = sync_playwright().start()
        browser_launcher = getattr(self._pw, self.options.browser_name)

        self._browser = browser_launcher.launch(headless=self.options.headless)

        # Create one long-lived context (cookies/session reuse)
        context_kwargs: Dict[str, Any] = {}
        if self.options.user_agent:
            context_kwargs["user_agent"] = self.options.user_agent
        self._context = self._browser.new_context(**context_kwargs)

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        finally:
            self._context = None

        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._browser = None

        try:
            if self._pw is not None:
                self._pw.stop()
        finally:
            self._pw = None

    # -------------------------
    # Core API
    # -------------------------

    def get(self, url: str, *, ctx: Optional[EngineContext] = None) -> FetchResult:
        # For browser engine, plain get just renders without actions.
        return self.get_rendered(url, ctx=ctx, actions=None, wait_for=None)

    def get_rendered(
        self,
        url: str,
        *,
        ctx: Optional[EngineContext] = None,
        actions: Optional[Sequence[Dict[str, Any]]] = None,
        wait_for: Optional[str] = None,
    ) -> FetchResult:
        ctx = ctx or EngineContext()
        timeout_s = float(ctx.timeout_s or self.options.timeout_s)

        last_err: Optional[FetchResult] = None

        for attempt in range(0, self.options.max_retries + 1):
            self._limiter.wait()
            started = time.time()

            try:
                self._ensure_started()
                assert self._context is not None

                page = self._context.new_page()
                if ctx.user_agent:
                    # If per-request UA is needed, create a new context.
                    # Keeping simple: only support global UA in options.
                    pass

                page.set_default_timeout(timeout_s * 1000)

                # Navigate
                resp = page.goto(url, wait_until="domcontentloaded")
                status_code = resp.status if resp is not None else None
                final_url = page.url

                # Optional wait_for selector
                if wait_for:
                    page.wait_for_selector(wait_for, timeout=timeout_s * 1000)

                # Run action DSL
                if actions:
                    self._run_actions(page, actions, timeout_s=timeout_s)

                # Grab content
                html = page.content()
                ended = time.time()

                headers: Headers = {}
                try:
                    if resp is not None:
                        headers = {str(k): str(v) for k, v in resp.headers.items()}
                except Exception:
                    headers = {}

                ok = True
                if status_code is not None and int(status_code) >= 400:
                    ok = False

                page.close()

                result = FetchResult(
                    ok=ok,
                    final_url=str(final_url),
                    status_code=int(status_code) if status_code is not None else None,
                    text=html,
                    headers=headers,
                    timings=FetchTimings(started_at_s=started, ended_at_s=ended),
                )

                if result.ok:
                    return result

                # retry on render failures / 4xx/5xx is source-specific; keep conservative
                if attempt < self.options.max_retries:
                    delay = compute_backoff_s(attempt + 1, mode=self.options.backoff_mode)
                    if delay > 0:
                        time.sleep(delay)
                    last_err = result
                    continue

                return result

            except Exception as e:
                ended = time.time()
                result = FetchResult(
                    ok=False,
                    final_url=url,
                    status_code=None,
                    text=None,
                    headers={},
                    timings=FetchTimings(started_at_s=started, ended_at_s=ended),
                    error_type=type(e).__name__,
                    error_message=str(e),
                )

                # best-effort cleanup of a bad page
                try:
                    if self._context is not None:
                        # nothing required here; page should be GC'ed, but safe
                        pass
                except Exception:
                    pass

                if attempt < self.options.max_retries:
                    delay = compute_backoff_s(attempt + 1, mode=self.options.backoff_mode)
                    if delay > 0:
                        time.sleep(delay)
                    last_err = result
                    continue

                return result

        return last_err or FetchResult(
            ok=False,
            final_url=url,
            status_code=None,
            text=None,
            headers={},
            timings=FetchTimings(started_at_s=0.0, ended_at_s=0.0),
            error_type="BrowserEngineError",
            error_message="exhausted retries",
        )

    # -------------------------
    # Action DSL
    # -------------------------

    def _run_actions(self, page: Any, actions: Sequence[Dict[str, Any]], *, timeout_s: float) -> None:
        """
        actions: list of dict like:
          {"type":"scroll", "params":{"min_px":200,"max_px":450,"repeat":6}}
          {"type":"click", "selector":"button.load-more", "params":{"repeat":2}}
          {"type":"wait_for", "selector":".results", "params":{"timeout_s":10}}
        """
        for act in actions:
            atype = str(act.get("type", "")).strip()
            selector = act.get("selector")
            params = act.get("params") or {}
            t_override = act.get("timeout_s", None)
            t_s = float(t_override) if t_override is not None else timeout_s

            if atype == "wait_for":
                if not selector:
                    continue
                page.wait_for_selector(selector, timeout=t_s * 1000)

            elif atype == "click":
                if not selector:
                    continue
                repeat = int(params.get("repeat", 1))
                for _ in range(max(1, repeat)):
                    page.click(selector, timeout=t_s * 1000)

            elif atype == "hover":
                if not selector:
                    continue
                page.hover(selector, timeout=t_s * 1000)

            elif atype == "type":
                if not selector:
                    continue
                text = str(params.get("text", ""))
                clear = bool(params.get("clear", False))
                if clear:
                    page.fill(selector, "", timeout=t_s * 1000)
                page.type(selector, text, timeout=t_s * 1000)

            elif atype == "close_popup":
                # best-effort click; ignore failures
                if not selector:
                    continue
                try:
                    page.click(selector, timeout=min(2.0, t_s) * 1000)
                except Exception:
                    pass

            elif atype == "scroll":
                mode = str(params.get("mode", "random"))
                repeat = int(params.get("repeat", 5))
                min_px = int(params.get("min_px", 200))
                max_px = int(params.get("max_px", 600))
                sleep_s = float(params.get("sleep_s", 0.2))

                import random
                for _ in range(max(1, repeat)):
                    if mode == "down":
                        delta = max_px
                    elif mode == "up":
                        delta = -max_px
                    else:
                        delta = random.randint(min_px, max_px)
                    page.mouse.wheel(0, delta)
                    time.sleep(sleep_s)

            else:
                # Unknown action type: ignore for forward compatibility
                continue
