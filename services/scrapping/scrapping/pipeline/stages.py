"""
scrapping.pipeline.stages

Pipeline stage implementations (V1).

Stages included:
- discover listing URLs from entrypoints + paging
- fetch listing pages (engine.get or engine.get_rendered)
- extract links from listing HTML
- fetch detail pages
- parse detail pages (basic strategy: trafilatura if available, else bs4 text)
- validate items
- dedupe items

This is engine-agnostic and config-driven.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from scrapping.engines.base import BaseEngine, EngineContext, FetchResult
from scrapping.extraction.link_extractors import LinkExtractRequest, extract_links
from scrapping.extraction.parsers import (
    extract_structured_trafilatura,
    get_text_bs4,
    select_text_bs4,
)
from scrapping.extraction.transforms import normalize_item_fields
from scrapping.pipeline.dedupe import DedupeStore, InMemoryDedupeStore, dedupe_items
from scrapping.pipeline.validators import validate_item


@dataclass
class StageStats:
    pages_attempted: int = 0
    pages_succeeded: int = 0
    detail_attempted: int = 0
    detail_succeeded: int = 0
    links_found: int = 0
    items_parsed: int = 0
    items_valid: int = 0
    items_saved: int = 0
    errors: int = 0


@dataclass
class ListingPage:
    url: str
    fetch: FetchResult


@dataclass
class DetailPage:
    url: str
    fetch: FetchResult


@dataclass
class PipelineArtifacts:
    listing_pages: list[ListingPage]
    detail_pages: list[DetailPage]
    extracted_links: list[str]
    items: list[dict[str, Any]]
    valid_items: list[dict[str, Any]]
    dropped_items: list[dict[str, Any]]
    stats: StageStats
    diagnostics: dict[str, Any]


# ---------------------------------------------------------------------
# Discover
# ---------------------------------------------------------------------

def discover_listing_urls(source_cfg: dict[str, Any]) -> list[str]:
    """
    Build listing URLs from entrypoints + paging.

    Supports paging.mode:
      - page: url contains {page}
      - offset: url contains {offset}
      - cursor/custom: not implemented (future)
    """
    entrypoints = source_cfg.get("entrypoints") or []
    out: list[str] = []

    for ep in entrypoints:
        if not isinstance(ep, dict):
            continue
        url_tpl = str(ep.get("url", "")).strip()
        if not url_tpl:
            continue

        paging = ep.get("paging") or {}
        mode = str(paging.get("mode", "page"))

        if mode == "page":
            pages = int(paging.get("pages", 1) or 1)
            start = int(paging.get("start", 1) or 1)
            step = int(paging.get("step", 1) or 1)
            for i in range(pages):
                page = start + i * step
                out.append(url_tpl.format(page=page))

        elif mode == "offset":
            pages = int(paging.get("pages", 1) or 1)
            start = int(paging.get("start", 0) or 0)
            step = int(paging.get("step", 10) or 10)
            for i in range(pages):
                offset = start + i * step
                out.append(url_tpl.format(offset=offset))

        else:
            # future: cursor/custom
            out.append(url_tpl)

    # stable unique
    seen = set()
    unique = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        unique.append(u)
    return unique


# ---------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------

def fetch_pages(
    urls: Sequence[str],
    *,
    engine: BaseEngine,
    ctx: EngineContext,
    parallelism: int = 8,
    rendered: bool = False,
    actions: Sequence[dict[str, Any]] | None = None,
    wait_for: str | None = None,
) -> list[FetchResult]:
    if not urls:
        return []

    def _one(u: str) -> FetchResult:
        if rendered:
            return engine.get_rendered(u, ctx=ctx, actions=actions, wait_for=wait_for)
        return engine.get(u, ctx=ctx)

    results: list[FetchResult] = []
    if parallelism <= 1:
        for u in urls:
            results.append(_one(u))
        return results

    with ThreadPoolExecutor(max_workers=int(parallelism)) as ex:
        futs = {ex.submit(_one, u): u for u in urls}
        for fut in as_completed(futs):
            results.append(fut.result())
    # keep stable by sorting according to original order
    order = {u: i for i, u in enumerate(urls)}
    results.sort(key=lambda r: order.get(r.final_url, 10**9))
    return results


# ---------------------------------------------------------------------
# Main pipeline (V1)
# ---------------------------------------------------------------------

def run_pipeline_v1(
    source_cfg: dict[str, Any],
    *,
    engine: BaseEngine,
    parallelism: int = 16,
    dedupe_store: DedupeStore | None = None,
) -> PipelineArtifacts:
    stats = StageStats()
    diagnostics: dict[str, Any] = {}

    dedupe_store = dedupe_store or InMemoryDedupeStore()

    # Build context for engine
    eng = source_cfg.get("engine") or {}
    ctx = EngineContext(
        timeout_s=float(eng.get("timeout_s", 15.0)),
        verify_ssl=bool(eng.get("verify_ssl", True)),
        user_agent=eng.get("user_agent"),
        proxy=None,
        headers=None,
        cookies=None,
    )

    # Decide listing fetch method
    engine_type = str(eng.get("type", "http")).lower()
    use_render_for_listing = engine_type in ("browser",)  # hybrid/http default to get()

    actions = source_cfg.get("actions") or None
    wait_for = None
    if isinstance(source_cfg.get("discovery"), dict):
        # optional: discovery.wait_for selector
        wait_for = (source_cfg["discovery"].get("wait_for") or None)

    # 1) discover listing URLs
    listing_urls = discover_listing_urls(source_cfg)
    diagnostics["listing_urls"] = listing_urls

    # 2) fetch listing pages
    listing_fetches = fetch_pages(
        listing_urls,
        engine=engine,
        ctx=ctx,
        parallelism=max(1, min(8, parallelism // 2)),
        rendered=bool(use_render_for_listing),
        actions=actions,
        wait_for=wait_for,
    )

    listing_pages: list[ListingPage] = []
    for r in listing_fetches:
        stats.pages_attempted += 1
        if r.ok and r.text:
            stats.pages_succeeded += 1
        else:
            stats.errors += 1
        listing_pages.append(ListingPage(url=r.final_url, fetch=r))

    # 3) extract links
    discovery = source_cfg.get("discovery") or {}
    link_cfg = (discovery.get("link_extract") or {}) if isinstance(discovery, dict) else {}

    base_url = _guess_base_url(listing_urls[0]) if listing_urls else None
    all_links: list[str] = []
    for lp in listing_pages:
        if not lp.fetch.ok or not lp.fetch.text:
            continue
        req = LinkExtractRequest(
            html=lp.fetch.text,
            base_url=base_url,
            method=str(link_cfg.get("method", "regex")),
            pattern=link_cfg.get("pattern"),
            selector=link_cfg.get("selector"),
            identifier=link_cfg.get("identifier"),
            normalize=True,
        )
        links = extract_links(req)
        all_links.extend(links)

    # stable unique
    seen = set()
    extracted_links: list[str] = []
    for u in all_links:
        if u in seen:
            continue
        seen.add(u)
        extracted_links.append(u)

    stats.links_found = len(extracted_links)
    diagnostics["extracted_links_sample"] = extracted_links[:20]

    # 4) fetch detail pages
    detail_fetches = fetch_pages(
        extracted_links,
        engine=engine,
        ctx=ctx,
        parallelism=max(1, parallelism),
        rendered=(engine_type in ("browser", "hybrid")),  # for hybrid, get_rendered => browser
        actions=actions if engine_type in ("browser", "hybrid") else None,
        wait_for=None,
    )

    detail_pages: list[DetailPage] = []
    for r in detail_fetches:
        stats.detail_attempted += 1
        if r.ok and r.text:
            stats.detail_succeeded += 1
        else:
            stats.errors += 1
        detail_pages.append(DetailPage(url=r.final_url, fetch=r))

    # 5) parse + normalize items
    items: list[dict[str, Any]] = []
    parse_cfg = (source_cfg.get("parse") or {}) if isinstance(source_cfg.get("parse"), dict) else {}
    title_selector = parse_cfg.get("title_selector")  # optional
    text_selector = parse_cfg.get("text_selector")    # optional

    for dp in detail_pages:
        if not dp.fetch.ok or not dp.fetch.text:
            continue

        html = dp.fetch.text
        url = dp.fetch.final_url

        # prefer trafilatura if present
        structured = extract_structured_trafilatura(html, url=url)
        if structured.ok and structured.text:
            title = structured.title
            text = structured.text
        else:
            title = select_text_bs4(html, title_selector) if title_selector else None
            text = select_text_bs4(html, text_selector) if text_selector else get_text_bs4(html)

        item = {
            "url": url,
            "title": title,
            "text": text,
            "fetched_at": None,
            "status_code": dp.fetch.status_code,
        }
        item = normalize_item_fields(item, url_fields=("url",))
        items.append(item)

    stats.items_parsed = len(items)

    # 6) validate
    val_rules = (source_cfg.get("validation") or {}) if isinstance(source_cfg.get("validation"), dict) else {}
    valid_items: list[dict[str, Any]] = []
    invalid_items: list[dict[str, Any]] = []

    for it in items:
        vr = validate_item(it, rules=val_rules)
        if vr.ok:
            valid_items.append(it)
        else:
            bad = dict(it)
            bad["_validation_errors"] = [i.__dict__ for i in vr.errors()]
            invalid_items.append(bad)

    stats.items_valid = len(valid_items)

    # 7) dedupe
    dd_cfg = (discovery.get("dedupe") or {}) if isinstance(discovery, dict) else {}
    content_fields = dd_cfg.get("content_fields", ("title", "text"))
    if content_fields is not None and not isinstance(content_fields, (list, tuple)):
        content_fields = ("title", "text")

    dd = dedupe_items(
        valid_items,
        store=dedupe_store,
        url_field="url",
        content_fields=tuple(content_fields) if content_fields else None,
        drop_tracking_params=True,
    )

    stats.items_saved = len(dd.kept)

    return PipelineArtifacts(
        listing_pages=listing_pages,
        detail_pages=detail_pages,
        extracted_links=extracted_links,
        items=items,
        valid_items=dd.kept,
        dropped_items=dd.dropped + invalid_items,
        stats=stats,
        diagnostics=diagnostics,
    )


def _guess_base_url(url: str) -> str | None:
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        if not p.scheme or not p.netloc:
            return None
        return f"{p.scheme}://{p.netloc}/"
    except Exception:
        return None
