"""
scrapping.runtime.blocks.

Minimal block detection classifier.
"""

from __future__ import annotations

import re

from .results import BlockSignal

_PATTERNS = {
    BlockSignal.CAPTCHA_PRESENT: [
        r"\bcaptcha\b",
        r"\bverify you are human\b",
        r"\bcloudflare\b",
    ],
    BlockSignal.LIKELY_BLOCKED: [
        r"\baccess denied\b",
        r"\bforbidden\b",
        r"\bunusual traffic\b",
    ],
    BlockSignal.LOGIN_REQUIRED: [
        r"\blogin required\b",
        r"\bsign in\b",
        r"\benable javascript\b",
        r"\bplease login\b",
    ],
}


def classify_blocks(text: str | None) -> list[BlockSignal]:
    """Perform the operation."""
    if not text:
        return []

    text_lower = text.lower()
    signals = []
    for signal, patterns in _PATTERNS.items():
        for p in patterns:
            if re.search(p, text_lower):
                signals.append(signal)
                break
    return signals
