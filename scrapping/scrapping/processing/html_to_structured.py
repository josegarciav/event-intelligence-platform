"""
scrapping.processing.html_to_structured

Convert raw HTML to a structured document representation.

Strategy (V1):
1) Prefer trafilatura if installed (best quality extraction + metadata)
2) Fallback to BeautifulSoup text extraction (script/style removal)
3) Optional selectors for title/body if known per source

This is meant to run as a QA/processing step after raw detail fetch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from scrapping.extraction.parsers import (
    get_text_bs4,
    select_text_bs4,
    extract_structured_trafilatura,
)
from scrapping.extraction.transforms import normalize_ws, strip_or_none


@dataclass
class StructuredDoc:
    ok: bool
    url: Optional[str]
    title: Optional[str]
    text: str

    language: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None

    # raw extraction metadata / debug
    extractor: str = "unknown"
    meta: Dict[str, Any] = None
    error: Optional[str] = None

    def as_item(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "language": self.language,
            "author": self.author,
            "published_date": self.published_date,
            "_extractor": self.extractor,
            "_meta": self.meta or {},
            "_error": self.error,
        }


def html_to_structured(
    html: str,
    *,
    url: Optional[str] = None,
    title_selector: Optional[str] = None,
    text_selector: Optional[str] = None,
    prefer_trafilatura: bool = True,
) -> StructuredDoc:
    """
    Convert HTML into a structured doc.

    - title_selector/text_selector: optional CSS selectors (bs4) for known layouts
    - prefer_trafilatura: if installed, use it first
    """
    html = html or ""
    if not html.strip():
        return StructuredDoc(
            ok=False,
            url=url,
            title=None,
            text="",
            extractor="none",
            meta={},
            error="empty_html",
        )

    # 1) trafilatura
    if prefer_trafilatura:
        tr = extract_structured_trafilatura(html, url=url)
        if tr.ok and tr.text:
            title = strip_or_none(tr.title)
            text = normalize_ws(tr.text)
            return StructuredDoc(
                ok=True,
                url=url,
                title=title,
                text=text,
                language=strip_or_none(tr.language),
                author=strip_or_none(tr.author),
                published_date=strip_or_none(tr.date),
                extractor="trafilatura",
                meta=tr.raw or {},
            )

    # 2) selectors (if available)
    title = None
    text = ""
    try:
        if title_selector:
            title = strip_or_none(select_text_bs4(html, title_selector))
        if text_selector:
            text = normalize_ws(select_text_bs4(html, text_selector))
    except Exception:
        # ignore and fallback
        title, text = None, ""

    # 3) fallback to bs4 get_text
    if not text:
        text = normalize_ws(get_text_bs4(html))

    # If still empty, attempt very basic cleanup by removing tags (worst-case)
    if not text:
        text = normalize_ws(_strip_tags(html))

    ok = bool(text)
    return StructuredDoc(
        ok=ok,
        url=url,
        title=title,
        text=text,
        extractor="bs4",
        meta={},
        error=None if ok else "no_text_extracted",
    )


_TAGS = re.compile(r"<[^>]+>")


def _strip_tags(html: str) -> str:
    return _TAGS.sub(" ", html or "")
