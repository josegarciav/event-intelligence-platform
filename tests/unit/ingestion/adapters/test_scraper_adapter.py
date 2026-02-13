"""
Unit tests for the scraper_adapter module.

Tests for ScraperAdapterConfig and ScraperAdapter classes.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.adapters.scraper_adapter import (
    HtmlEnrichmentConfig,
    HtmlEnrichmentScraper,
    ScraperAdapter,
    ScraperAdapterConfig,
)
from src.ingestion.adapters.base_adapter import SourceType

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def scraper_config():
    """Create a basic scraper adapter config."""
    return ScraperAdapterConfig(
        source_id="test_scraper",
        source_type=SourceType.SCRAPER,
        base_url="https://example.com/events",
        url_pattern=r"/events/\d+",
        url_identifier="/events/",
    )


@pytest.fixture
def mock_scraper():
    """Create a mock EventScraper."""
    scraper = MagicMock()
    return scraper


@pytest.fixture
def mock_fetch_result():
    """Create mock page fetch results."""
    result = MagicMock()
    result.ok = True
    result.html = "<html><body>Event content</body></html>"
    result.url = "https://example.com/events/1"
    result.final_url = "https://example.com/events/1"
    result.error = None
    return result


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestScraperAdapterConfig:
    """Tests for ScraperAdapterConfig dataclass."""

    def test_create_config(self):
        """Should create config with required fields."""
        config = ScraperAdapterConfig(
            source_id="test",
            source_type=SourceType.SCRAPER,
            base_url="https://example.com",
        )
        assert config.source_id == "test"
        assert config.base_url == "https://example.com"

    def test_default_values(self):
        """Should have sensible defaults."""
        config = ScraperAdapterConfig(
            source_id="test",
            source_type=SourceType.SCRAPER,
            base_url="https://example.com",
        )
        assert config.url_pattern == ""
        assert config.url_identifier == ""
        assert config.max_pages == 5
        assert config.timeout_s == 30.0
        assert config.min_delay_s == 2.0
        assert config.headless is True
        assert config.city == "barcelona"
        assert config.country_code == "es"

    def test_source_type_set(self):
        """Should have source_type set to SCRAPER."""
        config = ScraperAdapterConfig(
            source_id="test",
            source_type=SourceType.SCRAPER,
            base_url="https://example.com",
        )
        assert config.source_type == SourceType.SCRAPER

    def test_custom_values(self):
        """Should accept custom values."""
        config = ScraperAdapterConfig(
            source_id="test",
            source_type=SourceType.SCRAPER,
            base_url="https://example.com",
            url_pattern=r"/event/\w+",
            url_identifier="/event/",
            max_pages=10,
            timeout_s=60.0,
            min_delay_s=5.0,
            headless=False,
            city="madrid",
            country_code="es",
        )
        assert config.url_pattern == r"/event/\w+"
        assert config.url_identifier == "/event/"
        assert config.max_pages == 10
        assert config.timeout_s == 60.0
        assert config.min_delay_s == 5.0
        assert config.headless is False
        assert config.city == "madrid"


class TestScraperAdapterInit:
    """Tests for ScraperAdapter initialization."""

    def test_init_with_config(self, scraper_config):
        """Should initialize with config."""
        adapter = ScraperAdapter(scraper_config)
        assert adapter.scraper_config.base_url == "https://example.com/events"
        assert adapter._scraper is None

    def test_init_with_html_parser(self, scraper_config):
        """Should accept custom HTML parser."""
        parser = MagicMock()
        adapter = ScraperAdapter(scraper_config, html_parser=parser)
        assert adapter.html_parser is parser

    def test_validate_config_requires_base_url(self):
        """Should raise ValueError if no base_url provided."""
        config = ScraperAdapterConfig(source_id="test", source_type=SourceType.SCRAPER)
        with pytest.raises(ValueError, match="requires base_url"):
            ScraperAdapter(config)

    def test_scraper_config_property(self, scraper_config):
        """Should return typed config via property."""
        adapter = ScraperAdapter(scraper_config)
        assert adapter.scraper_config is adapter.config


class TestScraperAdapterGetScraper:
    """Tests for ScraperAdapter._get_scraper method."""

    def test_creates_scraper_on_first_call(self, scraper_config):
        """Should create scraper on first call."""
        adapter = ScraperAdapter(scraper_config)

        # Mock the scraper inside _get_scraper
        with patch(
            "src.ingestion.pipelines.scrapers.base_scraper.EventScraper"
        ) as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            result = adapter._get_scraper()

            assert result is not None

    def test_returns_same_scraper(self, scraper_config):
        """Should return the same scraper on subsequent calls."""
        adapter = ScraperAdapter(scraper_config)
        # Set the scraper directly to test caching
        mock_scraper = MagicMock()
        adapter._scraper = mock_scraper

        scraper1 = adapter._get_scraper()
        scraper2 = adapter._get_scraper()

        assert scraper1 is scraper2
        assert scraper1 is mock_scraper


class TestScraperAdapterFetch:
    """Tests for ScraperAdapter.fetch method."""

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_success(self, mock_get_scraper, scraper_config, mock_fetch_result):
        """Should return successful FetchResult."""
        mock_scraper = MagicMock()
        mock_scraper.fetch_listing_pages.return_value = [mock_fetch_result]
        mock_scraper.extract_event_urls.return_value = ["https://example.com/events/1"]
        mock_scraper.fetch_event_pages.return_value = [mock_fetch_result]
        mock_get_scraper.return_value = mock_scraper

        adapter = ScraperAdapter(scraper_config)
        result = adapter.fetch()

        assert result.success is True
        assert result.source_type == SourceType.SCRAPER
        assert result.total_fetched >= 0

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_with_html_parser(
        self, mock_get_scraper, scraper_config, mock_fetch_result
    ):
        """Should use custom HTML parser."""
        mock_scraper = MagicMock()
        mock_scraper.fetch_listing_pages.return_value = [mock_fetch_result]
        mock_scraper.extract_event_urls.return_value = ["https://example.com/events/1"]
        mock_scraper.fetch_event_pages.return_value = [mock_fetch_result]
        mock_get_scraper.return_value = mock_scraper

        parser = MagicMock(return_value={"title": "Parsed Event"})
        adapter = ScraperAdapter(scraper_config, html_parser=parser)
        result = adapter.fetch()

        assert result.success is True
        parser.assert_called()

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_tracks_metadata(
        self, mock_get_scraper, scraper_config, mock_fetch_result
    ):
        """Should track metadata."""
        mock_scraper = MagicMock()
        mock_scraper.fetch_listing_pages.return_value = [
            mock_fetch_result,
            mock_fetch_result,
        ]
        mock_scraper.extract_event_urls.return_value = [
            "https://example.com/events/1",
            "https://example.com/events/2",
        ]
        mock_scraper.fetch_event_pages.return_value = [
            mock_fetch_result,
            mock_fetch_result,
        ]
        mock_get_scraper.return_value = mock_scraper

        adapter = ScraperAdapter(scraper_config)
        result = adapter.fetch()

        assert "pages_fetched" in result.metadata
        assert "events_fetched" in result.metadata

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_handles_exception(self, mock_get_scraper, scraper_config):
        """Should handle exceptions gracefully."""
        mock_get_scraper.side_effect = Exception("Scraper failed")

        adapter = ScraperAdapter(scraper_config)
        result = adapter.fetch()

        assert result.success is False
        assert "Scraper failed" in result.errors

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_with_kwargs(
        self, mock_get_scraper, scraper_config, mock_fetch_result
    ):
        """Should pass kwargs to scraper."""
        mock_scraper = MagicMock()
        mock_scraper.fetch_listing_pages.return_value = [mock_fetch_result]
        mock_scraper.extract_event_urls.return_value = []
        mock_get_scraper.return_value = mock_scraper

        adapter = ScraperAdapter(scraper_config)
        adapter.fetch(city="madrid", country_code="es", max_pages=3)

        mock_scraper.fetch_listing_pages.assert_called_with(
            city="madrid",
            country_code="es",
            max_pages=3,
        )

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_dedupes_urls(
        self, mock_get_scraper, scraper_config, mock_fetch_result
    ):
        """Should deduplicate event URLs."""
        mock_scraper = MagicMock()
        mock_scraper.fetch_listing_pages.return_value = [
            mock_fetch_result,
            mock_fetch_result,
        ]
        # Return duplicate URLs
        mock_scraper.extract_event_urls.return_value = [
            "https://example.com/events/1",
            "https://example.com/events/1",  # Duplicate
        ]
        mock_scraper.fetch_event_pages.return_value = [mock_fetch_result]
        mock_get_scraper.return_value = mock_scraper

        adapter = ScraperAdapter(scraper_config)
        adapter.fetch()

        # Should fetch only unique URLs
        mock_scraper.fetch_event_pages.assert_called_once()

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_tracks_parse_failures(
        self, mock_get_scraper, scraper_config, mock_fetch_result
    ):
        """Should track parse failures in metadata."""
        mock_scraper = MagicMock()
        mock_scraper.fetch_listing_pages.return_value = [mock_fetch_result]
        mock_scraper.extract_event_urls.return_value = ["https://example.com/events/1"]
        mock_scraper.fetch_event_pages.return_value = [mock_fetch_result]
        mock_get_scraper.return_value = mock_scraper

        # Parser that raises exception
        parser = MagicMock(side_effect=Exception("Parse error"))
        adapter = ScraperAdapter(scraper_config, html_parser=parser)
        result = adapter.fetch()

        assert result.metadata["parse_failures"] >= 1

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_handles_failed_pages(self, mock_get_scraper, scraper_config):
        """Should handle failed page fetches."""
        mock_scraper = MagicMock()

        # Listing page failed
        failed_result = MagicMock()
        failed_result.ok = False
        failed_result.html = None
        failed_result.url = "https://example.com/events"
        failed_result.error = "Connection timeout"

        mock_scraper.fetch_listing_pages.return_value = [failed_result]
        mock_get_scraper.return_value = mock_scraper

        adapter = ScraperAdapter(scraper_config)
        result = adapter.fetch()

        assert result.metadata["pages_fetched"] == 0

    @patch.object(ScraperAdapter, "_get_scraper")
    def test_fetch_timestamps(
        self, mock_get_scraper, scraper_config, mock_fetch_result
    ):
        """Should track fetch timestamps."""
        mock_scraper = MagicMock()
        mock_scraper.fetch_listing_pages.return_value = [mock_fetch_result]
        mock_scraper.extract_event_urls.return_value = []
        mock_get_scraper.return_value = mock_scraper

        adapter = ScraperAdapter(scraper_config)
        result = adapter.fetch()

        assert result.fetch_started_at is not None
        assert result.fetch_ended_at is not None
        assert result.fetch_started_at <= result.fetch_ended_at


class TestScraperAdapterClose:
    """Tests for ScraperAdapter.close method."""

    def test_close_scraper(self, scraper_config):
        """Should close the scraper."""
        adapter = ScraperAdapter(scraper_config)
        mock_scraper = MagicMock()
        adapter._scraper = mock_scraper

        adapter.close()

        mock_scraper.close.assert_called_once()
        assert adapter._scraper is None

    def test_close_without_scraper(self, scraper_config):
        """Should handle close when no scraper exists."""
        adapter = ScraperAdapter(scraper_config)

        # Should not raise
        adapter.close()
        assert adapter._scraper is None


class TestScraperAdapterContextManager:
    """Tests for ScraperAdapter context manager usage."""

    def test_context_manager(self, scraper_config):
        """Should work as context manager."""
        adapter = ScraperAdapter(scraper_config)

        with patch.object(adapter, "close") as mock_close:
            with adapter as ctx:
                assert ctx is adapter
            mock_close.assert_called_once()


class TestHtmlEnrichmentScraper:
    """Tests for HtmlEnrichmentScraper behavior."""

    def test_loads_render_hints_from_generated_config(self, tmp_path):
        """Should load wait_for/actions and engine hints from generated config."""
        cfg_dir = tmp_path / "sources"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "ra_co_scraper_auto.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "engine": {"type": "browser"},
                    "discovery": {"wait_for": ".event-content"},
                    "actions": [{"type": "wait_for", "selector": "main"}],
                }
            ),
            encoding="utf-8",
        )

        scraper = HtmlEnrichmentScraper(
            HtmlEnrichmentConfig(
                enabled=True,
                engine_type="http",
                source_name="ra_co",
                generated_config_dir=str(cfg_dir),
            )
        )

        assert scraper.config.engine_type == "browser"
        assert scraper._wait_for == ".event-content"
        assert scraper._actions == [{"type": "wait_for", "selector": "main"}]

    def test_fetch_uses_rendered_path_for_hybrid_engine(self):
        """Hybrid/browser enrichment should use rendered fetch with optional hints."""
        scraper = HtmlEnrichmentScraper(
            HtmlEnrichmentConfig(
                enabled=True,
                engine_type="hybrid",
                min_text_len=10,
                wait_for="main",
                actions=[{"type": "wait_for", "selector": "main"}],
            )
        )
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.status_code = 200
        mock_result.block_signals = []
        mock_result.text = "<html><body><main>" + ("content " * 50) + "</main></body></html>"
        mock_engine.get_rendered.return_value = mock_result
        scraper._get_engine = MagicMock(return_value=mock_engine)

        text = scraper.fetch_compressed_html("https://example.com/event/1")

        assert text is not None
        assert mock_engine.get_rendered.call_count >= 1
        assert mock_engine.get_rendered.call_args_list[-1].args[0] == (
            "https://example.com/event/1"
        )
