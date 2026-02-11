"""
scrapping.pipeline.validators

Validation helpers for extracted items.

We keep this as:
- Pure functions
- Warning/error separation
- Configurable rules via dicts (so configs can tune validation per source)

Later:
- Add domain-specific validators (job posts, product cards, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from scrapping.extraction.transforms import normalize_ws


@dataclass(frozen=True)
class ValidationIssue:
    level: str  # "warning" or "error"
    code: str
    message: str
    field: str | None = None


@dataclass
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]


def validate_item(
    item: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None
) -> ValidationResult:
    """
    Generic item validation.

    Default expectations (light):
      - url must exist and be valid
      - title recommended
      - text recommended
      - min_text_len optional
    """
    rules = rules or {}
    issues: list[ValidationIssue] = []

    url_field = rules.get("url_field", "url")
    title_field = rules.get("title_field", "title")
    text_field = rules.get("text_field", "text")

    min_text_len = int(rules.get("min_text_len", 0))
    require_title = bool(rules.get("require_title", False))
    require_text = bool(rules.get("require_text", False))

    # URL presence & sanity
    url = item.get(url_field)
    if not url:
        issues.append(ValidationIssue("error", "missing_url", "Item missing url", field=url_field))
    elif not _looks_like_url(str(url)):
        issues.append(ValidationIssue("error", "bad_url", "URL is not valid", field=url_field))

    # title/text checks
    title = item.get(title_field)
    if require_title and not title:
        issues.append(ValidationIssue("error", "missing_title", "Item missing title", field=title_field))
    elif not title:
        issues.append(ValidationIssue("warning", "missing_title", "Title is missing", field=title_field))

    text = item.get(text_field)
    if require_text and not text:
        issues.append(ValidationIssue("error", "missing_text", "Item missing text", field=text_field))
    elif not text:
        issues.append(ValidationIssue("warning", "missing_text", "Text is missing", field=text_field))
    else:
        txt = normalize_ws(str(text))
        if min_text_len > 0 and len(txt) < min_text_len:
            issues.append(ValidationIssue(
                "warning",
                "short_text",
                f"Text length {len(txt)} < min_text_len={min_text_len}",
                field=text_field
            ))

    ok = not any(i.level == "error" for i in issues)
    return ValidationResult(ok=ok, issues=issues)


def _looks_like_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return bool(p.scheme) and bool(p.netloc)
    except Exception:
        return False
