"""
scrapping.recipes.jobs_aggregator

A recipe for aggregating jobs from multiple heterogeneous sources.
Supports phased execution per source with checkpointing and resume.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence, List, Dict

from scrapping.engines.browser import BrowserEngine, BrowserEngineOptions
from scrapping.engines.http import HttpEngine, HttpEngineOptions
from scrapping.engines.base import BaseEngine, EngineContext
from scrapping.extraction.link_extractors import LinkExtractRequest, extract_links
from scrapping.extraction.parsers import select_text_bs4, bs4_soup, get_text_bs4
from scrapping.monitoring.events import emit_event
from scrapping.schemas.job_items import JobPostItem

from .core.state import StateManager
from .core.phases import Phase, PhaseRunner, PhaseResult
from .core.artifacts import write_jsonl, register_artifact

logger = logging.getLogger("scrapping.recipes.jobs_aggregator")

@dataclass
class JobSourceConfig:
    source_id: str
    entrypoints: List[Dict[str, Any]]
    engine: Dict[str, Any] = field(default_factory=dict)
    discovery: Dict[str, Any] = field(default_factory=dict)
    parsing: Dict[str, Any] = field(default_factory=dict)

    # Recipe specific overrides/controls
    checkpoint_every_n: int = 10
    min_description_len: int = 50

@dataclass
class JobRecipeContext:
    engine: BaseEngine
    state: StateManager
    config: JobSourceConfig
    online: bool
    log: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

class DiscoverListingPagesPhase:
    name = "discover_listing_pages"
    def run(self, ctx: JobRecipeContext) -> dict:
        cfg = ctx.config
        urls = []

        for ep in cfg.entrypoints:
            url_tpl = ep.get("url", "")
            paging = ep.get("paging", {})
            max_p = paging.get("pages", 1)
            mode = paging.get("mode", "page")
            step = paging.get("step", 1)

            for p in range(1, max_p + 1):
                if mode == "offset":
                    val = (p - 1) * step
                    url = url_tpl.replace("{offset}", str(val))
                else:
                    url = url_tpl.replace("{page}", str(p))

                if url not in urls:
                    urls.append(url)

        ctx.state.metadata["listing_urls"] = urls
        ctx.state.save()
        return {"urls_count": len(urls)}

class CollectJobLinksPhase:
    name = "collect_job_links"
    def run(self, ctx: JobRecipeContext) -> dict:
        cfg = ctx.config
        listing_urls = ctx.state.metadata.get("listing_urls", [])
        all_links = set(ctx.state.processed_urls)
        counts = {}

        link_extract = cfg.discovery.get("link_extract", {})

        for url in listing_urls:
            if ctx.online:
                res = ctx.engine.get(url)
                html = res.text
            else:
                fixture_path = Path(f"tests/fixtures/html/jobs/{cfg.source_id}/listing.html")
                if fixture_path.exists():
                    html = fixture_path.read_text()
                else:
                    html = '<html><a href="/job/1">Job 1</a></html>'

            req = LinkExtractRequest(
                html=html,
                base_url=url,
                method=link_extract.get("method", "regex"),
                pattern=link_extract.get("pattern"),
                selector=link_extract.get("selector")
            )
            links = extract_links(req)

            new_links = [l for l in links if l not in all_links]
            all_links.update(new_links)
            counts[url] = len(links)

            ctx.state.processed_urls = list(all_links)
            ctx.state.save()
            if not ctx.online: break

        with (Path(ctx.state.output_dir) / "jobs_links.json").open("w") as f:
            json.dump({"total": len(all_links), "per_page": counts, "links": list(all_links)}, f)

        return {"links_found": len(all_links)}

class ScrapeJobDetailsPhase:
    name = "scrape_job_details"
    def run(self, ctx: JobRecipeContext) -> dict:
        cfg = ctx.config
        links = ctx.state.processed_urls
        completed = set(ctx.state.metadata.get("completed_jobs", []))

        remaining = [l for l in links if l not in completed]

        count = 0
        valid_count = 0
        rejected_count = 0

        job_extract = cfg.parsing.get("item_extract", {})
        fields_map = job_extract.get("fields", {})

        products_file = Path(ctx.state.output_dir) / "jobs.jsonl"
        rejected_file = Path(ctx.state.output_dir) / "jobs_rejected.jsonl"

        max_items = ctx.metadata.get("max_items_total")

        for link in remaining:
            if max_items and count >= max_items:
                logger.info(f"Reached max items limit ({max_items})")
                break

            if ctx.online:
                res = ctx.engine.get(link)
                html = res.text
                final_url = res.final_url
            else:
                idx = links.index(link) + 1
                fixture_path = Path(f"tests/fixtures/html/jobs/{cfg.source_id}/detail{idx}.html")
                if fixture_path.exists():
                    html = fixture_path.read_text()
                else:
                    html = f"<html><title>Job {idx}</title><div class='company'>Company</div><div class='location'>Loc</div><div class='description'>Description for job {idx}... long enough.</div></html>"
                final_url = link

            raw_item = {
                "source_id": cfg.source_id,
                "url": final_url,
                "title": select_text_bs4(html, fields_map.get("title", {}).get("selector", "title")),
                "company": select_text_bs4(html, fields_map.get("company", {}).get("selector", ".company")),
                "location": select_text_bs4(html, fields_map.get("location", {}).get("selector", ".location")),
                "description": select_text_bs4(html, fields_map.get("description", {}).get("selector", ".description")),
                "raw_text": get_text_bs4(html),
                "listing_url": None,
                "extraction_meta": {
                    "engine": ctx.engine.name,
                    "selectors": fields_map
                }
            }

            try:
                item = JobPostItem(**raw_item)
                write_jsonl(products_file, [item.model_dump()])
                valid_count += 1
            except Exception as e:
                raw_item["_rejection_reason"] = str(e)
                write_jsonl(rejected_file, [raw_item])
                rejected_count += 1

            completed.add(link)
            count += 1

            if count % cfg.checkpoint_every_n == 0:
                ctx.state.metadata["completed_jobs"] = list(completed)
                ctx.state.save()
                emit_event(ctx.log, "checkpoint.saved", {"count": count})

        ctx.state.metadata["completed_jobs"] = list(completed)
        ctx.state.save()
        return {"jobs_scraped": count, "valid": valid_count, "rejected": rejected_count}

def run_jobs_recipe(
    source_configs: List[JobSourceConfig],
    output_root: str,
    online: bool = False,
    only_sources: Optional[List[str]] = None,
    max_items_total: Optional[int] = None
):
    from .core.tracking import TrackingStore

    out_root = Path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    tracking = TrackingStore(str(out_root / "jobs_tracking.json"))

    for cfg in source_configs:
        if only_sources and cfg.source_id not in only_sources:
            continue

        source_dir = out_root / cfg.source_id
        source_dir.mkdir(parents=True, exist_ok=True)

        tracking.update_item(cfg.source_id, "running")

        state = StateManager.load(str(source_dir)) or StateManager(output_dir=str(source_dir))
        if state.phase == "init":
            state.mark_phase("discover_listing_pages")
        else:
            emit_event(logger, "resume.detected", {"source": cfg.source_id, "phase": state.phase})

        # Build engine
        eng_cfg = cfg.engine
        engine_type = eng_cfg.get("type", "http")

        if engine_type == "browser":
            b_cfg = eng_cfg.get("browser", {})
            engine = BrowserEngine(options=BrowserEngineOptions(
                headless=b_cfg.get("headless", True),
                nav_timeout_s=b_cfg.get("timeout_s", 30.0)
            ))
        else:
            engine = HttpEngine(options=HttpEngineOptions(
                timeout_s=eng_cfg.get("timeout_s", 15.0),
                verify_ssl=eng_cfg.get("verify_ssl", True)
            ))

        try:
            # Pass metadata to context
            metadata = {"max_items_total": max_items_total}
            ctx = JobRecipeContext(engine=engine, state=state, config=cfg, online=online, log=logger, metadata=metadata)
            runner = PhaseRunner(ctx, log=logger)

            phases = [
                DiscoverListingPagesPhase(),
                CollectJobLinksPhase(),
                ScrapeJobDetailsPhase()
            ]

            results = runner.run_phases(phases, start_at=state.phase)
            state.mark_phase("done")
            tracking.update_item(cfg.source_id, "success", results=[r.__dict__ for r in results])

        except Exception as e:
            logger.exception(f"Source {cfg.source_id} failed")
            tracking.update_item(cfg.source_id, "failed", error=str(e))
        finally:
            engine.close()

    return tracking.data
