"""Centralized settings management for the Event Intelligence API."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import make_url


class Settings(BaseSettings):
    """
    Application settings powered by pydantic-settings.

    Loads configuration from environment variables and a .env file located
    in the services/api directory.
    """

    # -------------------------------------------------------------------------
    # ENVIRONMENT
    # -------------------------------------------------------------------------
    ENV: str = "development"
    DEBUG: bool = True

    # -------------------------------------------------------------------------
    # DATABASE
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(..., min_length=1)

    # -------------------------------------------------------------------------
    # SOURCE API KEYS
    # -------------------------------------------------------------------------
    RA_CO_API_KEY: SecretStr | None = None
    MEETUP_API_KEY: SecretStr | None = None
    TICKETMASTER_API_KEY: SecretStr | None = None

    # -------------------------------------------------------------------------
    # ENRICHMENT SERVICES
    # -------------------------------------------------------------------------
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    GEOCODING_API_KEY: SecretStr | None = None

    # -------------------------------------------------------------------------
    # MONITORING & ALERTING
    # -------------------------------------------------------------------------
    SENTRY_DSN: str | None = None
    SLACK_WEBHOOK: SecretStr | None = None

    # -------------------------------------------------------------------------
    # PATHS
    # -------------------------------------------------------------------------
    # BASE_DIR points to services/api
    BASE_DIR: Path = Path(__file__).resolve().parents[2]

    TAXONOMY_DATA_PATH: Path = (
        BASE_DIR / "src" / "assets" / "human_experience_taxonomy_master.json"
    )
    INGESTION_CONFIG_PATH: Path = BASE_DIR / "src" / "configs" / "ingestion.yaml"

    # -------------------------------------------------------------------------
    # CONFIGURATION
    # -------------------------------------------------------------------------
    model_config = SettingsConfigDict(
        # Look for .env in the services/api directory
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        # Allow extra fields in .env but ignore them in the model
        extra="ignore",
    )

    def get_psycopg2_params(self) -> dict:
        """
        Parse DATABASE_URL into psycopg2-compatible connection parameters.

        Uses sqlalchemy.make_url for robust parsing of complex connection strings.

        Returns
        -------
        dict
            psycopg2 connection arguments (host, port, dbname, user, password).
        """
        url = make_url(self.DATABASE_URL)
        return {
            "host": url.host,
            "port": url.port,
            "dbname": url.database,
            "user": url.username,
            "password": url.password,
        }


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns
    -------
    Settings
        The singleton settings instance.
    """
    return Settings()
