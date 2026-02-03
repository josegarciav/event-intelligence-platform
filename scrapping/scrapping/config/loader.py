"""
scrapping.config.loader

Load JSON config(s) from one file or multiple files via glob.
Supports:
- file contains a single object  -> one SourceConfig
- file contains an array of objects -> many SourceConfig

Also supports:
- per-source migration to latest version
- validation via pydantic models
- optional strict mode (warnings become errors)

This module returns both:
- parsed SourceConfig objects
- rich metadata: files loaded, warnings, migration reports
"""

from __future__ import annotations

import glob
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError

from .migration import migrate_to_latest
from .schema import SourceConfig

JsonDict = Dict[str, Any]


@dataclass(frozen=True)
class LoadOptions:
    only_source_id_contains: Optional[str] = None
    max_sources: Optional[int] = None
    strict: bool = False  # treat warnings as errors


@dataclass(frozen=True)
class LoadResult:
    sources: List[SourceConfig]
    meta: JsonDict
    warnings: List[str]
    errors: List[str]


def load_sources(
    *,
    config_path: Optional[Union[str, Path]] = None,
    configs_glob: Optional[str] = None,
    options: Optional[LoadOptions] = None,
) -> LoadResult:
    """
    Load and validate SourceConfig(s).

    Raises nothing by default; returns ok/not ok via errors list.
    """
    options = options or LoadOptions()

    paths = _resolve_paths(config_path=config_path, configs_glob=configs_glob)
    warnings: List[str] = []
    errors: List[str] = []

    loaded_files: List[str] = []
    migration_reports: List[JsonDict] = []

    raw_source_dicts: List[JsonDict] = []
    for p in paths:
        loaded_files.append(str(p))
        data = _read_json(p)
        if isinstance(data, dict):
            raw_source_dicts.append(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    raw_source_dicts.append(item)
                else:
                    errors.append(f"{p}: config array contains non-object item")
        else:
            errors.append(f"{p}: config must be an object or an array of objects")

    # Apply enabled filter + selection early (before heavy validation)
    raw_source_dicts = [d for d in raw_source_dicts if bool(d.get("enabled", True))]

    if options.only_source_id_contains:
        needle = options.only_source_id_contains.lower()
        raw_source_dicts = [
            d for d in raw_source_dicts if needle in str(d.get("source_id", "")).lower()
        ]

    if options.max_sources is not None:
        raw_source_dicts = raw_source_dicts[: int(options.max_sources)]

    # Migrate + validate
    sources: List[SourceConfig] = []
    for d in raw_source_dicts:
        migrated, report = migrate_to_latest(d)
        migration_reports.append(
            {
                "source_id": report.source_id,
                "from_version": report.from_version,
                "to_version": report.to_version,
                "applied_steps": report.applied_steps,
            }
        )

        # loader-level warnings
        if migrated.get("engine", {}).get("type") == "browser" and not migrated.get(
            "engine", {}
        ).get("browser"):
            warnings.append(
                f"{migrated.get('source_id','<no source_id>')}: engine.browser not set (recommended: seleniumbase|playwright)"
            )

        try:
            sources.append(SourceConfig.model_validate(migrated))
        except ValidationError as ve:
            errors.append(f"{migrated.get('source_id','<no source_id>')}: {ve}")

    # strict mode converts warnings -> errors
    if options.strict and warnings:
        errors.extend([f"STRICT: {w}" for w in warnings])

    meta: JsonDict = {
        "files": loaded_files,
        "matched_files": len(loaded_files),
        "sources_loaded": len(sources),
        "migrations": migration_reports,
    }

    return LoadResult(sources=sources, meta=meta, warnings=warnings, errors=errors)


def _resolve_paths(
    *, config_path: Optional[Union[str, Path]], configs_glob: Optional[str]
) -> List[Path]:
    if config_path and configs_glob:
        raise ValueError("Provide only one of config_path or configs_glob")

    if config_path:
        p = Path(config_path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Config not found: {p}")
        return [p]

    if configs_glob:
        matches = sorted(glob.glob(configs_glob))
        if not matches:
            raise FileNotFoundError(f"No config files matched glob: {configs_glob}")
        return [Path(m).expanduser().resolve() for m in matches]

    raise ValueError("You must provide config_path or configs_glob")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
