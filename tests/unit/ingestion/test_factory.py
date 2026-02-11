"""
Unit tests for the factory module.

Tests for PipelineFactory and convenience functions.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# =============================================================================
# TEST CONFIG FIXTURES
# =============================================================================


@pytest.fixture
def sample_config():
    """Sample ingestion config for testing."""
    return {
        "sources": {
            "test_api": {
                "enabled": True,
                "pipeline_type": "api",
                "base_url": "https://api.example.com",
                "endpoint": "/events",
            },
            "test_disabled": {
                "enabled": False,
                "pipeline_type": "api",
                "base_url": "https://api.disabled.com",
            },
            "test_scraper": {
                "enabled": True,
                "pipeline_type": "scraper",
                "base_url": "https://example.com",
            },
            "test_legacy": {
                "enabled": True,
                "type": "api",  # Legacy 'type' field
                "base_url": "https://legacy.example.com",
            },
        }
    }


@pytest.fixture
def config_file(sample_config):
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_config, f)
        yield f.name


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestPipelineFactoryInit:
    """Tests for PipelineFactory initialization."""

    def test_init_with_custom_path(self, config_file):
        """Should accept custom config path."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        assert factory.config_path == Path(config_file)

    def test_init_uses_default_path(self):
        """Should use default path when not specified."""
        from src.ingestion.factory import PipelineFactory, DEFAULT_CONFIG_PATH

        factory = PipelineFactory()
        assert factory.config_path == DEFAULT_CONFIG_PATH

    def test_config_not_loaded_until_accessed(self, config_file):
        """Should lazy-load config."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        assert factory._config is None

        # Access config triggers load
        _ = factory.config
        assert factory._config is not None


class TestLoadConfig:
    """Tests for config loading."""

    def test_load_valid_config(self, config_file, sample_config):
        """Should load valid YAML config."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        config = factory.config

        assert "sources" in config
        assert "test_api" in config["sources"]

    def test_load_missing_config_raises(self):
        """Should raise FileNotFoundError for missing config."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path="/nonexistent/path.yaml")

        with pytest.raises(FileNotFoundError):
            _ = factory.config

    def test_config_caching(self, config_file):
        """Should cache config after first load."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)

        config1 = factory.config
        config2 = factory.config

        assert config1 is config2


class TestGetSourceConfig:
    """Tests for get_source_config method."""

    def test_get_existing_source(self, config_file, sample_config):
        """Should return config for existing source."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        config = factory.get_source_config("test_api")

        assert config is not None
        assert config["base_url"] == "https://api.example.com"

    def test_get_nonexistent_source(self, config_file):
        """Should return None for nonexistent source."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        config = factory.get_source_config("nonexistent")

        assert config is None


class TestListSources:
    """Tests for list_sources method."""

    def test_list_all_sources(self, config_file, sample_config):
        """Should list all configured sources."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        sources = factory.list_sources()

        assert len(sources) == 4
        assert "test_api" in sources
        assert "test_disabled" in sources
        assert "test_scraper" in sources

    def test_list_sources_includes_enabled_status(self, config_file):
        """Should include enabled status."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        sources = factory.list_sources()

        assert sources["test_api"]["enabled"] is True
        assert sources["test_disabled"]["enabled"] is False

    def test_list_sources_includes_type(self, config_file):
        """Should include pipeline type."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        sources = factory.list_sources()

        assert sources["test_api"]["type"] == "api"
        assert sources["test_scraper"]["type"] == "scraper"

    def test_list_sources_handles_legacy_type(self, config_file):
        """Should handle legacy 'type' field."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        sources = factory.list_sources()

        assert sources["test_legacy"]["type"] == "api"


class TestListEnabledSources:
    """Tests for list_enabled_sources method."""

    def test_list_only_enabled(self, config_file):
        """Should list only enabled sources."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        enabled = factory.list_enabled_sources()

        assert "test_api" in enabled
        assert "test_scraper" in enabled
        assert "test_legacy" in enabled
        assert "test_disabled" not in enabled

    def test_list_enabled_returns_list(self, config_file):
        """Should return a list."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        enabled = factory.list_enabled_sources()

        assert isinstance(enabled, list)


class TestCreatePipeline:
    """Tests for create_pipeline method."""

    def test_create_nonexistent_raises(self, config_file):
        """Should raise ValueError for nonexistent source."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)

        with pytest.raises(ValueError, match="not found"):
            factory.create_pipeline("nonexistent")

    def test_create_disabled_raises(self, config_file):
        """Should raise ValueError for disabled source."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)

        with pytest.raises(ValueError, match="not enabled"):
            factory.create_pipeline("test_disabled")

    def test_create_unknown_type_raises(self, config_file):
        """Should raise ValueError for unknown pipeline type."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        # Modify config to have unknown type
        factory.config["sources"]["test_api"]["pipeline_type"] = "unknown"

        with pytest.raises(ValueError, match="Unknown pipeline type"):
            factory.create_pipeline("test_api")

    @patch("src.ingestion.factory.PipelineFactory._create_api_pipeline")
    def test_create_api_pipeline_dispatches(self, mock_create, config_file):
        """Should dispatch to _create_api_pipeline for API type."""
        from src.ingestion.factory import PipelineFactory

        mock_pipeline = MagicMock()
        mock_create.return_value = mock_pipeline

        factory = PipelineFactory(config_path=config_file)
        result = factory.create_pipeline("test_api")

        mock_create.assert_called_once()
        assert result == mock_pipeline

    def test_create_scraper_raises_not_implemented(self, config_file):
        """Should raise NotImplementedError for scraper type."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)

        with pytest.raises(NotImplementedError, match="Scraper pipeline"):
            factory.create_pipeline("test_scraper")


class TestCreateAllEnabledPipelines:
    """Tests for create_all_enabled_pipelines method."""

    @patch("src.ingestion.factory.PipelineFactory._create_api_pipeline")
    def test_creates_all_enabled(self, mock_create, config_file):
        """Should create pipelines for all enabled sources."""
        from src.ingestion.factory import PipelineFactory

        mock_pipeline = MagicMock()
        mock_create.return_value = mock_pipeline

        factory = PipelineFactory(config_path=config_file)
        # Only API pipelines can be created
        factory.config["sources"]["test_scraper"]["enabled"] = False

        pipelines = factory.create_all_enabled_pipelines()

        # Should have created pipelines for test_api and test_legacy
        assert len(pipelines) >= 2
        assert "test_disabled" not in pipelines

    @patch("src.ingestion.factory.PipelineFactory._create_api_pipeline")
    def test_continues_on_error(self, mock_create, config_file):
        """Should continue creating other pipelines on error."""
        from src.ingestion.factory import PipelineFactory

        # First call succeeds, second raises
        mock_create.side_effect = [MagicMock(), Exception("Creation failed")]

        factory = PipelineFactory(config_path=config_file)
        factory.config["sources"]["test_scraper"]["enabled"] = False

        pipelines = factory.create_all_enabled_pipelines()

        # Should have at least one pipeline despite error
        assert len(pipelines) >= 1

    def test_returns_dict(self, config_file):
        """Should return a dictionary."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)
        # Disable all sources to avoid actual creation
        for source in factory.config["sources"]:
            factory.config["sources"][source]["enabled"] = False

        pipelines = factory.create_all_enabled_pipelines()

        assert isinstance(pipelines, dict)


class TestReloadConfig:
    """Tests for reload_config method."""

    def test_reload_clears_cache(self, config_file):
        """Should clear cached config."""
        from src.ingestion.factory import PipelineFactory

        factory = PipelineFactory(config_path=config_file)

        # Load config first
        _ = factory.config
        assert factory._config is not None

        # Reload clears cache
        factory.reload_config()
        assert factory._config is None


class TestGetFactory:
    """Tests for get_factory module function."""

    def test_get_factory_creates_instance(self):
        """Should create factory instance."""
        from src.ingestion.factory import get_factory
        import src.ingestion.factory as factory_module

        # Reset module state
        factory_module._factory = None

        factory = get_factory()

        assert factory is not None

    def test_get_factory_returns_singleton(self):
        """Should return same instance on multiple calls."""
        from src.ingestion.factory import get_factory
        import src.ingestion.factory as factory_module

        # Reset module state
        factory_module._factory = None

        factory1 = get_factory()
        factory2 = get_factory()

        assert factory1 is factory2

    def test_get_factory_with_path_creates_new(self, config_file):
        """Should create new factory when path provided."""
        from src.ingestion.factory import get_factory
        import src.ingestion.factory as factory_module

        # Reset module state
        factory_module._factory = None

        get_factory()
        factory2 = get_factory(config_path=config_file)

        # New factory created with custom path
        assert factory2.config_path == Path(config_file)


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch("src.ingestion.factory.get_factory")
    def test_create_pipeline_uses_factory(self, mock_get_factory):
        """create_pipeline should use factory."""
        from src.ingestion.factory import create_pipeline

        mock_factory = MagicMock()
        mock_get_factory.return_value = mock_factory

        create_pipeline("test_source")

        mock_factory.create_pipeline.assert_called_with("test_source")

    @patch("src.ingestion.factory.get_factory")
    def test_create_all_pipelines_uses_factory(self, mock_get_factory):
        """create_all_pipelines should use factory."""
        from src.ingestion.factory import create_all_pipelines

        mock_factory = MagicMock()
        mock_get_factory.return_value = mock_factory

        create_all_pipelines()

        mock_factory.create_all_enabled_pipelines.assert_called_once()
