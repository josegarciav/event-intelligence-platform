"""
scrapping.runtime.results

Unified response models for all engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class BlockSignal(str, Enum):
    OK = "ok"
    LIKELY_BLOCKED = "likely_blocked"
    LOGIN_REQUIRED = "login_required"
    CAPTCHA_PRESENT = "captcha_present"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RequestMeta:
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    proxy: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(frozen=True)
class ResponseMeta:
    headers: dict[str, str] = field(default_factory=dict)
    redirects: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EngineError:
    type: str
    message: str
    is_retryable: bool = False


@dataclass
class FetchResult:
    final_url: str
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    body_bytes: Optional[bytes] = None
    text: str = ""
    elapsed_ms: float = 0.0

    request_meta: RequestMeta = field(default_factory=RequestMeta)
    response_meta: ResponseMeta = field(default_factory=ResponseMeta)

    error: Optional[EngineError] = None
    block_signals: list[BlockSignal] = field(default_factory=list)
    engine_trace: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 400

    @property
    def is_retryable(self) -> bool:
        if self.error:
            return self.error.is_retryable
        # Standard HTTP retryable codes
        if self.status_code in (408, 429, 500, 502, 503, 504):
            return True
        return False

    @property
    def elapsed_s(self) -> float:
        return self.elapsed_ms / 1000.0

    @property
    def error_type(self) -> str | None:
        return self.error.type if self.error else None

    @property
    def error_message(self) -> str | None:
        return self.error.message if self.error else None

    @property
    def timings(self) -> Any:
        # Compatibility with old FetchTimings
        from dataclasses import dataclass
        @dataclass
        class CompatibilityTimings:
            elapsed_s: float
            started_at_s: float = 0.0
            ended_at_s: float = 0.0
        return CompatibilityTimings(elapsed_s=self.elapsed_s)

    def short_error(self) -> str:
        if self.ok:
            return ""
        if self.error:
            return f"{self.error.type}: {self.error.message}"
        if self.status_code:
            return f"HTTP {self.status_code}"
        return "Unknown Error"
