"""
Unit tests for the base_scraper module.

Tests for PageFetchResult, ScraperConfig, EventScraper, BaseScraperPipeline,
and config loading utilities.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import json
import time

import pytest

from src.ingestion.pipelines.scrapers.base_scraper import (
    PageFetchResult,
    ScraperConfig,
    EventScraper,
    BaseScraperPipeline,
    load_scraper_config,
    load_config_raw,
    get_config_path,
    list_available_configs,
)
from src.ingestion.base_pipeline import PipelineConfig


# =============================================================================
# TEST DATA
# =============================================================================


MOCK_SCRAPER_CONFIG_JSON = {
    "source_id": "test_source",
    "entrypoints": [
        {
            "url": "https://example.com/events/{country_code}/{city}",
            "params": {
                "city": "barcelona",
                "country_code": "es",
            },
            "paging": {
                "start": 0,
                "end": 5,
            },
        }
    ],
    "discovery": {
        "link_extract": {
            "pattern": r"/events/\d+",
            "identifier": "/events/",
        }
    },
    "engine": {
        "timeout_s": 30.0,
        "rate_limit_policy": {
            "min_delay_s": 2.0,
        },
    },
}


MOCK_HTML = """
<html>
<body>
    <a href="/events/123">Event 1</a>
    <a href="/events/456">Event 2</a>
    <a href="/events/789">Event 3</a>
</body>
</html>
"""


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def scraper_config():
    """Create a basic scraper config."""
    return ScraperConfig(
        source_id="test_scraper",
        base_url="https://example.com/events",
        url_pattern=r"/events/\d+",
        url_identifier="/events/",
    )


@pytest.fixture
def pipeline_config():
    """Create a pipeline config."""
    return PipelineConfig(
        source_name="test_scraper",
        batch_size=10,
    )


# =============================================================================
# TEST CLASSES - PageFetchResult
# =============================================================================


class TestPageFetchResult:
    """Tests for PageFetchResult dataclass."""

    def test_create_success_result(self):
        """Should create successful fetch result."""
        result = PageFetchResult(
            ok=True,
            url="https://example.com/events/1",
            final_url="https://example.com/events/1",
            status_code=200,
            html="<html></html>",
        )
        assert result.ok is True
        assert result.url == "https://example.com/events/1"
        assert result.status_code == 200
        assert result.html == "<html></html>"

    def test_create_failed_result(self):
        """Should create failed fetch result."""
        result = PageFetchResult(
            ok=False,
            url="https://example.com/events/1",
            final_url="https://example.com/events/1",
            status_code=404,
            html=None,
            error="Not found",
        )
        assert result.ok is False
        assert result.error == "Not found"

    def test_default_values(self):
        """Should have sensible defaults."""
        result = PageFetchResult(
            ok=True,
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            html="<html></html>",
        )
        assert result.error is None
        assert result.elapsed_s == 0.0


# =============================================================================
# TEST CLASSES - ScraperConfig
# =============================================================================


class TestScraperConfig:
    """Tests for ScraperConfig dataclass."""

    def test_create_config(self):
        """Should create config with required fields."""
        config = ScraperConfig(
            source_id="test",
            base_url="https://example.com",
            url_pattern=r"/event/\d+",
            url_identifier="/event/",
        )
        assert config.source_id == "test"
        assert config.base_url == "https://example.com"
        assert config.url_pattern == r"/event/\d+"

    def test_default_values(self):
        """Should have sensible defaults."""
        config = ScraperConfig(
            source_id="test",
            base_url="https://example.com",
            url_pattern="",
            url_identifier="",
        )
        assert config.max_pages == 5
        assert config.timeout_s == 30.0
        assert config.min_delay_s == 2.0
        assert config.headless is True
        assert config.city == "barcelona"
        assert config.country_code == "es"


# =============================================================================
# TEST CLASSES - Config Loaders
# =============================================================================


class TestGetConfigPath:
    """Tests for get_config_path function."""

    @patch("src.ingestion.pipelines.scrapers.base_scraper.SCRAPER_CONFIGS_DIR")
    def test_returns_path_for_existing_config(self, mock_dir):
        """Should return path for existing config."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_dir.__truediv__ = MagicMock(return_value=mock_path)

        result = get_config_path("test_source")

        assert result is not None

    @patch("src.ingestion.pipelines.scrapers.base_scraper.SCRAPER_CONFIGS_DIR")
    @patch("src.ingestion.pipelines.scrapers.base_scraper.list_available_configs")
    def test_raises_for_missing_config(self, mock_list, mock_dir):
        """Should raise FileNotFoundError for missing config."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_path)
        mock_list.return_value = ["other_source"]

        with pytest.raises(FileNotFoundError, match="Scraper config not found"):
            get_config_path("missing_source")


class TestListAvailableConfigs:
    """Tests for list_available_configs function."""

    @patch("src.ingestion.pipelines.scrapers.base_scraper.SCRAPER_CONFIGS_DIR")
    def test_returns_empty_when_dir_missing(self, mock_dir):
        """Should return empty list when dir doesn't exist."""
        mock_dir.exists.return_value = False

        result = list_available_configs()

        assert result == []

    @patch("src.ingestion.pipelines.scrapers.base_scraper.SCRAPER_CONFIGS_DIR")
    def test_returns_config_names(self, mock_dir):
        """Should return list of config names."""
        mock_file1 = MagicMock()
        mock_file1.stem = "source1"
        mock_file2 = MagicMock()
        mock_file2.stem = "source2"

        mock_dir.exists.return_value = True
        mock_dir.glob.return_value = [mock_file1, mock_file2]

        result = list_available_configs()

        assert "source1" in result
        assert "source2" in result


class TestLoadConfigRaw:
    """Tests for load_config_raw function."""

    @patch("src.ingestion.pipelines.scrapers.base_scraper.get_config_path")
    def test_loads_json_config(self, mock_get_path):
        """Should load and parse JSON config."""
        mock_get_path.return_value = Path("/fake/path.json")

        with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_SCRAPER_CONFIG_JSON))):
            result = load_config_raw("test_source")

        assert result["source_id"] == "test_source"


class TestLoadScraperConfig:
    """Tests for load_scraper_config function."""

    @patch("src.ingestion.pipelines.scrapers.base_scraper.load_config_raw")
    def test_creates_scraper_config(self, mock_load_raw):
        """Should create ScraperConfig from JSON."""
        mock_load_raw.return_value = MOCK_SCRAPER_CONFIG_JSON

        result = load_scraper_config("test_source")

        assert isinstance(result, ScraperConfig)
        assert result.source_id == "test_source"

    @patch("src.ingestion.pipelines.scrapers.base_scraper.load_config_raw")
    def test_uses_url_from_entrypoints(self, mock_load_raw):
        """Should extract base URL from entrypoints."""
        mock_load_raw.return_value = MOCK_SCRAPER_CONFIG_JSON

        result = load_scraper_config("test_source")

        assert "example.com" in result.base_url

    @patch("src.ingestion.pipelines.scrapers.base_scraper.load_config_raw")
    def test_override_city(self, mock_load_raw):
        """Should allow overriding city."""
        mock_load_raw.return_value = MOCK_SCRAPER_CONFIG_JSON

        result = load_scraper_config("test_source", city="madrid")

        assert result.city == "madrid"

    @patch("src.ingestion.pipelines.scrapers.base_scraper.load_config_raw")
    def test_override_max_pages(self, mock_load_raw):
        """Should allow overriding max_pages."""
        mock_load_raw.return_value = MOCK_SCRAPER_CONFIG_JSON

        result = load_scraper_config("test_source", max_pages=10)

        assert result.max_pages == 10


# =============================================================================
# TEST CLASSES - EventScraper
# =============================================================================


class TestEventScraperInit:
    """Tests for EventScraper initialization."""

    def test_init_with_config(self, scraper_config):
        """Should initialize with config."""
        scraper = EventScraper(scraper_config)

        assert scraper.config is scraper_config
        assert scraper._browser is None
        assert scraper._playwright is None


class TestEventScraperEnsureBrowser:
    """Tests for EventScraper._ensure_browser method."""

    def test_raises_import_error_without_playwright(self, scraper_config):
        """Should raise ImportError when playwright not installed."""
        scraper = EventScraper(scraper_config)

        with patch.dict("sys.modules", {"playwright.sync_api": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(ImportError, match="playwright is required"):
                    scraper._ensure_browser()


class TestEventScraperClose:
    """Tests for EventScraper.close method."""

    def test_close_browser(self, scraper_config):
        """Should close browser and playwright."""
        scraper = EventScraper(scraper_config)
        mock_browser = MagicMock()
        mock_playwright = MagicMock()
        scraper._browser = mock_browser
        scraper._playwright = mock_playwright

        scraper.close()

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert scraper._browser is None
        assert scraper._playwright is None

    def test_close_without_browser(self, scraper_config):
        """Should handle close when browser not initialized."""
        scraper = EventScraper(scraper_config)

        # Should not raise
        scraper.close()


class TestEventScraperExtractEventUrls:
    """Tests for EventScraper.extract_event_urls method."""

    def test_extracts_matching_urls(self, scraper_config):
        """Should extract URLs matching pattern."""
        scraper = EventScraper(scraper_config)

        urls = scraper.extract_event_urls(MOCK_HTML, "https://example.com")

        assert len(urls) == 3
        assert "https://ra.co/events/123" in urls
        assert "https://ra.co/events/456" in urls

    def test_deduplicates_urls(self, scraper_config):
        """Should deduplicate extracted URLs."""
        scraper = EventScraper(scraper_config)
        html = """
        <a href="/events/123">Event</a>
        <a href="/events/123">Event Duplicate</a>
        """

        urls = scraper.extract_event_urls(html, "https://example.com")

        assert len(urls) == 1

    def test_returns_empty_for_no_html(self, scraper_config):
        """Should return empty list for empty HTML."""
        scraper = EventScraper(scraper_config)

        urls = scraper.extract_event_urls("", "https://example.com")

        assert urls == []

    def test_filters_by_identifier(self, scraper_config):
        """Should filter by url_identifier."""
        scraper = EventScraper(scraper_config)
        html = """
        <a href="/events/123">Event</a>
        <a href="/other/456">Other Link</a>
        """

        urls = scraper.extract_event_urls(html, "https://example.com")

        assert len(urls) == 1
        assert "events" in urls[0]


class TestEventScraperContextManager:
    """Tests for EventScraper context manager."""

    def test_context_manager(self, scraper_config):
        """Should work as context manager."""
        scraper = EventScraper(scraper_config)

        with patch.object(scraper, "close") as mock_close:
            with scraper as ctx:
                assert ctx is scraper
            mock_close.assert_called_once()


# =============================================================================
# TEST CLASSES - BaseScraperPipeline
# =============================================================================


class TestBaseScraperPipelineInit:
    """Tests for BaseScraperPipeline initialization."""

    def test_cannot_instantiate_abstract(self, pipeline_config, scraper_config):
        """Should not be able to instantiate abstract class."""
        with pytest.raises(TypeError):
            BaseScraperPipeline(pipeline_config, scraper_config)

    def test_concrete_implementation(self, pipeline_config, scraper_config):
        """Should be able to create concrete implementation."""

        class ConcretePipeline(BaseScraperPipeline):
            def parse_event_html(self, html, url):
                return {"title": "Test", "url": url}

            def map_to_taxonomy(self, parsed_event):
                return "1", []

            def normalize_to_schema(self, parsed, primary_cat, dims):
                return MagicMock()

            def validate_event(self, event):
                return True, []

            def enrich_event(self, event):
                return event

        pipeline = ConcretePipeline(pipeline_config, scraper_config)

        assert pipeline.scraper_config is scraper_config

    def test_uses_custom_html_parser(self, pipeline_config, scraper_config):
        """Should use custom HTML parser when provided."""

        class ConcretePipeline(BaseScraperPipeline):
            def parse_event_html(self, html, url):
                return {"parsed": True}

            def map_to_taxonomy(self, parsed_event):
                return "1", []

            def normalize_to_schema(self, parsed, primary_cat, dims):
                return MagicMock()

            def validate_event(self, event):
                return True, []

            def enrich_event(self, event):
                return event

        custom_parser = MagicMock(return_value={"custom": True})
        pipeline = ConcretePipeline(pipeline_config, scraper_config, html_parser=custom_parser)

        # Access adapter's html_parser
        assert pipeline.adapter.html_parser is custom_parser


class TestBaseScraperPipelineParseRawEvent:
    """Tests for BaseScraperPipeline.parse_raw_event method."""

    def test_returns_event_as_is(self, pipeline_config, scraper_config):
        """Should return raw event unchanged (already parsed by adapter)."""

        class ConcretePipeline(BaseScraperPipeline):
            def parse_event_html(self, html, url):
                return {"parsed": True}

            def map_to_taxonomy(self, parsed_event):
                return "1", []

            def normalize_to_schema(self, parsed, primary_cat, dims):
                return MagicMock()

            def validate_event(self, event):
                return True, []

            def enrich_event(self, event):
                return event

        pipeline = ConcretePipeline(pipeline_config, scraper_config)
        raw_event = {"title": "Test Event", "_source_url": "https://example.com"}

        result = pipeline.parse_raw_event(raw_event)

        assert result == raw_event


class TestBaseScraperPipelineDefaultHtmlParser:
    """Tests for BaseScraperPipeline._default_html_parser method."""

    def test_delegates_to_parse_event_html(self, pipeline_config, scraper_config):
        """Should delegate to parse_event_html."""

        class ConcretePipeline(BaseScraperPipeline):
            def parse_event_html(self, html, url):
                return {"html_length": len(html), "url": url}

            def map_to_taxonomy(self, parsed_event):
                return "1", []

            def normalize_to_schema(self, parsed, primary_cat, dims):
                return MagicMock()

            def validate_event(self, event):
                return True, []

            def enrich_event(self, event):
                return event

        pipeline = ConcretePipeline(pipeline_config, scraper_config)

        result = pipeline._default_html_parser("<html></html>", "https://example.com")

        assert result["html_length"] == 13
        assert result["url"] == "https://example.com"
