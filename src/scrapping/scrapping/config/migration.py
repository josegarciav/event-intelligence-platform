"""
scrapping.config.migration

Config versioning and forward migrations.

We keep this simple:
- configs declare config_version
- we can upgrade older versions to the latest supported version
- migrations must be pure functions (dict -> dict)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

JsonDict = Dict[str, Any]

LATEST_VERSION = "1.0"
SUPPORTED_VERSIONS = {"1.0"}  # expand later: {"0.9", "1.0", "1.1"}


@dataclass(frozen=True)
class MigrationReport:
    source_id: str
    from_version: str
    to_version: str
    applied_steps: List[str]


def get_config_version(cfg: JsonDict) -> str:
    v = str(cfg.get("config_version", "1.0")).strip()
    return v or "1.0"


def migrate_to_latest(cfg: JsonDict) -> Tuple[JsonDict, MigrationReport]:
    """
    Upgrade a source config dict to the latest supported version.

    Returns:
      (new_cfg, report)
    """
    source_id = str(cfg.get("source_id", "<unknown>"))
    from_v = get_config_version(cfg)

    applied: List[str] = []

    # For now, 1.0 is baseline, but we keep the scaffold.
    new_cfg = dict(cfg)

    if from_v not in SUPPORTED_VERSIONS:
        # best-effort: attempt to interpret unknown versions as 1.0-like
        # but keep traceability.
        applied.append(f"unknown_version:{from_v}->assume:{LATEST_VERSION}")
        new_cfg["config_version"] = LATEST_VERSION
        return new_cfg, MigrationReport(source_id, from_v, LATEST_VERSION, applied)

    # Example future migration pattern:
    # if from_v == "0.9":
    #     new_cfg = _migrate_0_9_to_1_0(new_cfg); applied.append("0.9->1.0")
    #     from_v = "1.0"

    # Ensure version is set to latest
    if get_config_version(new_cfg) != LATEST_VERSION:
        new_cfg["config_version"] = LATEST_VERSION
        applied.append(f"set_version:{LATEST_VERSION}")

    return new_cfg, MigrationReport(
        source_id, get_config_version(cfg), LATEST_VERSION, applied
    )


# Example placeholder for future:
# def _migrate_0_9_to_1_0(cfg: JsonDict) -> JsonDict:
#     cfg = dict(cfg)
#     # rename old keys, move sections, etc.
#     return cfg
