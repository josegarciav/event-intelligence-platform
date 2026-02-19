"""Configuration loader for the event intelligence platform."""

from functools import lru_cache
from pathlib import Path

import yaml

from src.configs.settings import get_settings

settings = get_settings()


class Config:
    """Configuration for the event intelligence platform."""

    # 1. Setup Base Paths
    CONFIG_DIR = Path(__file__).parent.resolve()
    PROJECT_ROOT = settings.BASE_DIR

    # 2. Define File Paths
    INGESTION_CONFIG_PATH = settings.INGESTION_CONFIG_PATH
    TAXONOMY_DATA_PATH = settings.TAXONOMY_DATA_PATH

    @classmethod
    @lru_cache
    def load_ingestion_config(cls) -> dict:
        """Load the YAML configuration for ingestion pipelines."""
        if not cls.INGESTION_CONFIG_PATH.exists():
            raise FileNotFoundError(f"Missing config at {cls.INGESTION_CONFIG_PATH}")

        with open(cls.INGESTION_CONFIG_PATH, encoding="utf-8") as f:
            content = f.read()

            # Substitute environment variables from settings
            # This handles placeholders like ${DATABASE_URL} in the YAML
            for key, value in settings.model_dump().items():
                placeholder = f"${{{key}}}"
                if placeholder in content:
                    # Handle SecretStr
                    val_str = (
                        value.get_secret_value()
                        if hasattr(value, "get_secret_value")
                        else str(value)
                    )
                    content = content.replace(placeholder, val_str)

            return yaml.safe_load(content)

    @classmethod
    def get_taxonomy_path(cls) -> Path:
        """Return the absolute path to the taxonomy JSON."""
        return cls.TAXONOMY_DATA_PATH
