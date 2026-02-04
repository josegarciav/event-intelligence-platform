"""
scrapping.extraction.transforms

Normalization utilities used after parsing/extraction.
Keep these pure (input -> output), so they're easy to test.

Examples:
- clean text
- safe cast
- canonicalize URL
- normalize whitespace
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional, Sequence
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

_WS = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    return _WS.sub(" ", (text or "").strip())


def strip_or_none(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None


def safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(str(x).strip())
    except Exception:
        return None


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(str(x).strip())
    except Exception:
        return None


def parse_date_any(x: Any) -> Optional[str]:
    """
    Best-effort date parsing. Returns ISO 8601 string if possible.
    This is intentionally conservative. Team can expand with dateutil later.
    """
    s = strip_or_none(x)
    if not s:
        return None

    # Common patterns; expand later
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date().isoformat()
        except Exception:
            continue

    return None


def canonicalize_url(
    url: str,
    *,
    allow_fragments: bool = False,
    drop_tracking_params: bool = True,
    tracking_params: Sequence[str] = (
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
    ),
) -> str:
    """
    Same concept as in link_extractors, duplicated here for convenience.
    It’s okay to later unify these into one canonical function.
    """
    url = (url or "").strip()
    if not url:
        return url

    try:
        parts = urlparse(url)
    except Exception:
        return url

    scheme = (parts.scheme or "http").lower()
    netloc = parts.netloc.lower()

    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parts.path or "/"
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)

    if drop_tracking_params:
        drop = {p.lower() for p in tracking_params}
        query_pairs = [(k, v) for (k, v) in query_pairs if k.lower() not in drop]

    query_pairs.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(query_pairs, doseq=True)

    fragment = parts.fragment if allow_fragments else ""
    return urlunparse((scheme, netloc, path, parts.params, query, fragment))


def normalize_item_fields(
    item: Dict[str, Any], *, url_fields: Sequence[str] = ("url",)
) -> Dict[str, Any]:
    """
    Apply common cleaning rules to an item dict:
    - normalize whitespace in strings
    - canonicalize urls
    """
    out: Dict[str, Any] = {}
    for k, v in item.items():
        if isinstance(v, str):
            out[k] = normalize_ws(v)
        else:
            out[k] = v

    for f in url_fields:
        if f in out and isinstance(out[f], str):
            out[f] = canonicalize_url(out[f])

    return out
