"""Requests-based HTTP engine.

Features:
- session reuse + connection pooling
- retry with backoff (shared policy)
- rate limiting (shared bucket)
- basic proxy support
- redirect tracking
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

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
class HttpEngineOptions:
    """Configuration options for the HTTP engine."""

    timeout_s: float = 15.0
    verify_ssl: bool = True

    # retry
    max_retries: int = 3
    backoff_mode: str = "exp"  # exp | fixed | none
    base_delay_s: float = 0.5
    retry_on_status: tuple[int, ...] = (408, 429, 500, 502, 503, 504)

    # rate limit
    rps: float | None = None
    burst: int | None = None
    min_delay_s: float | None = None
    jitter_s: float | None = None

    # headers
    user_agent: str | None = None

    # pool
    pool_connections: int = 10
    pool_maxsize: int = 20


class HttpEngine(BaseEngine):
    """HTTP engine using the requests library."""

    def __init__(self, *, options: HttpEngineOptions | None = None) -> None:
        """Initialize the instance."""
        super().__init__(name="http")
        self.options = options or HttpEngineOptions()
        self._session = requests.Session()

        adapter = requests.adapters.HTTPAdapter(
            pool_connections=self.options.pool_connections,
            pool_maxsize=self.options.pool_maxsize,
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        self._limiter = RateLimiter(
            rps=self.options.rps,
            burst=self.options.burst,
            min_delay_s=self.options.min_delay_s,
            jitter_s=self.options.jitter_s,
        )
        self._retry_policy = RetryPolicy(
            max_retries=self.options.max_retries,
            backoff_mode=self.options.backoff_mode,
            base_delay_s=self.options.base_delay_s,
            retry_on_status=self.options.retry_on_status,
        )

    def close(self) -> None:
        """Perform the operation."""
        try:
            self._session.close()
        except Exception:
            pass

    def get(self, url: str, *, ctx: EngineContext | None = None) -> FetchResult:
        """Perform the operation."""
        ctx = ctx or EngineContext()
        timeout_s = float(ctx.timeout_s or self.options.timeout_s)
        verify_ssl = bool(ctx.verify_ssl if ctx.verify_ssl is not None else self.options.verify_ssl)

        headers: Headers = {}
        if self.options.user_agent:
            headers["User-Agent"] = self.options.user_agent
        if ctx.user_agent:
            headers["User-Agent"] = ctx.user_agent
        if ctx.headers:
            headers.update({str(k): str(v) for k, v in ctx.headers.items()})

        proxies: dict[str, str] | None = None
        if ctx.proxy:
            proxies = {"http": ctx.proxy, "https": ctx.proxy}

        cookies = ctx.cookies or None

        last_result: FetchResult | None = None
        trace: list[dict[str, Any]] = []

        for attempt in range(0, self._retry_policy.max_retries + 1):
            self._limiter.wait()

            req_meta = RequestMeta(
                method="GET",
                headers=headers,
                proxy=ctx.proxy,
                user_agent=headers.get("User-Agent"),
            )

            t0 = time.time()
            try:
                resp = self._session.get(
                    url,
                    timeout=timeout_s,
                    verify=verify_ssl,
                    headers=headers,
                    cookies=cookies,
                    proxies=proxies,
                    allow_redirects=True,
                )
                elapsed_ms = (time.time() - t0) * 1000

                # Extract info
                resp_headers = {str(k): str(v) for k, v in resp.headers.items()}
                redirects = [str(r.url) for r in resp.history]

                text = ""
                try:
                    resp.encoding = resp.encoding or "utf-8"
                    text = resp.text or ""
                except Exception:
                    text = ""

                result = FetchResult(
                    final_url=str(resp.url),
                    status_code=int(resp.status_code),
                    content_type=resp_headers.get("Content-Type"),
                    body_bytes=resp.content,
                    text=text,
                    elapsed_ms=elapsed_ms,
                    request_meta=req_meta,
                    response_meta=ResponseMeta(headers=resp_headers, redirects=redirects),
                    engine_trace=trace,
                )

                # Block detection
                result.block_signals = classify_blocks(result.text)

                if result.ok:
                    return result

                last_result = result
                trace.append({"attempt": attempt, "status": result.status_code, "ok": False})

                # Check if retryable
                if attempt < self._retry_policy.max_retries and result.is_retryable:
                    delay = self._retry_policy.compute_backoff_s(attempt + 1)
                    if delay > 0:
                        time.sleep(delay)
                    continue

                return result

            except requests.RequestException as e:
                elapsed_ms = (time.time() - t0) * 1000
                err = EngineError(type=type(e).__name__, message=str(e), is_retryable=True)

                result = FetchResult(
                    final_url=url,
                    elapsed_ms=elapsed_ms,
                    request_meta=req_meta,
                    error=err,
                    engine_trace=trace,
                )

                last_result = result
                trace.append({"attempt": attempt, "error": err.type, "ok": False})

                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.compute_backoff_s(attempt + 1)
                    if delay > 0:
                        time.sleep(delay)
                    continue

                return result

        return last_result or FetchResult(
            final_url=url,
            error=EngineError(type="HttpEngineError", message="Exhausted retries"),
            engine_trace=trace,
        )
