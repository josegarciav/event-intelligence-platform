"""
scrapping.diagnostics.signals

Standardized diagnosis labels for scraper results.
"""

from enum import Enum


class DiagnosisLabel(str, Enum):
    OK = "ok"
    JS_REQUIRED_OR_MISSING_CONTENT = "js_required_or_missing_content"
    RATE_LIMITED = "rate_limited"
    REQUIRES_AUTH = "requires_auth"
    CHALLENGE_DETECTED = "challenge_detected"
    BLOCKED_OR_DENIED = "blocked_or_denied"
    UNKNOWN_ERROR = "unknown_error"


class NextStep(str, Enum):
    TRY_HTTP_TUNING = "try_http_tuning"
    SWITCH_TO_BROWSER = "switch_to_browser"
    STOP_FOR_HUMAN = "stop_for_human"
    USE_OFFICIAL_API = "use_official_api"
    USE_AUTH = "use_auth"
    PROCEED = "proceed"
