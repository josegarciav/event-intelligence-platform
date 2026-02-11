"""
scrapping.engines.hybrid

Hybrid engine:
- uses HttpEngine for fast fetches
- uses BrowserEngine for rendering/detail pages or as fallback
- consistent output with full trace
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .base import BaseEngine, EngineContext, FetchResult
from .browser import BrowserEngine, BrowserEngineOptions
from .http import HttpEngine, HttpEngineOptions


@dataclass
class HybridEngineOptions:
    http: HttpEngineOptions = field(default_factory=HttpEngineOptions)
    browser: BrowserEngineOptions = field(default_factory=BrowserEngineOptions)

    # default routing for .get()
    default_get: str = "http"  # "http" or "browser"

    # fallback policy
    fallback_to_browser: bool = True
    min_text_len: int = 200  # If HTTP returns less text, try browser


class HybridEngine(BaseEngine):
    def __init__(self, *, options: HybridEngineOptions | None = None) -> None:
        super().__init__(name="hybrid")
        self.options = options or HybridEngineOptions()
        self.http = HttpEngine(options=self.options.http)
        self.browser = BrowserEngine(options=self.options.browser)

    def close(self) -> None:
        self.http.close()
        self.browser.close()

    def get(self, url: str, *, ctx: EngineContext | None = None) -> FetchResult:
        if self.options.default_get == "browser":
            return self.browser.get(url, ctx=ctx)

        # Try HTTP
        res = self.http.get(url, ctx=ctx)

        # Fallback check
        if self.options.fallback_to_browser:
            should_fallback = False
            if not res.ok:
                should_fallback = True
            elif res.block_signals:
                should_fallback = True
            elif len(res.text or "") < self.options.min_text_len:
                should_fallback = True

            if should_fallback:
                res_browser = self.browser.get(url, ctx=ctx)
                # Combine traces
                res_browser.engine_trace = [
                    {
                        "engine": "http",
                        "result": "fallback_triggered",
                        "http_res": res.status_code,
                    }
                ] + res_browser.engine_trace
                return res_browser

        return res

    def get_rendered(
        self,
        url: str,
        *,
        ctx: EngineContext | None = None,
        actions: Sequence[dict[str, Any]] | None = None,
        wait_for: str | None = None,
    ) -> FetchResult:
        # get_rendered always goes to browser
        return self.browser.get_rendered(
            url, ctx=ctx, actions=actions, wait_for=wait_for
        )
