"""
scrapping.diagnostics.classifiers.

Heuristics for classifying HTTP responses and rendered DOMs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .signals import DiagnosisLabel, NextStep


@dataclass(frozen=True)
class Diagnosis:
    """Class definition."""

    label: DiagnosisLabel
    reason: str
    next_step: NextStep
    details: dict[str, Any]


def diagnose_http_response(
    status_code: int, headers: dict[str, str], text: str | None = None
) -> Diagnosis:
    """Classify a raw HTTP response."""
    text = (text or "").lower()
    headers_low = {k.lower(): v.lower() for k, v in headers.items()}

    # 1. Rate limiting
    if status_code == 429 or "retry-after" in headers_low:
        return Diagnosis(
            label=DiagnosisLabel.RATE_LIMITED,
            reason="Received 429 status or Retry-After header",
            next_step=NextStep.TRY_HTTP_TUNING,
            details={
                "status_code": status_code,
                "retry_after": headers_low.get("retry-after"),
            },
        )

    # 2. Challenge detection
    challenge_patterns = [
        "captcha",
        "recaptcha",
        "turnstile",
        "cf-turnstile",
        "verify you are human",
        "unusual traffic",
    ]
    for p in challenge_patterns:
        if p in text:
            return Diagnosis(
                label=DiagnosisLabel.CHALLENGE_DETECTED,
                reason=f"Found challenge pattern: {p}",
                next_step=NextStep.STOP_FOR_HUMAN,
                details={"pattern": p},
            )

    # 3. Auth required (high confidence)
    auth_patterns = ["login", "sign in", "create account", "password required"]
    if status_code == 401 or any(p in text for p in auth_patterns):
        return Diagnosis(
            label=DiagnosisLabel.REQUIRES_AUTH,
            reason="Auth required signals detected",
            next_step=NextStep.USE_AUTH,
            details={"status_code": status_code},
        )

    # 4. Blocked/Denied / 403
    if status_code == 403:
        return Diagnosis(
            label=DiagnosisLabel.BLOCKED_OR_DENIED,
            reason="Received 403 Forbidden",
            next_step=NextStep.TRY_HTTP_TUNING,
            details={"status_code": status_code},
        )

    # 5. Missing content / JS required
    # Heuristic: very short body or common JS-only indicators
    if status_code == 200:
        if (
            len(text) < 500
            or "javascript is required" in text
            or "enable javascript" in text
        ):
            return Diagnosis(
                label=DiagnosisLabel.JS_REQUIRED_OR_MISSING_CONTENT,
                reason="Response too short or contains JS-requirement message",
                next_step=NextStep.SWITCH_TO_BROWSER,
                details={"len": len(text)},
            )

    if 200 <= status_code < 300:
        return Diagnosis(
            label=DiagnosisLabel.OK,
            reason="Status 2xx",
            next_step=NextStep.PROCEED,
            details={"status_code": status_code},
        )

    return Diagnosis(
        label=DiagnosisLabel.UNKNOWN_ERROR,
        reason=f"Unhandled status code: {status_code}",
        next_step=NextStep.TRY_HTTP_TUNING,
        details={"status_code": status_code},
    )


def diagnose_rendered_dom(text: str) -> Diagnosis:
    """Classify a DOM that has already been rendered by a browser."""
    text_low = text.lower()

    # 1. Challenge detection (even in browser)
    challenge_patterns = [
        "captcha",
        "recaptcha",
        "turnstile",
        "cf-turnstile",
        "verify you are human",
        "unusual traffic",
    ]
    for p in challenge_patterns:
        if p in text_low:
            return Diagnosis(
                label=DiagnosisLabel.CHALLENGE_DETECTED,
                reason=f"Found challenge pattern in rendered DOM: {p}",
                next_step=NextStep.STOP_FOR_HUMAN,
                details={"pattern": p},
            )

    # 2. Auth required
    auth_patterns = ["login", "sign in", "create account", "password required"]
    if any(p in text_low for p in auth_patterns):
        return Diagnosis(
            label=DiagnosisLabel.REQUIRES_AUTH,
            reason="Auth required signals detected in DOM",
            next_step=NextStep.USE_AUTH,
            details={},
        )

    # 3. Missing content
    if len(text) < 200:
        return Diagnosis(
            label=DiagnosisLabel.JS_REQUIRED_OR_MISSING_CONTENT,
            reason="Rendered DOM is suspiciously short",
            next_step=NextStep.TRY_HTTP_TUNING,
            details={"len": len(text)},
        )

    return Diagnosis(
        label=DiagnosisLabel.OK,
        reason="Rendered content seems ok",
        next_step=NextStep.PROCEED,
        details={"len": len(text)},
    )


def recommend_next_step(diagnosis: Diagnosis) -> str:
    """Human-friendly recommendation string."""
    mapping = {
        NextStep.PROCEED: "Continue with extraction.",
        NextStep.TRY_HTTP_TUNING: "Try adjusting User-Agent, adding delays, or using proxies.",
        NextStep.SWITCH_TO_BROWSER: "The site requires JavaScript. Switch to 'browser' engine.",
        NextStep.STOP_FOR_HUMAN: "Automated challenge detected. Stop and save artifacts for manual review.",
        NextStep.USE_OFFICIAL_API: "This site is hard to scrape. Check if an official API is available.",
        NextStep.USE_AUTH: "Login required. Use session cookies or provide credentials.",
    }
    return mapping.get(diagnosis.next_step, "Analyze artifacts and troubleshoot.")
