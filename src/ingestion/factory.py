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
from pathlib import Path
from typing import Dict, Optional

import yaml

from src.ingestion.base_pipeline import BasePipeline, PipelineConfig
from src.ingestion.adapters import SourceType

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "ingestion.yaml"


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
        return [
            name for name, info in self.list_sources().items()
            if info["enabled"]
        ]

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

        pipeline_type = source_config.get("pipeline_type", source_config.get("type", "api"))

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
        from src.ingestion.pipelines.apis.base_api import create_api_pipeline_from_config

        return create_api_pipeline_from_config(source_name, source_config)

    def _create_scraper_pipeline(
        self,
        source_name: str,
        source_config: Dict,
    ) -> BasePipeline:
        """Create a scraper-based pipeline."""
        # For now, raise NotImplementedError - scraper pipelines
        # require HTML parser implementations specific to each source
        raise NotImplementedError(
            f"Scraper pipeline for '{source_name}' not yet implemented. "
            "Scraper pipelines require source-specific HTML parsing logic."
        )

    def create_all_enabled_pipelines(self) -> Dict[str, BasePipeline]:
        """
        Create all enabled pipelines.

        Returns:
            Dict mapping source_name -> BasePipeline instance
        """
        pipelines = {}

        for source_name in self.list_enabled_sources():
            try:
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


def create_pipeline(source_name: str, config_path: Optional[str] = None) -> BasePipeline:
    """
    Convenience function to create a pipeline by source name.

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
    Convenience function to create all enabled pipelines.

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
