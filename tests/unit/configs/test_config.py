"""
Unit tests for the config module.

Tests for Config class path resolution and config loading.
"""

from pathlib import Path

from src.configs.config import Config


class TestConfigPaths:
    """Tests for Config path attributes."""

    def test_config_dir_is_path(self):
        """CONFIG_DIR should be a Path object."""
        assert isinstance(Config.CONFIG_DIR, Path)

    def test_config_dir_exists(self):
        """CONFIG_DIR should exist."""
        assert Config.CONFIG_DIR.exists()

    def test_project_root_is_path(self):
        """PROJECT_ROOT should be a Path object."""
        assert isinstance(Config.PROJECT_ROOT, Path)

    def test_project_root_exists(self):
        """PROJECT_ROOT should exist."""
        assert Config.PROJECT_ROOT.exists()

    def test_ingestion_config_path_is_path(self):
        """INGESTION_CONFIG_PATH should be a Path object."""
        assert isinstance(Config.INGESTION_CONFIG_PATH, Path)

    def test_taxonomy_path_is_path(self):
        """TAXONOMY_DATA_PATH should be a Path object."""
        assert isinstance(Config.TAXONOMY_DATA_PATH, Path)


class TestGetTaxonomyPath:
    """Tests for get_taxonomy_path method."""

    def test_returns_path(self):
        """Should return a Path object."""
        path = Config.get_taxonomy_path()
        assert isinstance(path, Path)

    def test_path_is_absolute(self):
        """Returned path should be absolute."""
        path = Config.get_taxonomy_path()
        assert path.is_absolute()

    def test_path_exists(self):
        """Taxonomy file should exist."""
        path = Config.get_taxonomy_path()
        assert path.exists()

    def test_path_is_json(self):
        """Taxonomy file should be a JSON file."""
        path = Config.get_taxonomy_path()
        assert path.suffix == ".json"


class TestLoadIngestionConfig:
    """Tests for load_ingestion_config method."""

    def test_returns_dict(self):
        """Should return a dictionary."""
        config = Config.load_ingestion_config()
        assert isinstance(config, dict)

    def test_config_has_sources(self):
        """Config should have sources section."""
        config = Config.load_ingestion_config()
        assert "sources" in config

    def test_config_cached(self):
        """Config should be cached (lru_cache)."""
        # Call twice and verify same object
        config1 = Config.load_ingestion_config()
        config2 = Config.load_ingestion_config()
        # LRU cache means same object is returned
        assert config1 is config2

    def test_env_substitution(self, monkeypatch):
        """Test environment variable substitution in config."""
        from src.configs.settings import Settings

        # We need to make sure Config uses a Settings object that has our test value
        test_db_url = "postgresql://test_user:test_pass@test_host:5432/test_db"

        # Mock Settings in config.py
        import src.configs.config

        monkeypatch.setattr(src.configs.config, "settings", Settings(DATABASE_URL=test_db_url))

        # Clear cache to ensure re-load
        Config.load_ingestion_config.cache_clear()

        config = Config.load_ingestion_config()

        # Check if DATABASE_URL was substituted
        assert config["global"]["storage"]["url"] == test_db_url

    def test_secret_substitution(self, monkeypatch):
        """Test that SecretStr values are correctly substituted."""
        from src.configs.settings import Settings

        test_key = "test-api-key"

        # Mock Settings in config.py
        import src.configs.config

        monkeypatch.setattr(
            src.configs.config,
            "settings",
            Settings(
                DATABASE_URL="postgresql://localhost/db",
                TICKETMASTER_API_KEY=test_key,
            ),
        )

        # Clear cache to ensure re-load
        Config.load_ingestion_config.cache_clear()

        config = Config.load_ingestion_config()

        # Check if TICKETMASTER_API_KEY was substituted
        assert config["sources"]["ticketmaster"]["query"]["params"]["apikey"] == test_key
