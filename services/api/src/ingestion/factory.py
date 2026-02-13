"""
Pipeline Factory for config-driven pipeline creation.

Provides a unified interface to create pipelines from YAML configuration.
Supports both API and scraper-based sources.

Usage:
    from src.ingestion.factory import create_pipeline, PipelineFactory

    # Create a single pipeline
    ra_co = create_pipeline("ra_co")
    result = ra_co.execute(area_id=20)

    # Create all enabled pipelines
    factory = PipelineFactory()
    pipelines = factory.create_all_enabled_pipelines()
"""

import logging
import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src.ingestion.base_pipeline import BasePipeline

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "ingestion.yaml"
SCRAPPING_SERVICE_DIR = Path(__file__).resolve().parents[3] / "scrapping"
DEFAULT_GENERATED_SCRAPER_CONFIG_DIR = (
    SCRAPPING_SERVICE_DIR / "generated_configs" / "sources"
)


class PipelineFactory:
    """
    Factory for creating pipelines from YAML configuration.

    Reads source configurations from ingestion.yaml and creates
    appropriate pipeline instances (API or scraper-based).
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the factory.

        Args:
            config_path: Path to ingestion.yaml. If not provided, uses default.
        """
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._config: Optional[Dict] = None

    @property
    def config(self) -> Dict:
        """Load and cache configuration."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_source_config(self, source_name: str) -> Optional[Dict]:
        """
        Get configuration for a specific source.

        Args:
            source_name: Name of the source (e.g., "ra_co")

        Returns:
            Source configuration dict or None if not found
        """
        sources = self.config.get("sources", {})
        return sources.get(source_name)

    def list_sources(self) -> Dict[str, Dict]:
        """
        List all configured sources with their status.

        Returns:
            Dict mapping source_name -> {enabled: bool, type: str}
        """
        sources = self.config.get("sources", {})
        return {
            name: {
                "enabled": cfg.get("enabled", True),
                "type": cfg.get("pipeline_type", cfg.get("type", "api")),
            }
            for name, cfg in sources.items()
        }

    def list_enabled_sources(self) -> list:
        """List names of all enabled sources."""
        return [name for name, info in self.list_sources().items() if info["enabled"]]

    def create_pipeline(self, source_name: str) -> BasePipeline:
        """
        Create a pipeline for the specified source.

        Args:
            source_name: Name of the source (e.g., "ra_co", "fever")

        Returns:
            Configured BasePipeline instance

        Raises:
            ValueError: If source not found or not enabled
        """
        source_config = self.get_source_config(source_name)
        if not source_config:
            raise ValueError(f"Source '{source_name}' not found in configuration")

        if not source_config.get("enabled", True):
            raise ValueError(f"Source '{source_name}' is not enabled")

        pipeline_type = source_config.get(
            "pipeline_type", source_config.get("type", "api")
        )

        if pipeline_type == "api":
            return self._create_api_pipeline(source_name, source_config)
        elif pipeline_type == "scraper":
            return self._create_scraper_pipeline(source_name, source_config)
        else:
            raise ValueError(f"Unknown pipeline type: {pipeline_type}")

    def _create_api_pipeline(
        self,
        source_name: str,
        source_config: Dict,
    ) -> BasePipeline:
        """Create an API-based pipeline."""
        from src.ingestion.pipelines.apis.base_api import (
            create_api_pipeline_from_config,
        )

        return create_api_pipeline_from_config(source_name, source_config)

    def _create_scraper_pipeline(
        self,
        source_name: str,
        source_config: Dict,
    ) -> BasePipeline:
        """Create a scraper-based pipeline."""
        config_path = self.bootstrap_scraper_source_config(source_name, source_config)
        # For now, raise NotImplementedError - scraper pipelines
        # require HTML parser implementations specific to each source
        raise NotImplementedError(
            f"Scraper pipeline for '{source_name}' not yet implemented. "
            f"Scrapping config is ready at: {config_path}"
        )

    def _collect_scraper_seed_urls(self, source_config: Dict[str, Any]) -> list[str]:
        """Collect candidate URLs used to auto-generate scrapping configs."""
        scraper_cfg = source_config.get("scraper", {}) or {}
        seed_urls = scraper_cfg.get("seed_urls", []) or []
        if isinstance(seed_urls, str):
            seed_urls = [seed_urls]

        if not seed_urls:
            endpoint = source_config.get("connection", {}).get("endpoint")
            if endpoint:
                seed_urls.append(endpoint)

        if not seed_urls and source_config.get("base_url"):
            seed_urls.append(source_config["base_url"])

        cleaned = []
        for url in seed_urls:
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                cleaned.append(url)
        return cleaned

    def _resolve_scraper_config_output_path(
        self,
        source_name: str,
        source_config: Dict[str, Any],
    ) -> Path:
        """Resolve where generated scrapping source config should be saved."""
        scraper_cfg = source_config.get("scraper", {}) or {}
        configured_path = scraper_cfg.get("config_output_path")
        if configured_path:
            return Path(configured_path).expanduser().resolve()
        return (DEFAULT_GENERATED_SCRAPER_CONFIG_DIR / f"{source_name}.json").resolve()

    def bootstrap_scraper_source_config(
        self,
        source_name: str,
        source_config: Dict[str, Any],
    ) -> Path:
        """
        Auto-generate and validate a scrapping source config for a scraper source.

        This allows adding new scraper sources via ingestion.yaml while keeping
        scrapping framework configs in sync automatically.
        """
        scraper_cfg = source_config.get("scraper", {}) or {}
        auto_generate = scraper_cfg.get("auto_generate_config", True)
        output_path = self._resolve_scraper_config_output_path(source_name, source_config)
        overwrite = scraper_cfg.get("overwrite_generated_config", False)

        if output_path.exists() and not auto_generate:
            return output_path
        if output_path.exists() and not overwrite:
            return output_path

        seed_urls = self._collect_scraper_seed_urls(source_config)
        if not seed_urls:
            raise ValueError(
                f"Cannot auto-generate scraper config for '{source_name}': "
                "no valid seed URL found. Set scraper.seed_urls in ingestion.yaml."
            )

        generated_config: Dict[str, Any]
        load_sources_fn = None
        load_result = None
        try:
            from scrapping.ai.config_agent import ConfigAgent
            from scrapping.config.loader import load_sources

            proposal = ConfigAgent().propose_source(seed_urls, source_id=source_name)
            generated_config = proposal.source_config
            generated_config["enabled"] = bool(source_config.get("enabled", True))
            # scrapping schema expects string config_version.
            generated_config["config_version"] = str(
                generated_config.get("config_version", "1.0")
            )
            load_sources_fn = load_sources
        except ImportError:
            # Fallback template keeps onboarding unblocked even when scrapping is
            # not installed in the current runtime environment.
            generated_config = {
                "config_version": "1.0",
                "source_id": source_name,
                "enabled": bool(source_config.get("enabled", True)),
                "engine": {"type": "http", "timeout_s": 15, "verify_ssl": True},
                "entrypoints": [{"url": seed_urls[0]}],
                "discovery": {
                    "link_extract": {
                        "method": "regex",
                        "pattern": ".*",
                        "identifier": "",
                    }
                },
                "storage": {"items_format": "jsonl"},
            }
            logger.warning(
                "scrapping package not importable; wrote fallback generated config for '%s'",
                source_name,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(generated_config, f, indent=2, ensure_ascii=True)

        if load_sources_fn:
            load_result = load_sources_fn(config_path=output_path)
        if load_result and load_result.errors:
            raise ValueError(
                f"Generated scrapping config for '{source_name}' is invalid: "
                f"{'; '.join(load_result.errors)}"
            )

        if load_result and load_result.warnings:
            logger.warning(
                "Generated scrapping config for '%s' has warnings: %s",
                source_name,
                "; ".join(load_result.warnings),
            )
        logger.info(
            "Generated scrapping config for '%s' at %s",
            source_name,
            output_path,
        )
        return output_path

    def create_all_enabled_pipelines(self) -> Dict[str, BasePipeline]:
        """
        Create all enabled pipelines.

        Returns:
            Dict mapping source_name -> BasePipeline instance
        """
        pipelines = {}

        for source_name in self.list_enabled_sources():
            try:
                source_config = self.get_source_config(source_name) or {}
                pipeline_type = source_config.get(
                    "pipeline_type", source_config.get("type", "api")
                )
                if pipeline_type == "scraper":
                    self.bootstrap_scraper_source_config(source_name, source_config)
                    logger.info(
                        "Bootstrapped scraper config for '%s' (pipeline creation skipped)",
                        source_name,
                    )
                    continue
                pipeline = self.create_pipeline(source_name)
                pipelines[source_name] = pipeline
                logger.info(f"Created pipeline: {source_name}")
            except Exception as e:
                logger.warning(f"Failed to create pipeline '{source_name}': {e}")

        return pipelines

    def reload_config(self) -> None:
        """Reload configuration from disk."""
        self._config = None


# Module-level factory instance
_factory: Optional[PipelineFactory] = None


def get_factory(config_path: Optional[str] = None) -> PipelineFactory:
    """
    Get or create the module-level factory instance.

    Args:
        config_path: Optional config path (only used if creating new factory)

    Returns:
        PipelineFactory instance
    """
    global _factory
    if _factory is None or config_path:
        _factory = PipelineFactory(config_path)
    return _factory


def create_pipeline(
    source_name: str, config_path: Optional[str] = None
) -> BasePipeline:
    """
    Create a pipeline by source name.

    Args:
        source_name: Name of the source (e.g., "ra_co")
        config_path: Optional path to ingestion.yaml

    Returns:
        Configured BasePipeline instance

    Example:
        >>> from src.ingestion.factory import create_pipeline
        >>> ra_co = create_pipeline("ra_co")
        >>> result = ra_co.execute(area_id=20)
    """
    factory = get_factory(config_path)
    return factory.create_pipeline(source_name)


def create_all_pipelines(config_path: Optional[str] = None) -> Dict[str, BasePipeline]:
    """
    Create all enabled pipelines.

    Args:
        config_path: Optional path to ingestion.yaml

    Returns:
        Dict mapping source_name -> BasePipeline instance

    Example:
        >>> from src.ingestion.factory import create_all_pipelines
        >>> pipelines = create_all_pipelines()
        >>> for name, pipeline in pipelines.items():
        ...     result = pipeline.execute()
    """
    factory = get_factory(config_path)
    return factory.create_all_enabled_pipelines()
