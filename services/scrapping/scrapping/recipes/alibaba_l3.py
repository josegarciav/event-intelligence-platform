"""
scrapping.recipes.alibaba_l3

Refactored Alibaba L3 recipe using the core recipe framework.
Fully config-driven with schema-validated items.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from scrapping.engines.browser import BrowserEngine, BrowserEngineOptions
from scrapping.extraction.link_extractors import LinkExtractRequest, extract_links
from scrapping.extraction.parsers import select_text_bs4, bs4_soup
from scrapping.monitoring.events import emit_event
from scrapping.monitoring.logging import with_context
from scrapping.schemas.items import ProductItem

from .core.state import StateManager
from .core.phases import Phase, PhaseRunner, PhaseResult
from .core.artifacts import write_jsonl, write_summary_csv

logger = logging.getLogger("scrapping.recipes.alibaba_l3")

@dataclass
class AlibabaConfig:
    source_id: str = "alibaba"
    # Controls
    max_pages: int = 5
    checkpoint_every_n: int = 10
    restart_every_n: int = 50
    # Selectors
    search_wait_selector: str = ".m-results-item, .item-main"
    link_pattern: str = "/product/\\d+\\.html"
    category_selector: str = ".category-item"
    product_title_selector: str = ".product-title"
    product_price_selector: str = ".price"
    # Output names
    links_file: str = "product_links.json"
    products_file: str = "products.jsonl"
    rejected_file: str = "products_rejected.jsonl"
    filters_file: str = "alibaba_filters.json"
    categories_file: str = "alibaba_categories.json"

class SearchPhase:
    name = "search"
    def run(self, ctx: RecipeContext) -> dict:
        url = f"https://www.alibaba.com/trade/search?SearchText={ctx.keyword}&language=en"
        if not ctx.online: return {"status": "skipped_offline"}

        res = ctx.engine.get_rendered(url, wait_for=ctx.config.search_wait_selector)
        if not res.ok:
            raise RuntimeError(f"Search failed: {res.short_error()}")
        return {"status": "ok"}

class FiltersPhase:
    name = "filters"
    def run(self, ctx: RecipeContext) -> dict:
        if not ctx.online:
            filters = {"Price": ["Min", "Max"]}
            categories = ["Mock Category"]
        else:
            url = f"https://www.alibaba.com/trade/search?SearchText={ctx.keyword}"
            res = ctx.engine.get(url)
            soup = bs4_soup(res.text)
            filters = {} # simplified
            categories = [cat.get_text(strip=True) for cat in soup.select(ctx.config.category_selector)]

        with (Path(ctx.state.output_dir) / ctx.config.filters_file).open("w") as f:
            json.dump(filters, f)
        with (Path(ctx.state.output_dir) / ctx.config.categories_file).open("w") as f:
            json.dump(categories, f)

        return {"filters_count": len(filters), "categories_count": len(categories)}

class LinksPhase:
    name = "links"
    def run(self, ctx: RecipeContext) -> dict:
        all_links = set(ctx.state.processed_urls) # Reuse processed_urls for links in this phase
        counts = {}

        max_p = ctx.config.max_pages
        for p in range(ctx.state.current_page, max_p + 1):
            url = f"https://www.alibaba.com/trade/search?SearchText={ctx.keyword}&page={p}&language=en"

            if ctx.online:
                res = ctx.engine.get_rendered(url, actions=[{"type": "scroll", "params": {"repeat": 3}}], wait_for=ctx.config.search_wait_selector)
                html = res.text
            else:
                html = '<html><a href="/product/123.html">P1</a></html>'

            req = LinkExtractRequest(html=html, method="regex", pattern=ctx.config.link_pattern)
            links = extract_links(req)

            new_links = [l for l in links if l not in all_links]
            all_links.update(new_links)
            counts[p] = len(links)

            ctx.state.processed_urls = list(all_links)
            ctx.state.current_page = p
            ctx.state.save()
            if not ctx.online: break

        with (Path(ctx.state.output_dir) / ctx.config.links_file).open("w") as f:
            json.dump({"total": len(all_links), "per_page": counts, "links": list(all_links)}, f)

        return {"links_found": len(all_links)}

class ProductsPhase:
    name = "products"
    def run(self, ctx: RecipeContext) -> dict:
        links = ctx.state.processed_urls
        completed = set(ctx.state.metadata.get("completed_links", []))

        remaining = [l for l in links if l not in completed]

        count = 0
        valid_count = 0
        rejected_count = 0

        for link in remaining:
            if count > 0 and count % ctx.config.restart_every_n == 0:
                ctx.engine.close()

            if ctx.online:
                full_url = f"https://www.alibaba.com{link}" if link.startswith("/") else link
                res = ctx.engine.get_rendered(full_url, wait_for=ctx.config.product_title_selector)
                raw_item = {
                    "source_id": ctx.config.source_id,
                    "url": full_url,
                    "title": select_text_bs4(res.text, ctx.config.product_title_selector),
                    "price": select_text_bs4(res.text, ctx.config.product_price_selector),
                }
            else:
                raw_item = {
                    "source_id": ctx.config.source_id,
                    "url": f"https://www.alibaba.com{link}",
                    "title": "Mock Product",
                    "price": "100",
                }

            try:
                item = ProductItem(**raw_item)
                write_jsonl(Path(ctx.state.output_dir) / ctx.config.products_file, [item.model_dump()])
                valid_count += 1
            except Exception as e:
                raw_item["_rejection_reason"] = str(e)
                write_jsonl(Path(ctx.state.output_dir) / ctx.config.rejected_file, [raw_item])
                rejected_count += 1

            completed.add(link)
            count += 1

            if count % ctx.config.checkpoint_every_n == 0:
                ctx.state.metadata["completed_links"] = list(completed)
                ctx.state.save()
                emit_event(ctx.log, "checkpoint.saved", {"count": count})

        ctx.state.metadata["completed_links"] = list(completed)
        ctx.state.save()
        return {"products_scraped": count, "valid": valid_count, "rejected": rejected_count}

@dataclass
class RecipeContext:
    keyword: str
    engine: BrowserEngine
    state: StateManager
    config: AlibabaConfig
    online: bool
    log: Any

def run_single_keyword(
    keyword: str,
    output_dir: str,
    config: Optional[AlibabaConfig] = None,
    online: bool = False,
    headed: bool = False,
):
    config = config or AlibabaConfig()
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    state = StateManager.load(output_dir) or StateManager(output_dir=output_dir)
    if state.phase == "init":
        state.mark_phase("search")
    else:
        emit_event(logger, "resume.detected", {"phase": state.phase})

    opts = BrowserEngineOptions(headless=not headed, save_artifacts=True, artifacts_dir=str(out_path / "artifacts"))
    engine = BrowserEngine(options=opts)

    ctx = RecipeContext(keyword=keyword, engine=engine, state=state, config=config, online=online, log=logger)
    runner = PhaseRunner(ctx, log=logger)

    phases = [SearchPhase(), FiltersPhase(), LinksPhase(), ProductsPhase()]

    try:
        results = runner.run_phases(phases, start_at=state.phase)
        state.mark_phase("done")
        return results
    finally:
        engine.close()

def run_l3_batch(
    json_path: str,
    base_output_dir: str,
    config: Optional[AlibabaConfig] = None,
    start_from: int = 0,
    online: bool = False,
    headed: bool = False,
):
    from .core.tracking import TrackingStore

    with open(json_path, "r", encoding="utf-8") as f:
        l3_data = json.load(f)

    keywords = l3_data.get("keywords", [])
    tracking = TrackingStore(str(Path(base_output_dir) / "l3_tracking.json"))

    for i, kw in enumerate(keywords):
        if i < start_from: continue

        kw_slug = kw.replace(" ", "_").lower()
        kw_dir = str(Path(base_output_dir) / kw_slug)

        tracking.update_item(kw, "running", index=i, output_dir=kw_dir)

        try:
            run_single_keyword(kw, kw_dir, config=config, online=online, headed=headed)
            tracking.update_item(kw, "success")
        except Exception as e:
            tracking.update_item(kw, "failed", error=str(e))

    return tracking.data
