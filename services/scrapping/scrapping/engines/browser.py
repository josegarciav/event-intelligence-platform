"""
scrapping.engines.browser

Playwright-based browser engine for rendering JS-heavy pages.
Supports a simple action DSL (scroll/click/wait_for/close_popup/type/hover).

Notes:
- This module uses optional dependency: playwright
- If playwright isn't installed, a clear ImportError is raised at runtime.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from scrapping.actions.browser_actions import ActionRunnerOptions, BrowserActionRunner
from scrapping.runtime.blocks import classify_blocks
from scrapping.runtime.resilience import RateLimiter, RetryPolicy
from scrapping.runtime.results import (
    EngineError,
    FetchResult,
    RequestMeta,
    ResponseMeta,
)

from .base import BaseEngine, EngineContext, Headers


@dataclass
class BrowserEngineOptions:
    browser_name: str = "chromium"  # chromium | firefox | webkit
    headless: bool = True
    nav_timeout_s: float = 30.0
    render_timeout_s: float = 20.0

    # retry
    max_retries: int = 2
    backoff_mode: str = "exp"

    # throttling
    rps: float | None = None
    burst: int | None = None
    min_delay_s: float = 0.0
    jitter_s: float = 0.25

    # context behavior
    user_agent: str | None = None
    viewport: dict[str, int] | None = field(
        default_factory=lambda: {"width": 1280, "height": 720}
    )
    locale: str = "en-US"
    timezone_id: str = "UTC"

    # resources
    block_images: bool = False
    block_fonts: bool = False
    block_resources: list[str] = field(default_factory=list)  # "image", "media", "font"

    # artifacts & debugging
    save_artifacts: bool = False
    artifacts_dir: str = "artifacts"
    trace: bool = False
    screenshot_on_error: bool = True


class BrowserEngine(BaseEngine):
    """
    Sync façade for BrowserEngine.
    If an asyncio loop is already running (e.g. Jupyter), it can use AsyncBrowserEngine
    via aget_rendered() or by running sync calls in a thread (Option B).
    """

    def __init__(self, *, options: BrowserEngineOptions | None = None) -> None:
        super().__init__(name="browser")
        self.options = options or BrowserEngineOptions()
        self._limiter = RateLimiter(
            rps=self.options.rps,
            burst=self.options.burst,
            min_delay_s=self.options.min_delay_s,
            jitter_s=self.options.jitter_s,
        )
        self._retry_policy = RetryPolicy(
            max_retries=self.options.max_retries,
            backoff_mode=self.options.backoff_mode,
        )

        # Action runner
        self._runner = BrowserActionRunner(
            options=ActionRunnerOptions(default_timeout_s=self.options.render_timeout_s)
        )

        self._pw = None
        self._browser = None
        self._context = None

        self._async_engine: AsyncBrowserEngine | None = None

    # -------------------------
    # Lifecycle
    # -------------------------

    def _ensure_started(self) -> None:
        if self._browser is not None:
            return

        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Playwright is missing. Install it with: pip install -e '.[browser]'"
            ) from e

        try:
            # Check if event loop is running. If so, sync_playwright().start() will fail.
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    # Check if we are in a thread other than the main thread.
                    # sync_playwright().start() often works in a thread even if the main thread has a loop.
                    import threading

                    if threading.current_thread() is threading.main_thread():
                        raise RuntimeError(
                            "Playwright Sync API cannot be used inside an asyncio loop (e.g. Jupyter). "
                            "Please use AsyncBrowserEngine or await engine.aget_rendered()."
                        )
            except RuntimeError:
                # No loop running, this is fine.
                pass

            self._pw = sync_playwright().start()
            browser_launcher = getattr(self._pw, self.options.browser_name)
            try:
                self._browser = browser_launcher.launch(headless=self.options.headless)
            except Exception as e:
                if (
                    "executable doesn't exist" in str(e)
                    or "not installed" in str(e).lower()
                ):
                    raise RuntimeError(
                        f"Browser binaries for {self.options.browser_name} are missing. "
                        "Run: playwright install"
                    ) from e
                raise

            # Create one long-lived context (cookies/session reuse)
            context_kwargs: dict[str, Any] = {
                "viewport": self.options.viewport,
                "locale": self.options.locale,
                "timezone_id": self.options.timezone_id,
            }
            if self.options.user_agent:
                context_kwargs["user_agent"] = self.options.user_agent

            self._context = self._browser.new_context(**context_kwargs)

            if self.options.trace:
                self._context.tracing.start(
                    screenshots=True, snapshots=True, sources=True
                )

        except Exception:
            self.close()
            raise

    def close(self) -> None:
        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.submit(self._close_sync).result()
        except RuntimeError:
            self._close_sync()

    def _close_sync(self) -> None:
        try:
            if self._context is not None:
                if self.options.trace:
                    try:
                        from pathlib import Path

                        out_dir = Path(self.options.artifacts_dir)
                        out_dir.mkdir(parents=True, exist_ok=True)
                        trace_path = out_dir / f"trace_{int(time.time())}.zip"
                        self._context.tracing.stop(path=str(trace_path))
                    except Exception:
                        pass
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

        if self._async_engine:
            # We cannot easily close it sync if it was used async.
            # User should call await close_async() if they used it.
            pass

    async def close_async(self) -> None:
        if self._async_engine:
            await self._async_engine.close()
            self._async_engine = None
        self.close()

    # -------------------------
    # Core API
    # -------------------------

    def get(self, url: str, *, ctx: EngineContext | None = None) -> FetchResult:
        # For browser engine, plain get just renders without actions.
        return self.get_rendered(url, ctx=ctx, actions=None, wait_for=None)

    def get_rendered(
        self,
        url: str,
        *,
        ctx: EngineContext | None = None,
        actions: Sequence[dict[str, Any]] | None = None,
        wait_for: str | None = None,
    ) -> FetchResult:
        # Check if we are in a notebook loop
        try:
            asyncio.get_running_loop()
            # If we reach here, we are in a loop.
            # We could use a thread pool to run the sync code, but it's better
            # to encourage aget_rendered in notebooks.
            # For compatibility, let's try to run it in a separate thread if called sync in a loop.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    self._get_rendered_sync,
                    url,
                    ctx=ctx,
                    actions=actions,
                    wait_for=wait_for,
                )
                return future.result()
        except RuntimeError:
            # No loop, just run it.
            return self._get_rendered_sync(
                url, ctx=ctx, actions=actions, wait_for=wait_for
            )

    async def aget_rendered(
        self,
        url: str,
        *,
        ctx: EngineContext | None = None,
        actions: Sequence[dict[str, Any]] | None = None,
        wait_for: str | None = None,
    ) -> FetchResult:
        if not self._async_engine:
            self._async_engine = AsyncBrowserEngine(options=self.options)
        return await self._async_engine.get_rendered(
            url, ctx=ctx, actions=actions, wait_for=wait_for
        )

    def _get_rendered_sync(
        self,
        url: str,
        *,
        ctx: EngineContext | None = None,
        actions: Sequence[dict[str, Any]] | None = None,
        wait_for: str | None = None,
    ) -> FetchResult:
        ctx = ctx or EngineContext()
        nav_timeout_s = float(ctx.timeout_s or self.options.nav_timeout_s)
        render_timeout_s = float(self.options.render_timeout_s)

        last_result: FetchResult | None = None
        trace: list[dict[str, Any]] = []

        for attempt in range(0, self._retry_policy.max_retries + 1):
            self._limiter.wait()
            t0 = time.time()

            req_meta = RequestMeta(
                method="RENDER",
                user_agent=self.options.user_agent,
            )

            try:
                self._ensure_started()
                assert self._context is not None

                page = self._context.new_page()
                page.set_default_timeout(nav_timeout_s * 1000)

                # Resource blocking
                block_types = set(self.options.block_resources)
                if self.options.block_images:
                    block_types.add("image")
                if self.options.block_fonts:
                    block_types.add("font")

                if block_types:

                    def _make_route_filter(types=block_types):
                        def _route_filter(route):
                            if route.request.resource_type in types:
                                return route.abort()
                            return route.continue_()
                        return _route_filter

                    page.route("**/*", _make_route_filter())

                # Navigate
                resp = page.goto(
                    url, wait_until="domcontentloaded", timeout=nav_timeout_s * 1000
                )
                status_code = resp.status if resp is not None else None
                final_url = page.url

                # Optional wait_for selector
                if wait_for:
                    page.wait_for_selector(wait_for, timeout=render_timeout_s * 1000)

                # Run action DSL
                action_results = []
                if actions:
                    action_results = self._runner.run(page, actions)

                # Grab content
                try:
                    html = page.content() or ""
                except Exception:
                    html = ""

                # Handle artifacts
                artifacts_meta = {}
                if self.options.save_artifacts:
                    artifacts_meta = self._save_page_artifacts(page, url, attempt, html)
                elapsed_ms = (time.time() - t0) * 1000

                resp_headers: Headers = {}
                try:
                    if resp is not None:
                        resp_headers = {str(k): str(v) for k, v in resp.headers.items()}
                except Exception:
                    pass

                result = FetchResult(
                    final_url=str(final_url),
                    status_code=int(status_code) if status_code is not None else None,
                    content_type=resp_headers.get("Content-Type") or "text/html",
                    text=html,
                    elapsed_ms=elapsed_ms,
                    request_meta=req_meta,
                    response_meta=ResponseMeta(headers=resp_headers),
                    engine_trace=trace
                    + [
                        {
                            "actions": [r.__dict__ for r in action_results],
                            "artifacts": artifacts_meta,
                        }
                    ],
                )

                result.block_signals = classify_blocks(result.text)

                page.close()

                if result.ok:
                    return result

                last_result = result
                trace.append(
                    {
                        "attempt": attempt,
                        "status": result.status_code,
                        "ok": False,
                        "artifacts": artifacts_meta,
                    }
                )

                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.compute_backoff_s(attempt + 1)
                    if delay > 0:
                        time.sleep(delay)
                    continue

                return result

            except Exception as e:
                elapsed_ms = (time.time() - t0) * 1000
                err = EngineError(
                    type=type(e).__name__, message=str(e), is_retryable=True
                )

                # Screenshot on error
                artifacts_meta = {}
                try:
                    if self.options.screenshot_on_error and self._context:
                        # try to get the page if it was created
                        pages = self._context.pages
                        if pages:
                            artifacts_meta = self._save_page_artifacts(
                                pages[-1], url, attempt, error=True
                            )
                except Exception:
                    pass

                result = FetchResult(
                    final_url=url,
                    elapsed_ms=elapsed_ms,
                    request_meta=req_meta,
                    text="",
                    error=err,
                    engine_trace=trace + [{"artifacts": artifacts_meta}],
                )

                last_result = result
                trace.append(
                    {
                        "attempt": attempt,
                        "error": err.type,
                        "ok": False,
                        "artifacts": artifacts_meta,
                    }
                )

                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.compute_backoff_s(attempt + 1)
                    if delay > 0:
                        time.sleep(delay)
                    continue

                return result

        return last_result or FetchResult(
            final_url=url,
            text="",
            error=EngineError(type="BrowserEngineError", message="Exhausted retries"),
            engine_trace=trace,
        )

    def _save_page_artifacts(
        self,
        page: Any,
        url: str,
        attempt: int,
        html: str | None = None,
        error: bool = False,
    ) -> dict[str, str]:
        import hashlib
        from pathlib import Path

        artifacts = {}
        out_dir = Path(self.options.artifacts_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        ts = int(time.time())
        base_name = f"{ts}_{url_hash}_att{attempt}"

        # HTML snapshot
        if html and self.options.save_artifacts:
            html_path = out_dir / f"{base_name}.html"
            html_path.write_text(html, encoding="utf-8")
            artifacts["html_path"] = str(html_path)

        # Screenshot
        if self.options.save_artifacts or (error and self.options.screenshot_on_error):
            ss_path = out_dir / f"{base_name}.png"
            try:
                page.screenshot(path=str(ss_path), full_page=True)
                artifacts["screenshot_path"] = str(ss_path)
            except Exception:
                pass

        return artifacts


class AsyncBrowserEngine(BaseEngine):
    """
    Playwright-based browser engine using Async API.
    """

    def __init__(self, *, options: BrowserEngineOptions | None = None) -> None:
        super().__init__(name="browser_async")
        self.options = options or BrowserEngineOptions()
        self._limiter = RateLimiter(
            rps=self.options.rps,
            burst=self.options.burst,
            min_delay_s=self.options.min_delay_s,
            jitter_s=self.options.jitter_s,
        )
        self._retry_policy = RetryPolicy(
            max_retries=self.options.max_retries,
            backoff_mode=self.options.backoff_mode,
        )

        self._pw = None
        self._browser = None
        self._context = None

        # Action runner
        self._runner = BrowserActionRunner(
            options=ActionRunnerOptions(default_timeout_s=self.options.render_timeout_s)
        )

    async def _ensure_started(self) -> None:
        if self._browser is not None:
            return

        try:
            from playwright.async_api import async_playwright  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Playwright is missing. Install it with: pip install -e '.[browser]'"
            ) from e

        try:
            self._pw = await async_playwright().start()
            browser_launcher = getattr(self._pw, self.options.browser_name)
            try:
                self._browser = await browser_launcher.launch(
                    headless=self.options.headless
                )
            except Exception as e:
                if (
                    "executable doesn't exist" in str(e)
                    or "not installed" in str(e).lower()
                ):
                    raise RuntimeError(
                        f"Browser binaries for {self.options.browser_name} are missing. "
                        "Run: playwright install"
                    ) from e
                raise

            context_kwargs: dict[str, Any] = {
                "viewport": self.options.viewport,
                "locale": self.options.locale,
                "timezone_id": self.options.timezone_id,
            }
            if self.options.user_agent:
                context_kwargs["user_agent"] = self.options.user_agent

            self._context = await self._browser.new_context(**context_kwargs)

            if self.options.trace:
                await self._context.tracing.start(
                    screenshots=True, snapshots=True, sources=True
                )

        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        try:
            if self._context is not None:
                if self.options.trace:
                    try:
                        from pathlib import Path

                        out_dir = Path(self.options.artifacts_dir)
                        out_dir.mkdir(parents=True, exist_ok=True)
                        trace_path = out_dir / f"trace_{int(time.time())}.zip"
                        await self._context.tracing.stop(path=str(trace_path))
                    except Exception:
                        pass
                await self._context.close()
        finally:
            self._context = None

        try:
            if self._browser is not None:
                await self._browser.close()
        finally:
            self._browser = None

        try:
            if self._pw is not None:
                await self._pw.stop()
        finally:
            self._pw = None

    async def get(
        self, url: str, *, ctx: EngineContext | None = None
    ) -> FetchResult:
        return await self.get_rendered(url, ctx=ctx, actions=None, wait_for=None)

    async def get_rendered(
        self,
        url: str,
        *,
        ctx: EngineContext | None = None,
        actions: Sequence[dict[str, Any]] | None = None,
        wait_for: str | None = None,
    ) -> FetchResult:
        ctx = ctx or EngineContext()
        nav_timeout_s = float(ctx.timeout_s or self.options.nav_timeout_s)
        render_timeout_s = float(self.options.render_timeout_s)

        last_result: FetchResult | None = None
        trace: list[dict[str, Any]] = []

        for attempt in range(0, self._retry_policy.max_retries + 1):
            await self._limiter.await_wait()
            t0 = time.time()

            req_meta = RequestMeta(
                method="RENDER",
                user_agent=self.options.user_agent,
            )

            try:
                await self._ensure_started()
                assert self._context is not None

                page = await self._context.new_page()
                page.set_default_timeout(nav_timeout_s * 1000)

                # Resource blocking
                block_types = set(self.options.block_resources)
                if self.options.block_images:
                    block_types.add("image")
                if self.options.block_fonts:
                    block_types.add("font")

                if block_types:

                    def _make_route_filter(types=block_types):
                        async def _route_filter(route):
                            if route.request.resource_type in types:
                                return await route.abort()
                            return await route.continue_()
                        return _route_filter

                    await page.route("**/*", _make_route_filter())

                # Navigate
                resp = await page.goto(
                    url, wait_until="domcontentloaded", timeout=nav_timeout_s * 1000
                )
                status_code = resp.status if resp is not None else None
                final_url = page.url

                # Optional wait_for selector
                if wait_for:
                    await page.wait_for_selector(
                        wait_for, timeout=render_timeout_s * 1000
                    )

                # Run actions
                action_results = []
                if actions:
                    action_results = await self._runner.arun(page, actions)

                # Grab content
                try:
                    html = await page.content() or ""
                except Exception:
                    html = ""

                # Handle artifacts
                artifacts_meta = {}
                if self.options.save_artifacts:
                    artifacts_meta = await self._asave_page_artifacts(
                        page, url, attempt, html
                    )
                elapsed_ms = (time.time() - t0) * 1000

                resp_headers: Headers = {}
                try:
                    if resp is not None:
                        resp_headers = {str(k): str(v) for k, v in resp.headers.items()}
                except Exception:
                    pass

                result = FetchResult(
                    final_url=str(final_url),
                    status_code=int(status_code) if status_code is not None else None,
                    content_type=resp_headers.get("Content-Type") or "text/html",
                    text=html,
                    elapsed_ms=elapsed_ms,
                    request_meta=req_meta,
                    response_meta=ResponseMeta(headers=resp_headers),
                    engine_trace=trace
                    + [
                        {
                            "actions": [r.__dict__ for r in action_results],
                            "artifacts": artifacts_meta,
                        }
                    ],
                )

                result.block_signals = classify_blocks(result.text)

                await page.close()

                if result.ok:
                    return result

                last_result = result
                trace.append(
                    {
                        "attempt": attempt,
                        "status": result.status_code,
                        "ok": False,
                        "artifacts": artifacts_meta,
                    }
                )

                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.compute_backoff_s(attempt + 1)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue

                return result

            except Exception as e:
                elapsed_ms = (time.time() - t0) * 1000
                err = EngineError(
                    type=type(e).__name__, message=str(e), is_retryable=True
                )

                # Screenshot on error
                artifacts_meta = {}
                try:
                    if self.options.screenshot_on_error and self._context:
                        pages = self._context.pages
                        if pages:
                            artifacts_meta = await self._asave_page_artifacts(
                                pages[-1], url, attempt, error=True
                            )
                except Exception:
                    pass

                result = FetchResult(
                    final_url=url,
                    elapsed_ms=elapsed_ms,
                    request_meta=req_meta,
                    text="",
                    error=err,
                    engine_trace=trace + [{"artifacts": artifacts_meta}],
                )

                last_result = result
                trace.append(
                    {
                        "attempt": attempt,
                        "error": err.type,
                        "ok": False,
                        "artifacts": artifacts_meta,
                    }
                )

                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.compute_backoff_s(attempt + 1)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue

                return result

        return last_result or FetchResult(
            final_url=url,
            text="",
            error=EngineError(
                type="AsyncBrowserEngineError", message="Exhausted retries"
            ),
            engine_trace=trace,
        )

    async def _asave_page_artifacts(
        self,
        page: Any,
        url: str,
        attempt: int,
        html: str | None = None,
        error: bool = False,
    ) -> dict[str, str]:
        import hashlib
        from pathlib import Path

        artifacts = {}
        out_dir = Path(self.options.artifacts_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        ts = int(time.time())
        base_name = f"{ts}_{url_hash}_att{attempt}"

        # HTML snapshot
        if html and self.options.save_artifacts:
            html_path = out_dir / f"{base_name}.html"
            html_path.write_text(html, encoding="utf-8")
            artifacts["html_path"] = str(html_path)

        # Screenshot
        if self.options.save_artifacts or (error and self.options.screenshot_on_error):
            ss_path = out_dir / f"{base_name}.png"
            try:
                await page.screenshot(path=str(ss_path), full_page=True)
                artifacts["screenshot_path"] = str(ss_path)
            except Exception:
                pass

        return artifacts
