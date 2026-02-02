"""
scrapping.engines.http

Requests-based engine:
- session reuse
- retry with backoff
- rate limiting
- basic proxy support
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from .base import (
    BaseEngine,
    EngineContext,
    FetchResult,
    FetchTimings,
    Headers,
    RateLimiter,
    compute_backoff_s,
    should_retry,
)


@dataclass
class HttpEngineOptions:
    timeout_s: float = 15.0
    verify_ssl: bool = True

    # retry
    max_retries: int = 3
    backoff_mode: str = "exp"  # exp | fixed | none
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)

    # rate limit
    rps: Optional[float] = None
    burst: Optional[int] = None
    min_delay_s: Optional[float] = None
    jitter_s: Optional[float] = None

    # headers
    user_agent: Optional[str] = None


class HttpEngine(BaseEngine):
    def __init__(self, *, options: Optional[HttpEngineOptions] = None) -> None:
        super().__init__(name="http")
        self.options = options or HttpEngineOptions()
        self._session = requests.Session()
        self._limiter = RateLimiter(
            rps=self.options.rps,
            burst=self.options.burst,
            min_delay_s=self.options.min_delay_s,
            jitter_s=self.options.jitter_s,
        )

    def close(self) -> None:
        try:
            self._session.close()
        finally:
            return

    def get(self, url: str, *, ctx: Optional[EngineContext] = None) -> FetchResult:
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

        proxies: Optional[Dict[str, str]] = None
        if ctx.proxy:
            proxies = {"http": ctx.proxy, "https": ctx.proxy}

        cookies = ctx.cookies or None

        last_err: Optional[FetchResult] = None

        for attempt in range(0, self.options.max_retries + 1):
            self._limiter.wait()

            started = requests.sessions.datetime.datetime.now().timestamp()
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
                ended = requests.sessions.datetime.datetime.now().timestamp()

                text = None
                try:
                    resp.encoding = resp.encoding or "utf-8"
                    text = resp.text
                except Exception:
                    text = None

                result = FetchResult(
                    ok=(200 <= resp.status_code < 400),
                    final_url=str(resp.url),
                    status_code=int(resp.status_code),
                    text=text,
                    headers={str(k): str(v) for k, v in resp.headers.items()},
                    timings=FetchTimings(started_at_s=started, ended_at_s=ended),
                )

                if result.ok:
                    return result

                # non-OK, maybe retry
                if attempt < self.options.max_retries and should_retry(result.status_code, self.options.retry_on_status):
                    delay = compute_backoff_s(attempt + 1, mode=self.options.backoff_mode)
                    if delay > 0:
                        import time
                        time.sleep(delay)
                    last_err = result
                    continue

                return result

            except requests.RequestException as e:
                ended = requests.sessions.datetime.datetime.now().timestamp()
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

                if attempt < self.options.max_retries:
                    delay = compute_backoff_s(attempt + 1, mode=self.options.backoff_mode)
                    if delay > 0:
                        import time
                        time.sleep(delay)
                    last_err = result
                    continue

                return result

        # should not happen, but safe fallback
        return last_err or FetchResult(
            ok=False,
            final_url=url,
            status_code=None,
            text=None,
            headers={},
            timings=FetchTimings(started_at_s=0.0, ended_at_s=0.0),
            error_type="HttpEngineError",
            error_message="exhausted retries",
        )
