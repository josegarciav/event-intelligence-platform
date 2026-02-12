"""Configuration loader for the event intelligence platform."""

from functools import lru_cache
from pathlib import Path

import yaml


class Config:
    """Configuration for the event intelligence platform."""

    # 1. Setup Base Paths
    # This points to src/configs/
    CONFIG_DIR = Path(__file__).parent.resolve()
    # This points to the project root
    PROJECT_ROOT = CONFIG_DIR.parent.parent

    # 2. Define File Paths
    INGESTION_CONFIG_PATH = CONFIG_DIR / "ingestion.yaml"
    TAXONOMY_DATA_PATH = (
        PROJECT_ROOT / "src" / "assets" / "human_experience_taxonomy_master.json"
    )

    @classmethod
    @lru_cache
    def load_ingestion_config(cls) -> dict:
        """Load the YAML configuration for ingestion pipelines."""
        if not cls.INGESTION_CONFIG_PATH.exists():
            raise FileNotFoundError(f"Missing config at {cls.INGESTION_CONFIG_PATH}")

        with open(cls.INGESTION_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @classmethod
    def get_taxonomy_path(cls) -> Path:
        """Return the absolute path to the taxonomy JSON."""
        return cls.TAXONOMY_DATA_PATH
