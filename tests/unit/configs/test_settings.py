from src.configs.settings import Settings


def test_settings_parsing():
    """Test basic DATABASE_URL parsing."""
    settings = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db")
    params = settings.get_psycopg2_params()
    assert params["host"] == "localhost"
    assert params["port"] == 5432
    assert params["dbname"] == "db"
    assert params["user"] == "user"
    assert params["password"] == "pass"


def test_settings_encoded_password():
    """Test DATABASE_URL parsing with encoded special characters in password."""
    # p@ss!word encoded
    settings = Settings(DATABASE_URL="postgresql://user:p%40ss%21word@localhost:5432/db")
    params = settings.get_psycopg2_params()
    assert params["password"] == "p@ss!word"
    assert params["host"] == "localhost"


def test_settings_default_values():
    """Test default values for settings."""
    settings = Settings(DATABASE_URL="postgresql://localhost/db")
    assert settings.ENV == "development"
    assert settings.DEBUG is True


def test_paths():
    """Test that paths are correctly resolved."""
    settings = Settings(DATABASE_URL="postgresql://localhost/db")
    assert settings.BASE_DIR.name == "api"
    assert settings.TAXONOMY_DATA_PATH.name == "human_experience_taxonomy_master.json"
    assert settings.INGESTION_CONFIG_PATH.name == "ingestion.yaml"
