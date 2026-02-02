"""
scrapping.storage.layouts

Defines the output folder layout and file naming conventions.

Default layout:
  results/
    run_<run_id>/
      run_meta.json
      run_report.json
      sources/
        <source_id>/
          meta.json
          raw_pages/
            listing/
              part-00000.jsonl
            detail/
              part-00000.jsonl
          links/
            extracted_links.jsonl
          items/
            items.jsonl
            items_valid.jsonl
            items_dropped.jsonl

Later we can add partitioning by date/hour, and parquet versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Layout:
    root: Path  # base results dir

    def run_dir(self, run_id: str) -> Path:
        return self.root / f"run_{run_id}"

    def sources_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "sources"

    def source_dir(self, run_id: str, source_id: str) -> Path:
        return self.sources_dir(run_id) / _safe_name(source_id)

    def source_meta_path(self, run_id: str, source_id: str) -> Path:
        return self.source_dir(run_id, source_id) / "meta.json"

    # raw pages
    def raw_pages_dir(self, run_id: str, source_id: str) -> Path:
        return self.source_dir(run_id, source_id) / "raw_pages"

    def raw_listing_dir(self, run_id: str, source_id: str) -> Path:
        return self.raw_pages_dir(run_id, source_id) / "listing"

    def raw_detail_dir(self, run_id: str, source_id: str) -> Path:
        return self.raw_pages_dir(run_id, source_id) / "detail"

    def raw_listing_path(self, run_id: str, source_id: str, part: int = 0, ext: str = "jsonl") -> Path:
        return self.raw_listing_dir(run_id, source_id) / f"part-{part:05d}.{ext}"

    def raw_detail_path(self, run_id: str, source_id: str, part: int = 0, ext: str = "jsonl") -> Path:
        return self.raw_detail_dir(run_id, source_id) / f"part-{part:05d}.{ext}"

    # links
    def links_dir(self, run_id: str, source_id: str) -> Path:
        return self.source_dir(run_id, source_id) / "links"

    def extracted_links_path(self, run_id: str, source_id: str, ext: str = "jsonl") -> Path:
        return self.links_dir(run_id, source_id) / f"extracted_links.{ext}"

    # items
    def items_dir(self, run_id: str, source_id: str) -> Path:
        return self.source_dir(run_id, source_id) / "items"

    def items_path(self, run_id: str, source_id: str, name: str = "items", ext: str = "jsonl") -> Path:
        return self.items_dir(run_id, source_id) / f"{name}.{ext}"

    # run-level
    def run_meta_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run_meta.json"

    def run_report_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run_report.json"


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(s: str) -> str:
    """
    Make safe folder names for source_id.
    """
    s = (s or "").strip()
    if not s:
        return "unknown_source"
    out = []
    for ch in s:
        if ch.isalnum() or ch in ("-", "_", "."):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)[:120]
