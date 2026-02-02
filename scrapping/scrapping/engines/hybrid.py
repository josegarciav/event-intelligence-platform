"""
scrapping.engines.hybrid

Hybrid engine:
- uses HttpEngine for fast fetches (listing pages, APIs)
- uses BrowserEngine for rendering/detail pages when needed

You choose which method to call:
- get() can default to HTTP for speed
- get_rendered() delegates to BrowserEngine
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from .base import BaseEngine, EngineContext, FetchResult
from .http import HttpEngine, HttpEngineOptions
from .browser import BrowserEngine, BrowserEngineOptions


@dataclass
class HybridEngineOptions:
    http: HttpEngineOptions = HttpEngineOptions()
    browser: BrowserEngineOptions = BrowserEngineOptions()
    # default routing for .get()
    default_get: str = "http"  # "http" or "browser"


class HybridEngine(BaseEngine):
    def __init__(self, *, options: Optional[HybridEngineOptions] = None) -> None:
        super().__init__(name="hybrid")
        self.options = options or HybridEngineOptions()
        self.http = HttpEngine(options=self.options.http)
        self.browser = BrowserEngine(options=self.options.browser)

    def close(self) -> None:
        self.http.close()
        self.browser.close()

    def get(self, url: str, *, ctx: Optional[EngineContext] = None) -> FetchResult:
        if self.options.default_get == "browser":
            return self.browser.get(url, ctx=ctx)
        return self.http.get(url, ctx=ctx)

    def get_rendered(
        self,
        url: str,
        *,
        ctx: Optional[EngineContext] = None,
        actions: Optional[Sequence[Dict[str, Any]]] = None,
        wait_for: Optional[str] = None,
    ) -> FetchResult:
        return self.browser.get_rendered(url, ctx=ctx, actions=actions, wait_for=wait_for)
