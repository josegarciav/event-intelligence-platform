"""
scrapping.processing.quality_filters.

Rule-based QA filters for items/docs.

Why:
- Most scraping failures aren't "engine down" — they are low-quality pages:
  login walls, cookie prompts, JS placeholders, empty pages, anti-bot pages, etc.

This module provides:
- issue reporting (warnings/errors)
- reject/keep decision
- configurable rules
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from scrapping.extraction.transforms import normalize_ws, strip_or_none


@dataclass(frozen=True)
class QualityIssue:
    """Class definition."""

    level: str  # "warning"|"error"
    code: str
    message: str


@dataclass
class QualityResult:
    """Class definition."""

    keep: bool
    issues: list[QualityIssue]

    def errors(self) -> list[QualityIssue]:
        """Perform the operation."""
        return [i for i in self.issues if i.level == "error"]

    def warnings(self) -> list[QualityIssue]:
        """Perform the operation."""
        return [i for i in self.issues if i.level == "warning"]


_DEFAULT_BLOCK_PATTERNS = [
    r"\baccess denied\b",
    r"\bverify you are human\b",
    r"\bcaptcha\b",
    r"\bcloudflare\b",
    r"\bforbidden\b",
    r"\bnot authorized\b",
    r"\blogin required\b",
    r"\bsign in\b",
    r"\benable javascript\b",
]

_WS = re.compile(r"\s+")


def evaluate_quality(
    item: dict[str, Any], *, rules: dict[str, Any] | None = None
) -> QualityResult:
    """
    Evaluate item quality and decide keep/drop.

    Expected item fields:
      - url (optional)
      - title (optional)
      - text (optional but recommended)

    rules (suggested):
      - min_text_len (int)
      - min_title_len (int)
      - max_boilerplate_ratio (float between 0..1) [heuristic]
      - block_patterns (list[str regex])
      - required_fields (list[str])
      - language_allow (list[str]) / language_deny (list[str]) using item['language'] if present
    """
    rules = rules or {}
    issues: list[QualityIssue] = []

    text = normalize_ws(str(item.get("text", "") or ""))
    title = normalize_ws(str(item.get("title", "") or ""))

    # required fields
    required = rules.get("required_fields") or []
    if isinstance(required, list | tuple):
        for f in required:
            if not item.get(f):
                issues.append(
                    QualityIssue(
                        "error", "missing_field", f"Missing required field: {f}"
                    )
                )

    # min lengths
    min_text_len = int(rules.get("min_text_len", 200))
    min_title_len = int(rules.get("min_title_len", 3))

    if len(title) < min_title_len:
        issues.append(
            QualityIssue(
                "warning", "short_title", f"title length {len(title)} < {min_title_len}"
            )
        )

    if len(text) < min_text_len:
        issues.append(
            QualityIssue(
                "error", "short_text", f"text length {len(text)} < {min_text_len}"
            )
        )

    # anti-bot / blocked page patterns
    patterns = rules.get("block_patterns") or _DEFAULT_BLOCK_PATTERNS
    try:
        for p in patterns:
            if re.search(p, text.lower(), flags=re.IGNORECASE):
                issues.append(
                    QualityIssue("error", "blocked_page", f"Matched block pattern: {p}")
                )
                break
    except Exception:
        # if patterns are malformed, warn but don't kill
        issues.append(
            QualityIssue(
                "warning",
                "bad_block_patterns",
                "Invalid block patterns; skipped matching",
            )
        )

    # boilerplate heuristic
    # This is a rough heuristic: if too many repeated tokens or too low lexical variety, it's often garbage.
    max_boilerplate_ratio = rules.get("max_boilerplate_ratio", None)
    if max_boilerplate_ratio is not None:
        try:
            max_boilerplate_ratio = float(max_boilerplate_ratio)
            ratio = _boilerplate_ratio(text)
            if ratio > max_boilerplate_ratio:
                issues.append(
                    QualityIssue(
                        "error",
                        "boilerplate",
                        f"boilerplate_ratio {ratio:.3f} > {max_boilerplate_ratio:.3f}",
                    )
                )
        except Exception:
            issues.append(
                QualityIssue(
                    "warning", "bad_boilerplate_rule", "Invalid max_boilerplate_ratio"
                )
            )

    # language allow/deny (uses extracted language if present)
    lang = strip_or_none(item.get("language"))
    allow = rules.get("language_allow")
    deny = rules.get("language_deny")

    if lang and isinstance(deny, list | tuple) and lang in deny:
        issues.append(
            QualityIssue("error", "lang_denied", f"language '{lang}' is denied")
        )

    if lang and isinstance(allow, list | tuple) and allow and (lang not in allow):
        issues.append(
            QualityIssue(
                "error", "lang_not_allowed", f"language '{lang}' not in allowed list"
            )
        )

    keep = not any(i.level == "error" for i in issues)
    return QualityResult(keep=keep, issues=issues)


def _boilerplate_ratio(text: str) -> float:
    """Heuristic for boilerplate and placeholder pages.

    Return value in [0..1] where higher => more boilerplate-y.

    We use a blend of:
    - repeated token ratio
    - lexical variety proxy
    """
    if not text:
        return 1.0

    tokens = [t for t in re.split(r"\W+", text.lower()) if t]
    if len(tokens) < 30:
        return 0.0  # too short handled elsewhere

    unique = set(tokens)
    variety = len(unique) / max(1, len(tokens))  # 0..1, higher is better

    # repeated token share
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    repeats = sum(1 for t, c in counts.items() if c >= 5)
    repeat_share = repeats / max(1, len(unique))  # 0..1

    # combine: low variety + high repeat share -> higher boilerplate
    score = (1.0 - variety) * 0.65 + repeat_share * 0.35
    return max(0.0, min(1.0, score))
