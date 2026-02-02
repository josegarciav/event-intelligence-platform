"""
Scraper configuration loader.

Loads scraper configs from JSON files and creates ScraperConfig instances.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .event_scraper import ScraperConfig


# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SCRAPER_CONFIGS_DIR = PROJECT_ROOT / "scrapping" / "configs" / "sources"


def get_config_path(source_name: str) -> Path:
    """
    Get the path to a scraper config file.

    Args:
        source_name: Name of the source (e.g., "ra_co")

    Returns:
        Path to the config JSON file

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    config_path = SCRAPER_CONFIGS_DIR / f"{source_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Scraper config not found: {config_path}. "
            f"Available configs: {list_available_configs()}"
        )
    return config_path


def list_available_configs() -> list[str]:
    """List all available scraper config names."""
    if not SCRAPER_CONFIGS_DIR.exists():
        return []
    return [f.stem for f in SCRAPER_CONFIGS_DIR.glob("*.json")]


def load_config_raw(source_name: str) -> Dict[str, Any]:
    """
    Load raw config dict from JSON file.

    Args:
        source_name: Name of the source

    Returns:
        Raw config dictionary
    """
    config_path = get_config_path(source_name)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_event_scraper_config(
    source_name: str,
    *,
    city: Optional[str] = None,
    country_code: Optional[str] = None,
    max_pages: Optional[int] = None,
    headless: bool = True,
    **overrides: Any,
) -> ScraperConfig:
    """
    Load a scraper config from JSON and create a ScraperConfig instance.

    Args:
        source_name: Name of the source (e.g., "ra_co")
        city: City to scrape (e.g., "barcelona")
        country_code: Country code (e.g., "es")
        max_pages: Maximum listing pages to scrape
        headless: Run browser in headless mode
        **overrides: Additional config overrides

    Returns:
        ScraperConfig instance

    Example:
        >>> config = load_event_scraper_config(
        ...     "ra_co",
        ...     city="barcelona",
        ...     country_code="es",
        ...     max_pages=2
        ... )
    """
    raw_config = load_config_raw(source_name)

    # Extract values from config structure
    source_id = raw_config.get("source_id", source_name)

    # Get base URL from entrypoints
    entrypoints = raw_config.get("entrypoints", [])
    base_url = "https://ra.co/events"
    if entrypoints:
        url_template = entrypoints[0].get("url", "")
        # Extract base URL (remove template parameters)
        if "{" in url_template:
            base_url = url_template.split("{")[0].rstrip("/")
        else:
            base_url = url_template

    # Get discovery config
    discovery = raw_config.get("discovery", {})
    link_extract = discovery.get("link_extract", {})
    url_pattern = link_extract.get("pattern", r"/events/\d+")
    url_identifier = link_extract.get("identifier", "/events/")

    # Get engine config
    engine = raw_config.get("engine", {})
    timeout_s = engine.get("timeout_s", 30.0)
    rate_policy = engine.get("rate_limit_policy", {})
    min_delay_s = rate_policy.get("min_delay_s", 2.0)

    # Get default params from entrypoints
    default_params = {}
    if entrypoints:
        default_params = entrypoints[0].get("params", {})

    # Determine paging
    paging = entrypoints[0].get("paging", {}) if entrypoints else {}
    config_max_pages = paging.get("end", 5)

    return ScraperConfig(
        source_id=source_id,
        base_url=base_url,
        url_pattern=url_pattern,
        url_identifier=url_identifier,
        max_pages=max_pages if max_pages is not None else config_max_pages,
        timeout_s=timeout_s,
        min_delay_s=min_delay_s,
        headless=headless,
        city=city or default_params.get("city", "barcelona"),
        country_code=country_code or default_params.get("country_code", "es"),
    )
