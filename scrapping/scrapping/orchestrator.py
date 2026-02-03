"""
orchestrator.py

Loads configs, schedules work, aggregates results.

Core responsibilities:
- Validate config (lightweight V1 checks)
- For each source:
    - create appropriate engine (http/browser/hybrid)
    - run pipeline (run_pipeline_v1)
    - write artifacts using storage writers + layouts
    - collect metrics + logs + per-source report
- Write run_report.json + run_meta.json

This is a V1 orchestrator: simple and dependable.
Later:
- cron-like scheduling / daemon mode
- persistent dedupe store
- retries across sources
- distributed runs
"""

from __future__ import annotations

import platform
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scrapping.engines.http import HttpEngine, HttpEngineOptions
from scrapping.engines.browser import BrowserEngine, BrowserEngineOptions
from scrapping.engines.hybrid import HybridEngine, HybridEngineOptions

from scrapping.pipeline.stages import run_pipeline_v1
from scrapping.pipeline.dedupe import InMemoryDedupeStore

from scrapping.storage.layouts import Layout
from scrapping.storage.writers import (
    WriterOptions,
    fetchresult_to_raw_record,
    write_links,
    write_items,
    write_raw_pages_jsonl,
    write_run_meta,
    write_run_report,
    write_source_meta,
)

from scrapping.monitoring.logging import (
    LoggingOptions,
    setup_run_logger,
    add_source_file_handler,
    with_context,
)
from scrapping.monitoring.reporting import (
    RunReportBuilder,
    SourceReport,
    exception_to_error_dict,
)

# ---------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class OrchestratorOptions:
    results_dir: str = "results"
    parallelism: int = 16
    only_sources: Optional[List[str]] = None

    json_logs: bool = False
    strict: bool = False

    items_format_override: Optional[str] = None  # jsonl|csv|parquet
    dry_run: bool = False


# ---------------------------------------------------------------------
# Config validation (V1)
# ---------------------------------------------------------------------


def validate_config(cfg: Dict[str, Any], *, verbose: bool = False) -> Dict[str, Any]:
    """
    Minimal V1 validator.

    Expected config shape (V1):
      {
        "run": {... optional ...},
        "sources": [
           {
             "source_id": "xxx",
             "engine": {"type":"http|browser|hybrid", ...},
             "entrypoints": [{"url": "...", "paging": {...}}],
             "discovery": {"link_extract": {...}},
             "storage": {"items_format":"jsonl|csv|parquet"}
           }
        ]
      }
    """
    issues: List[Dict[str, Any]] = []

    if not isinstance(cfg, dict):
        return {
            "ok": False,
            "issues": [
                {
                    "level": "error",
                    "code": "bad_root",
                    "msg": "config root must be an object",
                }
            ],
        }

    sources = cfg.get("sources")
    if not isinstance(sources, list) or not sources:
        issues.append(
            {
                "level": "error",
                "code": "missing_sources",
                "msg": "config must contain non-empty 'sources' list",
            }
        )
        return {"ok": False, "issues": issues}

    seen_ids = set()
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            issues.append(
                {
                    "level": "error",
                    "code": "bad_source",
                    "msg": f"source[{i}] must be an object",
                }
            )
            continue

        sid = s.get("source_id")
        if not sid or not isinstance(sid, str):
            issues.append(
                {
                    "level": "error",
                    "code": "missing_source_id",
                    "msg": f"source[{i}] missing 'source_id'",
                }
            )
            continue

        if sid in seen_ids:
            issues.append(
                {
                    "level": "error",
                    "code": "duplicate_source_id",
                    "msg": f"duplicate source_id: {sid}",
                }
            )
        seen_ids.add(sid)

        eng = s.get("engine") or {}
        et = str(eng.get("type", "http")).lower().strip()
        if et not in ("http", "browser", "hybrid"):
            issues.append(
                {
                    "level": "error",
                    "code": "bad_engine_type",
                    "msg": f"{sid}: engine.type must be http|browser|hybrid",
                }
            )

        entrypoints = s.get("entrypoints")
        if not isinstance(entrypoints, list) or not entrypoints:
            issues.append(
                {
                    "level": "error",
                    "code": "missing_entrypoints",
                    "msg": f"{sid}: missing 'entrypoints' list",
                }
            )
        else:
            # check that at least one has url
            if not any(isinstance(ep, dict) and ep.get("url") for ep in entrypoints):
                issues.append(
                    {
                        "level": "error",
                        "code": "bad_entrypoints",
                        "msg": f"{sid}: entrypoints must include at least one object with 'url'",
                    }
                )

        discovery = s.get("discovery") or {}
        link_extract = (
            discovery.get("link_extract") if isinstance(discovery, dict) else None
        )
        if not isinstance(link_extract, dict):
            issues.append(
                {
                    "level": "warning",
                    "code": "missing_link_extract",
                    "msg": f"{sid}: discovery.link_extract not set; pipeline may find no links",
                }
            )
        else:
            method = str(link_extract.get("method", "regex")).lower()
            if method == "regex" and not link_extract.get("pattern"):
                issues.append(
                    {
                        "level": "warning",
                        "code": "regex_no_pattern",
                        "msg": f"{sid}: link_extract.method=regex but no pattern provided",
                    }
                )
            if method in ("css", "xpath") and not link_extract.get("selector"):
                issues.append(
                    {
                        "level": "warning",
                        "code": "selector_missing",
                        "msg": f"{sid}: link_extract.method={method} but no selector provided",
                    }
                )

    ok = not any(x["level"] == "error" for x in issues)
    out = {"ok": ok, "issues": issues}
    if verbose:
        out["sources_count"] = len(sources)
        out["source_ids"] = [s.get("source_id") for s in sources if isinstance(s, dict)]
    return out


# ---------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------


def doctor_environment(*, verbose: bool = False) -> Dict[str, Any]:
    """
    Checks environment readiness and optional dependencies.
    """
    info: Dict[str, Any] = {
        "python": sys.version,
        "platform": platform.platform(),
        "ok": True,
        "checks": {},
    }

    def _check(mod: str) -> Tuple[bool, str]:
        try:
            __import__(mod)
            return True, "ok"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    # required-ish for core
    for m in ["requests"]:
        ok, msg = _check(m)
        info["checks"][m] = {"ok": ok, "msg": msg}
        if not ok:
            info["ok"] = False

    # optional but recommended
    for m in ["bs4", "lxml", "trafilatura", "pyarrow", "pandas"]:
        ok, msg = _check(m)
        info["checks"][m] = {"ok": ok, "msg": msg}

    # browser stack
    ok_pw, msg_pw = _check("playwright")
    info["checks"]["playwright"] = {"ok": ok_pw, "msg": msg_pw}
    if ok_pw and verbose:
        # We cannot run `playwright install` here; just suggest.
        info["checks"]["playwright"][
            "hint"
        ] = "If browser binaries missing: run `playwright install`"

    return info


# ---------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------


class Orchestrator:
    def __init__(self, *, options: Optional[OrchestratorOptions] = None) -> None:
        self.options = options or OrchestratorOptions()

    def run(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        # Validate
        v = validate_config(cfg, verbose=False)
        if not v.get("ok", False):
            return {
                "ok": False,
                "run_id": None,
                "run_dir": None,
                "run_report_path": None,
                "summary": {"reason": "config_invalid", "validation": v},
            }

        # Build run_id
        run_id = self._make_run_id()
        layout = Layout(root=Path(self.options.results_dir))
        writer_opts = WriterOptions(strict=self.options.strict)

        # Setup logging + reporting
        log_opts = LoggingOptions(json_logs=self.options.json_logs)
        logger = setup_run_logger(layout, run_id=run_id, options=log_opts)
        log = with_context(logger, run_id=run_id)

        report = RunReportBuilder(run_id=run_id)
        report.meta.update(
            {
                "results_dir": str(Path(self.options.results_dir).resolve()),
                "parallelism": self.options.parallelism,
                "dry_run": self.options.dry_run,
            }
        )

        # run_meta.json (static run info)
        run_meta = {
            "run_id": run_id,
            "started_at_s": report.started_at_s,
            "host": platform.node(),
            "platform": platform.platform(),
            "python": sys.version,
        }
        write_run_meta(layout, run_id, run_meta, options=writer_opts)

        # Filter sources
        sources = cfg.get("sources") or []
        if self.options.only_sources:
            only = set(self.options.only_sources)
            sources = [
                s for s in sources if isinstance(s, dict) and s.get("source_id") in only
            ]

        if not sources:
            report.finish()
            run_report_dict = report.as_dict()
            rp = write_run_report(layout, run_id, run_report_dict, options=writer_opts)
            return {
                "ok": True,
                "run_id": run_id,
                "run_dir": str(layout.run_dir(run_id)),
                "run_report_path": str(rp),
                "summary": {"sources_total": 0, "sources_ok": 0, "sources_failed": 0},
            }

        # Shared dedupe store for the whole run (so cross-page duplicates drop)
        dedupe_store = InMemoryDedupeStore()

        overall_ok = True

        for s in sources:
            if not isinstance(s, dict):
                continue
            source_id = str(s.get("source_id"))
            slog = with_context(logger, run_id=run_id, source_id=source_id)

            # per-source log file
            add_source_file_handler(
                logger, layout, run_id=run_id, source_id=source_id, options=log_opts
            )

            # source meta
            try:
                write_source_meta(
                    layout, run_id, source_id, meta=s, options=writer_opts
                )
            except Exception as e:
                slog.error(
                    "Failed writing source meta", extra={"payload": {"error": str(e)}}
                )

            # SourceReport setup
            sr = SourceReport(source_id=source_id, ok=False)

            t0 = time.time()
            try:
                if self.options.dry_run:
                    slog.info("Dry run: skipping fetch/pipeline")
                    sr.ok = True
                    sr.stats = {"dry_run": True}
                    sr.timings = {"elapsed_s": time.time() - t0}
                    report.add_source(sr)
                    continue

                engine = self._build_engine_from_source(s)
                try:
                    slog.info("Running pipeline")
                    with report.metrics.time(
                        "source.run", labels={"source_id": source_id}
                    ):
                        artifacts = run_pipeline_v1(
                            s,
                            engine=engine,
                            parallelism=int(self.options.parallelism),
                            dedupe_store=dedupe_store,
                        )
                finally:
                    try:
                        engine.close()
                    except Exception:
                        pass

                # Write artifacts
                storage_cfg = s.get("storage") or {}
                items_fmt = (
                    self.options.items_format_override
                    or storage_cfg.get("items_format")
                    or "jsonl"
                )
                items_fmt = str(items_fmt).lower()

                # raw pages
                listing_records = [
                    {"url": lp.url, **fetchresult_to_raw_record(lp.fetch)}
                    for lp in artifacts.listing_pages
                ]
                detail_records = [
                    {"url": dp.url, **fetchresult_to_raw_record(dp.fetch)}
                    for dp in artifacts.detail_pages
                ]

                lp_paths = write_raw_pages_jsonl(
                    layout,
                    run_id,
                    source_id,
                    kind="listing",
                    pages=listing_records,
                    options=writer_opts,
                )
                dp_paths = write_raw_pages_jsonl(
                    layout,
                    run_id,
                    source_id,
                    kind="detail",
                    pages=detail_records,
                    options=writer_opts,
                )

                # links + items
                links_path = write_links(
                    layout,
                    run_id,
                    source_id,
                    artifacts.extracted_links,
                    options=writer_opts,
                )

                items_path = write_items(
                    layout,
                    run_id,
                    source_id,
                    name="items",
                    items=artifacts.items,
                    fmt=items_fmt,
                    options=writer_opts,
                )
                valid_path = write_items(
                    layout,
                    run_id,
                    source_id,
                    name="items_valid",
                    items=artifacts.valid_items,
                    fmt=items_fmt,
                    options=writer_opts,
                )
                dropped_path = write_items(
                    layout,
                    run_id,
                    source_id,
                    name="items_dropped",
                    items=artifacts.dropped_items,
                    fmt=items_fmt,
                    options=writer_opts,
                )

                # report stats
                sr.ok = True
                sr.stats = {
                    "pages_attempted": artifacts.stats.pages_attempted,
                    "pages_succeeded": artifacts.stats.pages_succeeded,
                    "detail_attempted": artifacts.stats.detail_attempted,
                    "detail_succeeded": artifacts.stats.detail_succeeded,
                    "links_found": artifacts.stats.links_found,
                    "items_parsed": artifacts.stats.items_parsed,
                    "items_valid": artifacts.stats.items_valid,
                    "items_saved": artifacts.stats.items_saved,
                    "errors": artifacts.stats.errors,
                }
                sr.artifacts = {
                    "raw_listing_parts": [str(p) for p in lp_paths],
                    "raw_detail_parts": [str(p) for p in dp_paths],
                    "links": str(links_path),
                    "items": str(items_path),
                    "items_valid": str(valid_path),
                    "items_dropped": str(dropped_path),
                }
                sr.timings = {"elapsed_s": time.time() - t0}

                slog.info(
                    "Source done",
                    extra={"payload": {"stats": sr.stats, "artifacts": sr.artifacts}},
                )

            except Exception as e:
                overall_ok = False
                sr.ok = False
                sr.errors.append(exception_to_error_dict(e))
                sr.timings = {"elapsed_s": time.time() - t0}
                slog.exception("Source failed", extra={"payload": {"error": str(e)}})

            report.add_source(sr)

        # Finalize run report
        report.finish()
        run_report_dict = report.as_dict()
        rp = write_run_report(layout, run_id, run_report_dict, options=writer_opts)

        # Summarize
        summary = run_report_dict.get("summary") or {}
        log.info(
            "Run completed",
            extra={"payload": {"summary": summary, "run_report_path": str(rp)}},
        )

        return {
            "ok": overall_ok,
            "run_id": run_id,
            "run_dir": str(layout.run_dir(run_id)),
            "run_report_path": str(rp),
            "summary": summary,
        }

    # -----------------------------------------------------------------
    # Engine factory
    # -----------------------------------------------------------------

    def _build_engine_from_source(self, source_cfg: Dict[str, Any]):
        eng = source_cfg.get("engine") or {}
        et = str(eng.get("type", "http")).lower().strip()

        timeout_s = float(eng.get("timeout_s", 15.0))
        verify_ssl = bool(eng.get("verify_ssl", True))
        user_agent = eng.get("user_agent")

        retry_policy = eng.get("retry_policy") or {}
        max_retries = int(retry_policy.get("max_retries", 3))
        backoff_mode = str(retry_policy.get("backoff", "exp"))
        retry_on_status = tuple(
            int(x)
            for x in (retry_policy.get("retry_on_status") or (429, 500, 502, 503, 504))
        )

        rate = eng.get("rate_limit_policy") or {}
        rps = rate.get("rps", None)
        burst = rate.get("burst", None)
        min_delay_s = rate.get("min_delay_s", None)
        jitter_s = rate.get("jitter_s", None)

        # HTTP options
        http_opts = HttpEngineOptions(
            timeout_s=timeout_s,
            verify_ssl=verify_ssl,
            max_retries=max_retries,
            backoff_mode=backoff_mode,
            retry_on_status=retry_on_status,
            rps=float(rps) if rps is not None else None,
            burst=int(burst) if burst is not None else None,
            min_delay_s=float(min_delay_s) if min_delay_s is not None else None,
            jitter_s=float(jitter_s) if jitter_s is not None else None,
            user_agent=user_agent,
        )

        # Browser options
        b = eng.get("browser") or {}
        browser_opts = BrowserEngineOptions(
            browser_name=str(b.get("browser_name", "chromium")),
            headless=bool(b.get("headless", True)),
            timeout_s=float(b.get("timeout_s", max(20.0, timeout_s))),
            max_retries=int(b.get("max_retries", 2)),
            backoff_mode=str(b.get("backoff_mode", "exp")),
            rps=float(rps) if rps is not None else None,
            burst=int(burst) if burst is not None else None,
            min_delay_s=float(min_delay_s) if min_delay_s is not None else 0.0,
            jitter_s=float(jitter_s) if jitter_s is not None else 0.25,
            user_agent=user_agent,
        )

        if et == "http":
            return HttpEngine(options=http_opts)
        if et == "browser":
            return BrowserEngine(options=browser_opts)
        if et == "hybrid":
            return HybridEngine(
                options=HybridEngineOptions(http=http_opts, browser=browser_opts)
            )

        # fallback
        return HttpEngine(options=http_opts)

    def _make_run_id(self) -> str:
        # readable + unique: 20260131_235959_ab12cd
        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        rnd = uuid.uuid4().hex[:6]
        return f"{ts}_{rnd}"
