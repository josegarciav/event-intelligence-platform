"""
scrapping.pipeline.dedupe

Deduplication helpers.

We dedupe by:
- canonical URL (primary)
- optional content fingerprint (secondary)

This module also includes a simple state store interface.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set

from scrapping.extraction.transforms import canonicalize_url, normalize_ws


def fingerprint_text(text: str) -> str:
    """
    Stable content fingerprint for dedupe / replay.
    """
    t = normalize_ws(text or "")
    h = hashlib.sha256(t.encode("utf-8", errors="ignore")).hexdigest()
    return h


def fingerprint_item(
    item: Dict[str, Any], *, fields: Sequence[str] = ("title", "text")
) -> str:
    parts: List[str] = []
    for f in fields:
        v = item.get(f)
        if v:
            parts.append(normalize_ws(str(v)))
    return fingerprint_text(" | ".join(parts))


class DedupeStore:
    """
    Interface for dedupe state.

    V1 uses in-memory store. Later we can implement:
      - sqlite
      - redis
      - file-backed bloom filter
    """

    def seen(self, key: str) -> bool:
        raise NotImplementedError

    def add(self, key: str) -> None:
        raise NotImplementedError


class InMemoryDedupeStore(DedupeStore):
    def __init__(self) -> None:
        self._seen: Set[str] = set()

    def seen(self, key: str) -> bool:
        return key in self._seen

    def add(self, key: str) -> None:
        self._seen.add(key)


@dataclass
class DedupeResult:
    kept: List[Dict[str, Any]]
    dropped: List[Dict[str, Any]]
    stats: Dict[str, int]


def dedupe_items(
    items: List[Dict[str, Any]],
    *,
    store: Optional[DedupeStore] = None,
    url_field: str = "url",
    content_fields: Optional[Sequence[str]] = ("title", "text"),
    drop_tracking_params: bool = True,
) -> DedupeResult:
    store = store or InMemoryDedupeStore()

    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []

    n_url_dupes = 0
    n_content_dupes = 0

    for it in items:
        url = it.get(url_field)
        if not url:
            # no url: cannot dedupe reliably; keep (validation will catch)
            kept.append(it)
            continue

        canon = canonicalize_url(str(url), drop_tracking_params=drop_tracking_params)
        url_key = f"url:{canon}"

        if store.seen(url_key):
            n_url_dupes += 1
            dropped.append(it)
            continue

        # mark url seen
        store.add(url_key)

        # optional content fingerprint
        if content_fields:
            fp = fingerprint_item(it, fields=content_fields)
            content_key = f"content:{fp}"
            if store.seen(content_key):
                n_content_dupes += 1
                dropped.append(it)
                continue
            store.add(content_key)

        # keep and also rewrite canonical URL in item for stability
        it2 = dict(it)
        it2[url_field] = canon
        kept.append(it2)

    return DedupeResult(
        kept=kept,
        dropped=dropped,
        stats={
            "input": len(items),
            "kept": len(kept),
            "dropped": len(dropped),
            "url_dupes": n_url_dupes,
            "content_dupes": n_content_dupes,
        },
    )
