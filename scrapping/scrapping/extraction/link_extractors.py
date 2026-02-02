"""
scrapping.extraction.link_extractors

Extract links from HTML using different strategies:
- regex
- css selector
- xpath

Also provides URL normalization helpers for stable dedupe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode


@dataclass(frozen=True)
class LinkExtractRequest:
    html: str
    base_url: Optional[str] = None

    method: str = "regex"  # regex|css|xpath|js
    pattern: Optional[str] = None  # regex
    selector: Optional[str] = None  # css/xpath

    identifier: Optional[str] = None  # substring filter
    allow_fragments: bool = False

    # canonicalization options
    normalize: bool = True
    drop_tracking_params: bool = True
    tracking_params: Tuple[str, ...] = (
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gclid", "fbclid", "mc_cid", "mc_eid",
    )


def extract_links(req: LinkExtractRequest) -> List[str]:
    """
    Main entrypoint. Returns a list of unique links in stable order.
    """
    if not req.html:
        return []

    method = (req.method or "regex").lower().strip()

    if method == "regex":
        if not req.pattern:
            raise ValueError("regex extraction requires pattern")
        raw = _extract_regex(req.html, req.pattern)

    elif method == "css":
        if not req.selector:
            raise ValueError("css extraction requires selector")
        raw = _extract_css(req.html, req.selector)

    elif method == "xpath":
        if not req.selector:
            raise ValueError("xpath extraction requires selector")
        raw = _extract_xpath(req.html, req.selector)

    elif method == "js":
        # Placeholder for future: if html is from browser engine we can also do page.evaluate,
        # but that belongs to engine/actions; here we stay HTML-only.
        raise NotImplementedError("js extraction is not supported in pure HTML mode yet")

    else:
        raise ValueError(f"unknown link extract method: {method}")

    # join with base_url if relative
    cooked: List[str] = []
    for u in raw:
        u = u.strip()
        if not u:
            continue
        if req.base_url:
            u = urljoin(req.base_url, u)
        cooked.append(u)

    # filter by identifier
    if req.identifier:
        cooked = [u for u in cooked if req.identifier in u]

    # normalize/canonicalize
    if req.normalize:
        cooked = [
            canonicalize_url(
                u,
                allow_fragments=req.allow_fragments,
                drop_tracking_params=req.drop_tracking_params,
                tracking_params=req.tracking_params,
            )
            for u in cooked
        ]

    # unique stable
    return _stable_unique(cooked)


# ---------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------

def _extract_regex(html: str, pattern: str) -> List[str]:
    # If pattern has capturing group(s), return the first group; else return whole match.
    rx = re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE)
    links: List[str] = []
    for m in rx.finditer(html):
        if m.groups():
            links.append(m.group(1))
        else:
            links.append(m.group(0))
    return links


def _extract_css(html: str, selector: str) -> List[str]:
    """
    Extract href/src attributes using BeautifulSoup.

    selector example: "a.job-card::attr(href)" or "a.job-card"
    If ::attr(name) is provided, use that attribute, else default to href/src.
    """
    soup = _bs4_soup(html)
    if soup is None:
        return []

    attr = None
    sel = selector
    m = re.search(r"::attr\(([^)]+)\)\s*$", selector.strip())
    if m:
        attr = m.group(1).strip()
        sel = selector[: m.start()].strip()

    nodes = soup.select(sel)
    out: List[str] = []
    for n in nodes:
        if attr:
            v = n.get(attr)
            if v:
                out.append(str(v))
        else:
            # heuristic: href for <a>, src for others
            v = n.get("href") or n.get("src")
            if v:
                out.append(str(v))
    return out


def _extract_xpath(html: str, xpath: str) -> List[str]:
    """
    Extract links using lxml if available.

    xpath example:
      //a[contains(@class,'job')]/@href
    """
    doc = _lxml_doc(html)
    if doc is None:
        return []
    try:
        res = doc.xpath(xpath)
    except Exception:
        return []
    out: List[str] = []
    for x in res:
        if isinstance(x, (str, bytes)):
            out.append(x.decode("utf-8", errors="ignore") if isinstance(x, bytes) else x)
        else:
            # lxml may return nodes; attempt href/src
            try:
                v = x.get("href") or x.get("src")
                if v:
                    out.append(str(v))
            except Exception:
                pass
    return out


def _bs4_soup(html: str):
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        return None
    return BeautifulSoup(html, "html.parser")


def _lxml_doc(html: str):
    try:
        from lxml import html as lxml_html  # type: ignore
    except Exception:
        return None
    try:
        return lxml_html.fromstring(html)
    except Exception:
        return None


# ---------------------------------------------------------------------
# URL canonicalization
# ---------------------------------------------------------------------

def canonicalize_url(
    url: str,
    *,
    allow_fragments: bool = False,
    drop_tracking_params: bool = True,
    tracking_params: Sequence[str] = (),
) -> str:
    """
    Normalize URLs for dedupe:
    - lowercase scheme+host
    - remove default ports
    - remove fragments (optional)
    - optionally drop tracking params (utm, gclid, etc.)
    - sort query params for stability
    """
    url = url.strip()
    if not url:
        return url

    try:
        parts = urlparse(url)
    except Exception:
        return url

    scheme = (parts.scheme or "http").lower()
    netloc = parts.netloc.lower()

    # strip default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parts.path or "/"
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)

    if drop_tracking_params and tracking_params:
        drop = set(p.lower() for p in tracking_params)
        query_pairs = [(k, v) for (k, v) in query_pairs if k.lower() not in drop]

    # stable sort
    query_pairs.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(query_pairs, doseq=True)

    fragment = parts.fragment if allow_fragments else ""

    normalized = urlunparse((scheme, netloc, path, parts.params, query, fragment))
    return normalized


def _stable_unique(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for x in items:
        if not x:
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out
