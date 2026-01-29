# normalization/taxonomy.py
"""
Builds and provides access to the Human Experience Taxonomy index.
"""

import json
from pathlib import Path
from typing import Dict, Set, List, Any
from functools import lru_cache

from src.configs.config import Config

TAXONOMY_PATH = Config.get_taxonomy_path()


def _normalize_primary_key(label: str) -> str:
    """Normalize category label to index key (lowercase, ' & ' -> '_', ' ' -> '_')."""
    return label.lower().replace(" & ", "_").replace(" ", "_")


@lru_cache
def load_taxonomy() -> dict:
    """
    Load and cache the Human Experience Taxonomy.
    """
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_taxonomy_index() -> Dict[str, Set[str]]:
    """
    Builds a mapping:
    primary_category -> set(subcategory_ids)
    """
    taxonomy = load_taxonomy()
    index: Dict[str, Set[str]] = {}

    for cat in taxonomy["categories"]:
        primary = _normalize_primary_key(cat["category"])
        index[primary] = {sub["id"] for sub in cat.get("subcategories", [])}

    return index


@lru_cache
def get_all_subcategory_options() -> List[Dict[str, Any]]:
    """
    Returns a flat list of all subcategory options from the taxonomy.

    Each option is a dict with:
      - "id": subcategory id (e.g. "1.4")
      - "name": human-readable name (e.g. "Music & Rhythm Play")
      - "primary_category": taxonomy primary key (e.g. "play_and_pure_fun")
    """
    taxonomy = load_taxonomy()
    out: List[Dict[str, Any]] = []
    for cat in taxonomy["categories"]:
        primary = _normalize_primary_key(cat["category"])
        for sub in cat.get("subcategories", []):
            out.append({
                "id": sub["id"],
                "name": sub["name"],
                "primary_category": primary,
            })
    return out


def get_all_subcategory_ids() -> Set[str]:
    """
    Returns the set of all valid subcategory ids (all available options).
    """
    return {opt["id"] for opt in get_all_subcategory_options()}
