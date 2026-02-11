from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def write_jsonl(path: Path, items: Sequence[dict[str, Any]], append: bool = True):
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def write_summary_csv(
    path: Path, items: Sequence[dict[str, Any]], fields: Sequence[str] | None = None
):
    if not items:
        return

    if not fields:
        # Use keys from first item
        fields = list(items[0].keys())

    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(items)


def register_artifact(run_report: dict[str, Any], source_id: str, name: str, path: str):
    # This is a helper to update a standard run_report dict with custom recipe artifacts
    if "sources" not in run_report:
        run_report["sources"] = {}
    if source_id not in run_report["sources"]:
        run_report["sources"][source_id] = {"artifacts": {}}

    run_report["sources"][source_id]["artifacts"][name] = path
