"""
scrapping.engines.base

Engine interfaces + shared primitives.

Goals:
- One standard response shape across HTTP and Browser engines.
- Built-in rate limiting + retry helpers (stdlib-only).
- Engines remain swappable: http | browser | hybrid.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from scrapping.runtime.results import FetchResult

Headers = dict[str, str]


@dataclass
class EngineContext:
    """
    The minimum execution context engines may need.
    Keep it small. If you need more, add fields deliberately.
    """

    timeout_s: float = 15.0
    verify_ssl: bool = True
    user_agent: str | None = None
    proxy: str | None = None
    headers: Headers | None = None
    cookies: dict[str, str] | None = None


class BaseEngine(ABC):
    """
    Common interface for all engines.

    - `get` is for normal fetches (HTTP or browser-based GET if engine chooses).
    - `get_rendered` is for JS rendering with an optional action DSL.
    """

    def __init__(self, *, name: str = "base") -> None:
        self.name = name

    @abstractmethod
    def get(self, url: str, *, ctx: EngineContext | None = None) -> FetchResult:
        raise NotImplementedError

    def get_rendered(
        self,
        url: str,
        *,
        ctx: EngineContext | None = None,
        actions: Sequence[dict[str, Any]] | None = None,
        wait_for: str | None = None,
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
