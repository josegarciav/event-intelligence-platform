"""Resilient HTML parsing helpers.

Includes:
- BeautifulSoup-based helpers (always nice to have)
- lxml-based helpers when installed (faster XPath)
- trafilatura extraction when installed (HTML -> structured text/metadata)

This module should NOT enforce a schema. It just provides primitives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class TextExtractResult:
    """Hold structured text extraction results."""

    ok: bool
    text: str
    title: str | None = None
    author: str | None = None
    date: str | None = None
    language: str | None = None
    raw: dict[str, Any] | None = None
    error: str | None = None


def bs4_soup(html: str):
    """Parse HTML with BeautifulSoup, returning None if unavailable."""
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        return None
    return BeautifulSoup(html or "", "html.parser")


def get_text_bs4(html: str) -> str:
    """Extract visible text from HTML using BeautifulSoup."""
    soup = bs4_soup(html)
    if soup is None:
        return ""
    # remove script/style
    for t in soup(["script", "style", "noscript"]):
        try:
            t.extract()
        except Exception:
            pass
    text = soup.get_text(" ", strip=True)
    return _collapse_ws(text)


def select_text_bs4(html: str, selector: str) -> str:
    """Extract text from elements matching a CSS selector."""
    soup = bs4_soup(html)
    if soup is None:
        return ""
    nodes = soup.select(selector)
    text = " ".join(n.get_text(" ", strip=True) for n in nodes)
    return _collapse_ws(text)


def select_attr_bs4(html: str, selector: str, attr: str) -> list[str]:
    """Extract attribute values from elements matching a CSS selector."""
    soup = bs4_soup(html)
    if soup is None:
        return []
    nodes = soup.select(selector)
    out: list[str] = []
    for n in nodes:
        v = n.get(attr)
        if v:
            out.append(str(v))
    return out


def xpath_values(html: str, xpath: str) -> list[str]:
    """Return string values from XPath evaluation using lxml."""
    try:
        from lxml import html as lxml_html  # type: ignore
    except Exception:
        return []
    try:
        doc = lxml_html.fromstring(html or "")
        res = doc.xpath(xpath)
    except Exception:
        return []
    out: list[str] = []
    for x in res:
        if isinstance(x, (str, bytes)):
            out.append(
                x.decode("utf-8", errors="ignore") if isinstance(x, bytes) else x
            )
        else:
            try:
                out.append(str(x))
            except Exception:
                pass
    return out


# ---------------------------------------------------------------------
# trafilatura (optional)
# ---------------------------------------------------------------------


def extract_structured_trafilatura(
    html: str, *, url: str | None = None
) -> TextExtractResult:
    """
    If trafilatura is installed, returns structured content.

    This is useful for post-processing/QA stages (like your current analyze pipeline).
    """
    try:
        import trafilatura  # type: ignore
        from trafilatura.settings import use_config  # type: ignore
    except Exception as e:
        return TextExtractResult(
            ok=False, text="", error=f"trafilatura not available: {type(e).__name__}"
        )

    try:
        downloaded = html
        if not downloaded:
            return TextExtractResult(ok=False, text="", error="empty html")

        # Use trafilatura defaults (can be configured later)
        config = use_config()
        text = trafilatura.extract(
            downloaded,
            config=config,
            url=url,
            include_comments=False,
            include_tables=False,
        )
        if not text:
            return TextExtractResult(
                ok=False, text="", error="trafilatura returned empty"
            )

        meta = trafilatura.metadata.extract_metadata(downloaded, url=url)
        return TextExtractResult(
            ok=True,
            text=_collapse_ws(text),
            title=getattr(meta, "title", None),
            author=getattr(meta, "author", None),
            date=getattr(meta, "date", None),
            language=getattr(meta, "language", None),
            raw={
                "sitename": getattr(meta, "sitename", None),
                "hostname": getattr(meta, "hostname", None),
                "categories": getattr(meta, "categories", None),
                "tags": getattr(meta, "tags", None),
            },
        )
    except Exception as e:
        return TextExtractResult(ok=False, text="", error=f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

_WS = re.compile(r"\s+")


def _collapse_ws(s: str) -> str:
    return _WS.sub(" ", (s or "").strip())
