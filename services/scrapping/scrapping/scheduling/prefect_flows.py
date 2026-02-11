"""
scrapping.scheduling.prefect_flows

Optional: Prefect flows for orchestrating scrapes.

Design goals:
- Do NOT require Prefect for core library usage.
- If Prefect isn't installed, importing this module should still work enough
  to show a clear error when trying to build/run flows.
- Reuse the same orchestrator and pipeline logic (single source execution).

Typical usage (local):
    from scrapping.scheduling.prefect_flows import build_scrap_flow
    flow = build_scrap_flow(config_dict, results_dir="results")
    flow()  # run locally

Typical usage (deployment):
- register or serve the flow using Prefect tooling (outside this module).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Core (always available)
from scrapping.orchestrator import Orchestrator, OrchestratorOptions, validate_config

# -----------------------------
# Prefect import (optional)
# -----------------------------

_PREFECT_AVAILABLE = True
_PREFECT_IMPORT_ERROR: str | None = None

try:
    # Prefect 2.x
    from prefect import flow, get_run_logger, task  # type: ignore
except Exception as e:
    _PREFECT_AVAILABLE = False
    _PREFECT_IMPORT_ERROR = f"{type(e).__name__}: {e}"

    # Lightweight fallbacks so module import doesn't explode
    def flow(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn

        return _decorator

    def task(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn

        return _decorator

    def get_run_logger():  # type: ignore
        import logging

        return logging.getLogger("prefect_missing")


def _require_prefect() -> None:
    if not _PREFECT_AVAILABLE:
        raise ImportError(
            "Prefect is not installed (or failed to import). "
            f"Install with `pip install prefect`. Details: {_PREFECT_IMPORT_ERROR}"
        )


# -----------------------------
# Options for flow build
# -----------------------------


@dataclass(frozen=True)
class PrefectFlowOptions:
    """
    Controls how Prefect runs the scraping flow.

    - per_source_tasks: if True, create one task per source (nice in Prefect UI)
    - only_sources: optional list of source_ids to include
    """

    per_source_tasks: bool = True
    only_sources: list[str] | None = None

    parallelism: int = 16
    results_dir: str = "results"
    json_logs: bool = False
    strict: bool = False

    items_format_override: str | None = None


# -----------------------------
# Tasks
# -----------------------------


@task(name="validate_config", retries=0)
def validate_config_task(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Validate config inside Prefect.
    """
    _require_prefect()
    res = validate_config(cfg, verbose=False)
    if not res.get("ok", False):
        # Fail task so flow fails (visible in Prefect UI)
        raise ValueError(f"Config invalid: {res}")
    return res


@task(name="run_sources", retries=0)
def run_sources_task(cfg: dict[str, Any], opts: PrefectFlowOptions) -> dict[str, Any]:
    """
    Run full orchestrator for all sources in a single task.
    """
    _require_prefect()
    logger = get_run_logger()
    logger.info("Starting orchestrator run (single task)")

    orch_opts = OrchestratorOptions(
        results_dir=opts.results_dir,
        parallelism=opts.parallelism,
        only_sources=opts.only_sources,
        json_logs=opts.json_logs,
        strict=opts.strict,
        items_format_override=opts.items_format_override,
        dry_run=False,
    )
    orch = Orchestrator(options=orch_opts)
    out = orch.run(cfg)
    if not out.get("ok", False):
        raise RuntimeError(f"Run failed: {out}")
    return out


@task(name="run_one_source", retries=0)
def run_one_source_task(
    cfg: dict[str, Any], source_id: str, opts: PrefectFlowOptions
) -> dict[str, Any]:
    """
    Run orchestrator but restricted to a single source.
    """
    _require_prefect()
    logger = get_run_logger()
    logger.info(f"Running source: {source_id}")

    orch_opts = OrchestratorOptions(
        results_dir=opts.results_dir,
        parallelism=opts.parallelism,
        only_sources=[source_id],
        json_logs=opts.json_logs,
        strict=opts.strict,
        items_format_override=opts.items_format_override,
        dry_run=False,
    )
    orch = Orchestrator(options=orch_opts)
    out = orch.run(cfg)

    # Note: out contains a whole run folder even for single source.
    # In Prefect UI, this gives a nice per-source artifact structure.
    if not out.get("ok", False):
        raise RuntimeError(f"Source failed: {source_id} -> {out}")
    return out


# -----------------------------
# Flow factory
# -----------------------------


def build_scrap_flow(
    cfg: dict[str, Any],
    *,
    name: str = "scrap_flow",
    options: PrefectFlowOptions | None = None,
):
    """
    Returns a Prefect flow function.

    If Prefect isn't installed, calling the returned function will raise a helpful error.
    """
    options = options or PrefectFlowOptions()

    @flow(name=name)
    def _flow():
        _require_prefect()

        _ = validate_config_task(cfg)

        sources = cfg.get("sources") or []
        source_ids = [
            s.get("source_id")
            for s in sources
            if isinstance(s, dict) and s.get("source_id")
        ]

        if options.only_sources:
            allow = set(options.only_sources)
            source_ids = [sid for sid in source_ids if sid in allow]

        if not options.per_source_tasks:
            # One big orchestrator run
            return run_sources_task(cfg, options)

        # One Prefect task per source (nice observability)
        outs = []
        for sid in source_ids:
            outs.append(run_one_source_task(cfg, str(sid), options))
        return {"sources": source_ids, "runs": outs}

    return _flow


# -----------------------------
# Convenience helper
# -----------------------------


def run_prefect_flow_from_config_path(
    config_path: str,
    *,
    results_dir: str = "results",
    only_sources: list[str] | None = None,
    per_source_tasks: bool = True,
) -> Any:
    """
    Convenience for local usage:
        python -c "from scrapping.scheduling.prefect_flows import run_prefect_flow_from_config_path; run_prefect_flow_from_config_path('config.json')"
    """
    p = Path(config_path)
    with p.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    flow_opts = PrefectFlowOptions(
        per_source_tasks=per_source_tasks,
        only_sources=only_sources,
        results_dir=results_dir,
    )
    fflow = build_scrap_flow(cfg, options=flow_opts)
    return fflow()
