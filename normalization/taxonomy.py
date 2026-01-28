# normalization/taxonomy.py
"""
Builds and provides access to the Human Experience Taxonomy index.
"""

import json
from pathlib import Path
from typing import Dict, Set
from functools import lru_cache

TAXONOMY_PATH = Path("normalization/human_experience_taxonomy_master.json")


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
        primary = cat["category"].lower().replace(" & ", "_").replace(" ", "_")
        index[primary] = {
            sub["id"] for sub in cat.get("subcategories", [])
        }

    return index
