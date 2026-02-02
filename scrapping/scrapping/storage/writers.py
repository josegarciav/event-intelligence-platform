"""
scrapping.storage.writers

Writers for pipeline artifacts:
- JSON
- JSONL
- CSV (optional pandas)
- Parquet (optional pyarrow or pandas+pyarrow)

This module is meant to be a dependency-tolerant layer:
- If pyarrow isn't installed, parquet writes fall back to jsonl (unless strict).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from scrapping.storage.layouts import Layout, ensure_parent


@dataclass(frozen=True)
class WriterOptions:
    strict: bool = False  # if True, missing optional deps raises
    default_encoding: str = "utf-8"

    # If data is large, jsonl chunking prevents huge single files
    jsonl_chunk_size: int = 5000


# ---------------------------------------------------------------------
# Generic low-level writers
# ---------------------------------------------------------------------

def write_json(path: Path, obj: Any, *, encoding: str = "utf-8") -> None:
    ensure_parent(path)
    with path.open("w", encoding=encoding) as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]], *, encoding: str = "utf-8") -> None:
    ensure_parent(path)
    with path.open("w", encoding=encoding) as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]], *, encoding: str = "utf-8") -> None:
    ensure_parent(path)
    with path.open("a", encoding=encoding) as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: List[Dict[str, Any]], *, options: WriterOptions) -> None:
    """
    CSV needs stable columns; pandas makes it easier.
    """
    try:
        import pandas as pd  # type: ignore
    except Exception as e:
        if options.strict:
            raise ImportError("pandas is required for CSV writing") from e
        # fallback: jsonl
        write_jsonl(path.with_suffix(".jsonl"), rows, encoding=options.default_encoding)
        return

    ensure_parent(path)
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding=options.default_encoding)


def write_parquet(path: Path, rows: List[Dict[str, Any]], *, options: WriterOptions) -> None:
    """
    Parquet writing: prefer pyarrow, fallback to pandas if it can.
    """
    # Try pyarrow directly
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
        ensure_parent(path)
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, path.as_posix())
        return
    except Exception as e_arrow:
        # Try pandas -> parquet
        try:
            import pandas as pd  # type: ignore
            ensure_parent(path)
            df = pd.DataFrame(rows)
            df.to_parquet(path, index=False)  # requires pyarrow or fastparquet anyway
            return
        except Exception as e_pd:
            if options.strict:
                raise RuntimeError(f"Parquet write failed: {e_arrow} | {e_pd}")
            # fallback jsonl
            write_jsonl(path.with_suffix(".jsonl"), rows, encoding=options.default_encoding)


# ---------------------------------------------------------------------
# Artifact writers (pipeline-level)
# ---------------------------------------------------------------------

def write_run_meta(layout: Layout, run_id: str, meta: Dict[str, Any], *, options: WriterOptions) -> Path:
    path = layout.run_meta_path(run_id)
    write_json(path, meta, encoding=options.default_encoding)
    return path


def write_run_report(layout: Layout, run_id: str, report: Dict[str, Any], *, options: WriterOptions) -> Path:
    path = layout.run_report_path(run_id)
    write_json(path, report, encoding=options.default_encoding)
    return path


def write_source_meta(layout: Layout, run_id: str, source_id: str, meta: Dict[str, Any], *, options: WriterOptions) -> Path:
    path = layout.source_meta_path(run_id, source_id)
    write_json(path, meta, encoding=options.default_encoding)
    return path


def write_links(layout: Layout, run_id: str, source_id: str, links: Sequence[str], *, options: WriterOptions) -> Path:
    path = layout.extracted_links_path(run_id, source_id, ext="jsonl")
    rows = [{"url": u} for u in links]
    write_jsonl(path, rows, encoding=options.default_encoding)
    return path


def write_raw_pages_jsonl(
    layout: Layout,
    run_id: str,
    source_id: str,
    *,
    kind: str,  # "listing" or "detail"
    pages: List[Dict[str, Any]],
    options: WriterOptions
) -> List[Path]:
    """
    Write raw pages as JSONL, chunked.

    Each page record should look like:
      {"url":..., "status_code":..., "ok":..., "final_url":..., "headers":..., "text":..., "timings":...}
    """
    if kind not in ("listing", "detail"):
        raise ValueError("kind must be listing or detail")

    out_paths: List[Path] = []
    chunk_size = max(1, int(options.jsonl_chunk_size))

    for i in range(0, len(pages), chunk_size):
        part = i // chunk_size
        chunk = pages[i:i + chunk_size]
        if kind == "listing":
            path = layout.raw_listing_path(run_id, source_id, part=part, ext="jsonl")
        else:
            path = layout.raw_detail_path(run_id, source_id, part=part, ext="jsonl")
        write_jsonl(path, chunk, encoding=options.default_encoding)
        out_paths.append(path)

    return out_paths


def write_items(
    layout: Layout,
    run_id: str,
    source_id: str,
    *,
    name: str,
    items: List[Dict[str, Any]],
    fmt: str,
    options: WriterOptions
) -> Path:
    """
    Write items in requested format, with graceful fallback.

    fmt: jsonl|csv|parquet
    """
    fmt = (fmt or "jsonl").lower().strip()
    path = layout.items_path(run_id, source_id, name=name, ext=fmt if fmt != "jsonl" else "jsonl")

    if fmt == "jsonl":
        write_jsonl(path, items, encoding=options.default_encoding)
        return path

    if fmt == "csv":
        write_csv(path, items, options=options)
        return path

    if fmt == "parquet":
        write_parquet(path, items, options=options)
        return path

    # unknown format -> fallback
    fallback = layout.items_path(run_id, source_id, name=name, ext="jsonl")
    write_jsonl(fallback, items, encoding=options.default_encoding)
    return fallback


# ---------------------------------------------------------------------
# Converters for pipeline artifacts
# ---------------------------------------------------------------------

def fetchresult_to_raw_record(fr: Any) -> Dict[str, Any]:
    """
    Convert FetchResult (from engines/base.py) to a serializable dict.
    """
    try:
        timings = getattr(fr, "timings", None)
        tdict = None
        if timings is not None:
            tdict = {
                "started_at_s": getattr(timings, "started_at_s", None),
                "ended_at_s": getattr(timings, "ended_at_s", None),
                "elapsed_s": getattr(timings, "elapsed_s", None),
            }
        return {
            "ok": bool(getattr(fr, "ok", False)),
            "final_url": getattr(fr, "final_url", None),
            "status_code": getattr(fr, "status_code", None),
            "headers": getattr(fr, "headers", {}) or {},
            "text": getattr(fr, "text", None),
            "error_type": getattr(fr, "error_type", None),
            "error_message": getattr(fr, "error_message", None),
            "timings": tdict,
        }
    except Exception:
        return {"ok": False, "error_type": "serialization_error"}
