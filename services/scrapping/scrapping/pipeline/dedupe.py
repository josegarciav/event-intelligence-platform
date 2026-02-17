"""Deduplication helpers.

We dedupe by:
- canonical URL (primary)
- optional content fingerprint (secondary)

This module also includes a simple state store interface.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from scrapping.extraction.transforms import canonicalize_url, normalize_ws


def fingerprint_text(text: str) -> str:
    """Compute a stable content fingerprint for dedupe and replay."""
    t = normalize_ws(text or "")
    h = hashlib.sha256(t.encode("utf-8", errors="ignore")).hexdigest()
    return h


def fingerprint_item(item: dict[str, Any], *, fields: Sequence[str] = ("title", "text")) -> str:
    """Compute a fingerprint from selected item fields."""
    parts: list[str] = []
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
        """Check if the key has already been seen."""
        raise NotImplementedError

    def add(self, key: str) -> None:
        """Add a key to the store."""
        raise NotImplementedError


class InMemoryDedupeStore(DedupeStore):
    """In-memory implementation of the dedupe store."""

    def __init__(self) -> None:
        """Initialize with an empty set."""
        self._seen: set[str] = set()

    def seen(self, key: str) -> bool:
        """Check if the key has already been seen."""
        return key in self._seen

    def add(self, key: str) -> None:
        """Add a key to the store."""
        self._seen.add(key)


@dataclass
class DedupeResult:
    """Hold the result of deduplication."""

    kept: list[dict[str, Any]]
    dropped: list[dict[str, Any]]
    stats: dict[str, int]


def dedupe_items(
    items: list[dict[str, Any]],
    *,
    store: DedupeStore | None = None,
    url_field: str = "url",
    content_fields: Sequence[str] | None = ("title", "text"),
    drop_tracking_params: bool = True,
) -> DedupeResult:
    """Deduplicate items by URL and optional content fingerprint."""
    store = store or InMemoryDedupeStore()

    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

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
