"""
Unit tests for the event_schema module.

Tests for all schema components against the current EventSchema definition:
- Subcategory helper class
- Coordinates validation
- PriceInfo / TicketInfo / OrganizerInfo / SourceInfo
- TaxonomyDimension validation
- MediaAsset / EngagementMetrics
- EventFormat / EventType enums
- EventSchema validation
- EventBatch creation
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from src.schemas.event import (
    Coordinates,
    EngagementMetrics,
    EventBatch,
    EventFormat,
    EventType,
    LocationInfo,
    MediaAsset,
    OrganizerInfo,
    PriceInfo,
    SourceInfo,
    Subcategory,
    TaxonomyDimension,
    TicketInfo,
)


class TestSubcategory:
    """Tests for Subcategory helper class."""

    def test_all_ids_returns_set(self):
        """all_ids should return a non-empty set."""
        ids = Subcategory.all_ids()
        assert isinstance(ids, set)
        assert len(ids) > 0

    def test_all_options_returns_list(self):
        """all_options should return a non-empty list of dicts."""
        options = Subcategory.all_options()
        assert isinstance(options, list)
        assert len(options) > 0
        for opt in options[:5]:
            assert "id" in opt
            assert "name" in opt

    def test_ids_for_primary_returns_set(self):
        """ids_for_primary should return a set for a known primary key."""
        ids = Subcategory.ids_for_primary("play_pure_fun")
        assert isinstance(ids, set)

    def test_get_by_id_valid(self):
        """get_by_id should return subcategory dict for a valid ID."""
        all_ids = Subcategory.all_ids()
        valid_id = next(iter(all_ids))
        result = Subcategory.get_by_id(valid_id)
        assert result is not None
        assert "id" in result

    def test_get_by_id_invalid(self):
        """get_by_id should return None for an unknown ID."""
        assert Subcategory.get_by_id("99.99") is None

    def test_validate_for_primary_valid(self):
        """Subcategory 1.x should belong to primary 1."""
        all_ids = Subcategory.all_ids()
        for sub_id in all_ids:
            if sub_id.startswith("1."):
                assert Subcategory.validate_for_primary(sub_id, "1") is True
                break

    def test_validate_for_primary_invalid(self):
        """Subcategory 2.x should not belong to primary 1."""
        all_ids = Subcategory.all_ids()
        for sub_id in all_ids:
            if sub_id.startswith("2."):
                assert Subcategory.validate_for_primary(sub_id, "1") is False
                break


class TestEventFormat:
    """Tests for EventFormat enum."""

    def test_enum_values(self):
        """All format values should exist."""
        assert EventFormat.IN_PERSON.value == "in_person"
        assert EventFormat.VIRTUAL.value == "virtual"
        assert EventFormat.HYBRID.value == "hybrid"
        assert EventFormat.STREAMED.value == "streamed"


class TestEventType:
    """Tests for EventType enum."""

    def test_enum_has_15_values(self):
        """Should have 15 event types."""
        assert len(EventType) == 15

    def test_concert_exists(self):
        """Concert type should exist."""
        assert EventType.CONCERT.value == "concert"

    def test_other_exists(self):
        """Other type should exist as fallback."""
        assert EventType.OTHER.value == "other"


class TestCoordinates:
    """Tests for Coordinates validation."""

    def test_valid_coordinates(self):
        """Valid lat/lon with sufficient precision should be accepted."""
        coords = Coordinates(latitude=40.7128, longitude=-74.0059)
        assert coords.latitude == 40.7128
        assert coords.longitude == -74.0059

    def test_insufficient_precision_rejected(self):
        """Coordinates with < 4 decimal places should be rejected."""
        with pytest.raises(ValidationError, match="insufficient precision"):
            Coordinates(latitude=41.0, longitude=2.0)

    def test_latitude_out_of_range(self):
        """Latitude outside ±90 should raise ValidationError."""
        with pytest.raises(ValidationError):
            Coordinates(latitude=91.1234, longitude=2.1734)
        with pytest.raises(ValidationError):
            Coordinates(latitude=-91.1234, longitude=2.1734)

    def test_longitude_out_of_range(self):
        """Longitude outside ±180 should raise ValidationError."""
        with pytest.raises(ValidationError):
            Coordinates(latitude=41.3851, longitude=181.1234)
        with pytest.raises(ValidationError):
            Coordinates(latitude=41.3851, longitude=-181.1234)


class TestLocationInfo:
    """Tests for LocationInfo model."""

    def test_minimal_location(self):
        """Minimal valid location with just city."""
        loc = LocationInfo(city="Barcelona")
        assert loc.city == "Barcelona"
        assert loc.country_code == "US"  # default
        assert loc.venue_name is None

    def test_full_location(self):
        """Full location with all fields."""
        loc = LocationInfo(
            venue_name="Club XYZ",
            street_address="123 Main St",
            city="Barcelona",
            state_or_region="Catalonia",
            postal_code="08001",
            country_code="ES",
            coordinates=Coordinates(latitude=41.3851, longitude=2.1734),
            timezone="Europe/Madrid",
        )
        assert loc.venue_name == "Club XYZ"
        assert loc.timezone == "Europe/Madrid"


class TestPriceInfo:
    """Tests for PriceInfo validation."""

    def test_default_values(self):
        """Default PriceInfo values."""
        price = PriceInfo()
        assert price.currency == "USD"
        assert price.is_free is False
        assert price.minimum_price is None

    def test_coerce_float_to_decimal(self):
        """Float prices should be coerced to Decimal."""
        price = PriceInfo(minimum_price=15.50)
        assert isinstance(price.minimum_price, Decimal)
        assert price.minimum_price == Decimal("15.5")

    def test_coerce_int_to_decimal(self):
        """Int prices should be coerced to Decimal."""
        price = PriceInfo(minimum_price=20)
        assert isinstance(price.minimum_price, Decimal)
        assert price.minimum_price == Decimal("20")

    def test_price_range_valid(self):
        """Valid price range where min <= max."""
        price = PriceInfo(minimum_price=10, maximum_price=50)
        assert price.minimum_price == Decimal("10")
        assert price.maximum_price == Decimal("50")

    def test_price_range_invalid(self):
        """max < min should raise ValidationError."""
        with pytest.raises(ValidationError, match="maximum_price cannot be less than minimum_price"):
            PriceInfo(minimum_price=50, maximum_price=10)

    def test_negative_price_rejected(self):
        """Negative prices should be rejected."""
        with pytest.raises(ValidationError):
            PriceInfo(minimum_price=-10)

    def test_is_free_flag(self):
        """is_free flag should be stored."""
        price = PriceInfo(is_free=True)
        assert price.is_free is True


class TestTicketInfo:
    """Tests for TicketInfo model."""

    def test_default_values(self):
        """All TicketInfo fields are optional."""
        ticket = TicketInfo()
        assert ticket.url is None
        assert ticket.is_sold_out is False

    def test_sold_out_flag(self):
        """is_sold_out flag should be stored."""
        ticket = TicketInfo(url="https://tickets.example.com", is_sold_out=True, ticket_count_available=0)
        assert ticket.is_sold_out is True


class TestOrganizerInfo:
    """Tests for OrganizerInfo model."""

    def test_minimal_organizer(self):
        """Minimal organizer with just a name."""
        org = OrganizerInfo(name="Test Organizer")
        assert org.name == "Test Organizer"
        assert org.verified is False

    def test_full_organizer(self):
        """Full organizer info."""
        org = OrganizerInfo(
            name="Big Events Inc",
            url="https://bigevents.com",
            email="info@bigevents.com",
            verified=True,
            follower_count=10000,
        )
        assert org.verified is True
        assert org.follower_count == 10000


class TestSourceInfo:
    """Tests for SourceInfo model."""

    def test_minimal_source(self):
        """Minimal required SourceInfo fields."""
        source = SourceInfo(
            source_name="test_source",
            source_event_id="12345",
            source_url="https://source.com/event/12345",
        )
        assert source.source_name == "test_source"
        assert source.ingestion_timestamp is not None

    def test_with_optional_fields(self):
        """SourceInfo with all optional fields."""
        ts = datetime.now(UTC)
        source = SourceInfo(
            source_name="meetup",
            source_event_id="abc",
            source_url="https://meetup.com/events/abc",
            source_updated_at=ts,
        )
        assert source.source_updated_at == ts


class TestMediaAsset:
    """Tests for MediaAsset model."""

    def test_minimal_asset(self):
        """Minimal media asset."""
        asset = MediaAsset(type="image", url="https://example.com/image.jpg")
        assert asset.type == "image"
        assert asset.url == "https://example.com/image.jpg"
        assert asset.title is None

    def test_full_asset(self):
        """Media asset with all fields."""
        asset = MediaAsset(
            type="video", url="https://example.com/clip.mp4", title="Event Recap", width=1920, height=1080
        )
        assert asset.width == 1920
        assert asset.height == 1080


class TestEngagementMetrics:
    """Tests for EngagementMetrics model."""

    def test_default_values(self):
        """All fields should be optional."""
        metrics = EngagementMetrics()
        assert metrics.going_count is None
        assert metrics.interested_count is None

    def test_with_values(self):
        """Set engagement values."""
        metrics = EngagementMetrics(going_count=100, interested_count=500, views_count=1000)
        assert metrics.going_count == 100
        assert metrics.views_count == 1000


class TestTaxonomyDimension:
    """Tests for TaxonomyDimension validation."""

    def test_minimal_dimension(self):
        """Minimal valid dimension uses a string primary_category."""
        dim = TaxonomyDimension(primary_category="play_pure_fun")
        assert dim.primary_category == "play_pure_fun"
        assert dim.confidence == 1.0

    def test_dimension_with_valid_subcategory(self):
        """Dimension with a valid subcategory from the taxonomy."""
        all_ids = Subcategory.all_ids()
        valid_sub = next((s for s in all_ids if s.startswith("1.")), None)
        if valid_sub:
            dim = TaxonomyDimension(primary_category="play_pure_fun", subcategory=valid_sub)
            assert dim.subcategory == valid_sub

    def test_invalid_subcategory_rejected(self):
        """Unknown subcategory ID should raise ValidationError."""
        with pytest.raises(ValidationError, match="not a valid taxonomy id"):
            TaxonomyDimension(primary_category="play_pure_fun", subcategory="99.99")

    def test_subcategory_primary_mismatch_rejected(self):
        """Subcategory from a different primary category should raise."""
        all_ids = Subcategory.all_ids()
        cat2_sub = next((s for s in all_ids if s.startswith("2.")), None)
        if cat2_sub:
            with pytest.raises(ValidationError, match="does not belong to"):
                TaxonomyDimension(primary_category="play_pure_fun", subcategory=cat2_sub)

    def test_empty_subcategory_coerced_to_none(self):
        """Empty string subcategory should be treated as None."""
        dim = TaxonomyDimension(primary_category="play_pure_fun", subcategory="")
        assert dim.subcategory is None

    def test_confidence_bounds(self):
        """Confidence must be 0.0–1.0."""
        dim = TaxonomyDimension(primary_category="play_pure_fun", confidence=0.95)
        assert dim.confidence == 0.95

        with pytest.raises(ValidationError):
            TaxonomyDimension(primary_category="play_pure_fun", confidence=1.5)

        with pytest.raises(ValidationError):
            TaxonomyDimension(primary_category="play_pure_fun", confidence=-0.1)

    def test_numeric_id_normalized(self):
        """Numeric primary_category ID ('1') is normalized to its slug."""
        dim = TaxonomyDimension(primary_category="1")
        assert dim.primary_category != "1"  # resolved to slug form


class TestEventSchema:
    """Tests for EventSchema using the conftest create_event fixture."""

    def test_minimal_valid_event(self, create_event):
        """Minimal event should have required fields with defaults."""
        event = create_event()
        assert event.title == "Test Event"
        assert event.data_quality_score == 0.0
        assert event.is_all_day is False
        assert event.is_recurring is False
        assert event.tags == []
        assert event.custom_fields == {}
        assert event.normalization_errors == []
        assert event.taxonomy_dimension is None

    def test_event_with_taxonomy_dimension(self, create_event):
        """Event with a TaxonomyDimension should store it."""
        dim = TaxonomyDimension(primary_category="play_pure_fun", confidence=0.9)
        event = create_event(taxonomy_dimension=dim)
        assert event.taxonomy_dimension is not None
        assert event.taxonomy_dimension.confidence == 0.9

    def test_quality_score_bounds(self, create_event):
        """data_quality_score must be 0.0–1.0."""
        event = create_event(data_quality_score=0.85)
        assert event.data_quality_score == 0.85

        with pytest.raises(ValidationError):
            create_event(data_quality_score=1.5)

        with pytest.raises(ValidationError):
            create_event(data_quality_score=-0.1)

    def test_custom_fields_stored(self, create_event):
        """Extra metadata in custom_fields should be preserved."""
        event = create_event(custom_fields={"source_ref": "abc123"})
        assert event.custom_fields["source_ref"] == "abc123"

    def test_event_with_price(self, create_event):
        """PriceInfo nested model should be stored correctly."""
        price = PriceInfo(minimum_price=25, maximum_price=50, currency="EUR")
        event = create_event(price=price)
        assert event.price.currency == "EUR"
        assert event.price.minimum_price == Decimal("25")

    def test_event_with_coordinates(self, create_event):
        """Location with coordinates should be accessible."""
        location = LocationInfo(
            city="Barcelona",
            venue_name="Club XYZ",
            coordinates=Coordinates(latitude=41.3851, longitude=2.1734),
        )
        event = create_event(location=location)
        assert event.location.coordinates.latitude == 41.3851

    def test_event_format_default(self, create_event):
        """Default format should be IN_PERSON."""
        event = create_event()
        assert event.format == EventFormat.IN_PERSON.value


class TestEventBatch:
    """Tests for EventBatch model."""

    def test_batch_creation(self, create_event):
        """Basic batch creation with events."""
        events = [create_event(title=f"Event {i}") for i in range(3)]
        batch = EventBatch(source_name="test_source", batch_id="batch-001", events=events, total_count=3)
        assert batch.source_name == "test_source"
        assert len(batch.events) == 3
        assert batch.total_count == 3

    def test_batch_counts(self, create_event):
        """Batch with success/failure counts."""
        events = [create_event()]
        batch = EventBatch(
            source_name="test_source",
            batch_id="batch-002",
            events=events,
            total_count=5,
            successful_count=3,
            failed_count=2,
            errors=[{"event_id": "123", "error": "Validation failed"}],
        )
        assert batch.successful_count == 3
        assert batch.failed_count == 2
        assert len(batch.errors) == 1

    def test_batch_ingestion_timestamp(self, create_event):
        """Batch should auto-set ingestion_timestamp."""
        events = [create_event()]
        batch = EventBatch(source_name="test", batch_id="batch-003", events=events, total_count=1)
        assert batch.ingestion_timestamp is not None
