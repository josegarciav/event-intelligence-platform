"""
Unit tests for the base_adapter module.

Tests for BaseSourceAdapter, SourceType, FetchResult, and AdapterConfig.
"""

from datetime import datetime, timedelta

import pytest

from src.ingestion.adapters.base_adapter import (
    BaseSourceAdapter,
    SourceType,
    FetchResult,
    AdapterConfig,
)


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestSourceType:
    """Tests for SourceType enum."""

    def test_enum_values(self):
        """Should have API and SCRAPER values."""
        assert SourceType.API == "api"
        assert SourceType.SCRAPER == "scraper"

    def test_all_types_count(self):
        """Should have 2 source types."""
        assert len(SourceType) == 2


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_create_success_result(self):
        """Should create successful fetch result."""
        result = FetchResult(
            success=True,
            source_type=SourceType.API,
            raw_data=[{"id": 1}, {"id": 2}],
            total_fetched=2,
        )
        assert result.success is True
        assert result.source_type == SourceType.API
        assert len(result.raw_data) == 2
        assert result.total_fetched == 2

    def test_create_failed_result(self):
        """Should create failed fetch result."""
        result = FetchResult(
            success=False,
            source_type=SourceType.SCRAPER,
            raw_data=[],
            total_fetched=0,
            errors=["Connection timeout"],
        )
        assert result.success is False
        assert result.errors == ["Connection timeout"]

    def test_default_values(self):
        """Should have sensible defaults."""
        result = FetchResult(
            success=True,
            source_type=SourceType.API,
        )
        assert result.raw_data == []
        assert result.total_fetched == 0
        assert result.errors == []
        assert result.metadata == {}
        assert result.fetch_started_at is None
        assert result.fetch_ended_at is None

    def test_duration_seconds(self):
        """Should calculate duration correctly."""
        start = datetime.utcnow()
        end = start + timedelta(seconds=5)

        result = FetchResult(
            success=True,
            source_type=SourceType.API,
            fetch_started_at=start,
            fetch_ended_at=end,
        )

        assert result.duration_seconds == 5.0

    def test_duration_seconds_no_timestamps(self):
        """Should return 0 when timestamps not set."""
        result = FetchResult(
            success=True,
            source_type=SourceType.API,
        )
        assert result.duration_seconds == 0.0

    def test_metadata_storage(self):
        """Should store metadata."""
        result = FetchResult(
            success=True,
            source_type=SourceType.API,
            metadata={"pages_fetched": 5, "api_calls": 5},
        )
        assert result.metadata["pages_fetched"] == 5
        assert result.metadata["api_calls"] == 5


class TestAdapterConfig:
    """Tests for AdapterConfig dataclass."""

    def test_create_config(self):
        """Should create config with required fields."""
        config = AdapterConfig(
            source_id="test_source",
            source_type=SourceType.API,
        )
        assert config.source_id == "test_source"
        assert config.source_type == SourceType.API

    def test_default_values(self):
        """Should have sensible defaults."""
        config = AdapterConfig(
            source_id="test",
            source_type=SourceType.API,
        )
        assert config.request_timeout == 30
        assert config.max_retries == 3
        assert config.rate_limit_per_second == 1.0
        assert config.custom_config == {}

    def test_custom_values(self):
        """Should accept custom values."""
        config = AdapterConfig(
            source_id="custom",
            source_type=SourceType.SCRAPER,
            request_timeout=60,
            max_retries=5,
            rate_limit_per_second=0.5,
            custom_config={"key": "value"},
        )
        assert config.request_timeout == 60
        assert config.max_retries == 5
        assert config.rate_limit_per_second == 0.5
        assert config.custom_config == {"key": "value"}


class TestBaseSourceAdapter:
    """Tests for BaseSourceAdapter abstract class."""

    def test_cannot_instantiate_abstract(self):
        """Should not be able to instantiate abstract class."""
        config = AdapterConfig(
            source_id="test",
            source_type=SourceType.API,
        )
        with pytest.raises(TypeError):
            BaseSourceAdapter(config)

    def test_concrete_implementation(self):
        """Should be able to create concrete implementation."""

        class ConcreteAdapter(BaseSourceAdapter):
            def fetch(self, **kwargs):
                return FetchResult(
                    success=True,
                    source_type=self.source_type,
                    raw_data=[],
                )

            def _validate_config(self):
                pass

        config = AdapterConfig(
            source_id="test",
            source_type=SourceType.API,
        )
        adapter = ConcreteAdapter(config)

        assert adapter.source_id == "test"
        assert adapter.source_type == SourceType.API

    def test_context_manager(self):
        """Should work as context manager."""

        class ConcreteAdapter(BaseSourceAdapter):
            closed = False

            def fetch(self, **kwargs):
                return FetchResult(success=True, source_type=self.source_type)

            def _validate_config(self):
                pass

            def close(self):
                self.closed = True

        config = AdapterConfig(
            source_id="test",
            source_type=SourceType.API,
        )

        with ConcreteAdapter(config) as adapter:
            assert adapter.closed is False

        assert adapter.closed is True

    def test_close_default_implementation(self):
        """Should have default close that does nothing."""

        class ConcreteAdapter(BaseSourceAdapter):
            def fetch(self, **kwargs):
                return FetchResult(success=True, source_type=self.source_type)

            def _validate_config(self):
                pass

        config = AdapterConfig(
            source_id="test",
            source_type=SourceType.API,
        )
        adapter = ConcreteAdapter(config)

        # Should not raise
        adapter.close()
