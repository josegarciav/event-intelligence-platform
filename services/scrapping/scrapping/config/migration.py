"""
scrapping.config.migration

Minimal config migration system.
"""

from __future__ import annotations

from typing import Any

CURRENT_CONFIG_VERSION = 1


def migrate_config(cfg: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Migrate config to current version.
    Returns (migrated_cfg, was_migrated).
    """
    if not isinstance(cfg, dict):
        return cfg, False

    # Handle multi-source config file
    if "sources" in cfg and isinstance(cfg["sources"], list):
        was_any_migrated = False
        new_sources = []
        for s in cfg["sources"]:
            new_s, was_migrated = _migrate_source(s)
            new_sources.append(new_s)
            if was_migrated:
                was_any_migrated = True
        cfg["sources"] = new_sources
        return cfg, was_any_migrated
    else:
        # Assume it's a single source config
        return _migrate_source(cfg)


def _migrate_source(s: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if not isinstance(s, dict):
        return s, False

    version = s.get("config_version", 0)
    if isinstance(version, str):
        try:
            version = int(float(version))
        except ValueError:
            version = 1  # assume current if malformed string

    if version >= CURRENT_CONFIG_VERSION:
        return s, False

    # Migration 0 -> 1
    new_s = dict(s)

    # Example: Move storage.items_format to storage.items.format
    storage = new_s.get("storage")
    if isinstance(storage, dict) and "items_format" in storage:
        items_fmt = storage.pop("items_format")
        if "items" not in storage:
            storage["items"] = {}
        if isinstance(storage["items"], dict):
            storage["items"]["format"] = items_fmt

    # Example: Ensure engine.type exists
    engine = new_s.get("engine")
    if engine is None:
        new_s["engine"] = {"type": "http"}
    elif isinstance(engine, dict) and "type" not in engine:
        engine["type"] = "http"

    new_s["config_version"] = CURRENT_CONFIG_VERSION
    return new_s, True
