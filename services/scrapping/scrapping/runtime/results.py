"""
scrapping.runtime.results.

Unified response models for all engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BlockSignal(str, Enum):
    """Class definition."""

    OK = "ok"
    LIKELY_BLOCKED = "likely_blocked"
    LOGIN_REQUIRED = "login_required"
    CAPTCHA_PRESENT = "captcha_present"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RequestMeta:
    """Class definition."""

    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    proxy: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class ResponseMeta:
    """Class definition."""

    headers: dict[str, str] = field(default_factory=dict)
    redirects: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EngineError:
    """Class definition."""

    type: str
    message: str
    is_retryable: bool = False


@dataclass
class FetchResult:
    """Class definition."""

    final_url: str
    status_code: int | None = None
    content_type: str | None = None
    body_bytes: bytes | None = None
    text: str = ""
    elapsed_ms: float = 0.0

    request_meta: RequestMeta = field(default_factory=RequestMeta)
    response_meta: ResponseMeta = field(default_factory=ResponseMeta)

    error: EngineError | None = None
    block_signals: list[BlockSignal] = field(default_factory=list)
    engine_trace: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Perform the operation."""
        return (
            self.error is None
            and self.status_code is not None
            and 200 <= self.status_code < 400
        )

    @property
    def is_retryable(self) -> bool:
        """Perform the operation."""
        if self.error:
            return self.error.is_retryable
        # Standard HTTP retryable codes
        if self.status_code in (408, 429, 500, 502, 503, 504):
            return True
        return False

    @property
    def elapsed_s(self) -> float:
        """Perform the operation."""
        return self.elapsed_ms / 1000.0

    @property
    def error_type(self) -> str | None:
        """Perform the operation."""
        return self.error.type if self.error else None

    @property
    def error_message(self) -> str | None:
        """Perform the operation."""
        return self.error.message if self.error else None

    @property
    def timings(self) -> Any:
        """Perform the operation."""
        # Compatibility with old FetchTimings
        from dataclasses import dataclass

        @dataclass
        class CompatibilityTimings:
            elapsed_s: float
            started_at_s: float = 0.0
            ended_at_s: float = 0.0

        return CompatibilityTimings(elapsed_s=self.elapsed_s)

    def short_error(self) -> str:
        """Perform the operation."""
        if self.ok:
            return ""
        if self.error:
            return f"{self.error.type}: {self.error.message}"
        if self.status_code:
            return f"HTTP {self.status_code}"
        return "Unknown Error"
