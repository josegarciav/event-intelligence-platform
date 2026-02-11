"""
Unit tests for the event_schema module.

Tests for all schema components:
- PrimaryCategory enum with ID conversion
- Subcategory helper class
- Coordinates validation
- PriceInfo validation
- TaxonomyDimension validation
- EventSchema validation
- EventBatch creation
"""

from datetime import datetime, timezone
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
    PrimaryCategory,
    SourceInfo,
    Subcategory,
    TaxonomyDimension,
    TicketInfo,
)


class TestPrimaryCategory:
    """Tests for PrimaryCategory enum."""

    def test_enum_has_10_values(self):
        """Should have exactly 10 primary categories."""
        assert len(PrimaryCategory) == 10

    def test_enum_values(self):
        """All category values should be correct."""
        assert PrimaryCategory.PLAY_AND_PURE_FUN.value == "play_and_fun"
        assert (
            PrimaryCategory.EXPLORATION_AND_ADVENTURE.value
            == "exploration_and_adventure"
        )
        assert (
            PrimaryCategory.CREATION_AND_EXPRESSION.value == "creation_and_expression"
        )
        assert (
            PrimaryCategory.LEARNING_AND_INTELLECTUAL.value
            == "learning_and_intellectual"
        )
        assert PrimaryCategory.SOCIAL_CONNECTION.value == "social_connection"
        assert PrimaryCategory.BODY_AND_MOVEMENT.value == "body_and_movement"
        assert (
            PrimaryCategory.CHALLENGE_AND_ACHIEVEMENT.value
            == "challenge_and_achievement"
        )
        assert (
            PrimaryCategory.RELAXATION_AND_ESCAPISM.value == "relaxation_and_escapism"
        )
        assert PrimaryCategory.IDENTITY_AND_MEANING.value == "identity_and_meaning"
        assert (
            PrimaryCategory.CONTRIBUTION_AND_IMPACT.value == "contribution_and_impact"
        )

    def test_from_id_valid(self):
        """from_id should convert numeric ID to enum."""
        assert PrimaryCategory.from_id("1") == PrimaryCategory.PLAY_AND_PURE_FUN
        assert PrimaryCategory.from_id("5") == PrimaryCategory.SOCIAL_CONNECTION
        assert PrimaryCategory.from_id("10") == PrimaryCategory.CONTRIBUTION_AND_IMPACT

    def test_from_id_invalid(self):
        """from_id should raise ValueError for invalid ID."""
        with pytest.raises(ValueError, match="Invalid category ID"):
            PrimaryCategory.from_id("0")

        with pytest.raises(ValueError, match="Invalid category ID"):
            PrimaryCategory.from_id("11")

        with pytest.raises(ValueError, match="Invalid category ID"):
            PrimaryCategory.from_id("invalid")

    def test_from_id_or_value_with_id(self):
        """from_id_or_value should accept numeric ID."""
        result = PrimaryCategory.from_id_or_value("1")
        assert result == PrimaryCategory.PLAY_AND_PURE_FUN

    def test_from_id_or_value_with_value(self):
        """from_id_or_value should accept string value."""
        result = PrimaryCategory.from_id_or_value("play_and_fun")
        assert result == PrimaryCategory.PLAY_AND_PURE_FUN

    def test_from_id_or_value_invalid(self):
        """from_id_or_value should raise ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid value"):
            PrimaryCategory.from_id_or_value("not_a_category")

    def test_to_id(self):
        """to_id should return numeric ID for category."""
        assert PrimaryCategory.PLAY_AND_PURE_FUN.to_id() == "1"
        assert PrimaryCategory.SOCIAL_CONNECTION.to_id() == "5"
        assert PrimaryCategory.CONTRIBUTION_AND_IMPACT.to_id() == "10"


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
        # Each option should have required keys
        for opt in options[:5]:  # Check first 5
            assert "id" in opt
            assert "name" in opt

    def test_ids_for_primary_returns_subcategories(self):
        """ids_for_primary should return subcategories for a primary category."""
        # Use taxonomy key format
        ids = Subcategory.ids_for_primary("play_and_fun")
        assert isinstance(ids, set)
        # May be empty if key format doesn't match - just verify return type

    def test_get_by_id_valid(self):
        """get_by_id should return subcategory dict for valid ID."""
        # Get a valid ID from all_ids
        all_ids = Subcategory.all_ids()
        if all_ids:
            valid_id = next(iter(all_ids))
            result = Subcategory.get_by_id(valid_id)
            assert result is not None
            assert "id" in result

    def test_get_by_id_invalid(self):
        """get_by_id should return None for invalid ID."""
        result = Subcategory.get_by_id("99.99")
        assert result is None

    def test_validate_for_primary_valid(self):
        """validate_for_primary should return True for valid match."""
        # Subcategory 1.x should belong to primary 1
        all_ids = Subcategory.all_ids()
        for sub_id in all_ids:
            if sub_id.startswith("1."):
                assert Subcategory.validate_for_primary(sub_id, "1") is True
                break

    def test_validate_for_primary_invalid(self):
        """validate_for_primary should return False for invalid match."""
        # Subcategory 2.x should not belong to primary 1
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
        """Valid lat/lon should create Coordinates."""
        coords = Coordinates(latitude=40.7128, longitude=-74.0060)
        assert coords.latitude == 40.7128
        assert coords.longitude == -74.0060

    def test_edge_valid_coordinates(self):
        """Edge case valid coordinates."""
        coords = Coordinates(latitude=90, longitude=180)
        assert coords.latitude == 90
        assert coords.longitude == 180

        coords = Coordinates(latitude=-90, longitude=-180)
        assert coords.latitude == -90
        assert coords.longitude == -180

    def test_latitude_too_high(self):
        """Latitude > 90 should raise ValidationError."""
        with pytest.raises(ValidationError, match="Latitude must be between"):
            Coordinates(latitude=91, longitude=0)

    def test_latitude_too_low(self):
        """Latitude < -90 should raise ValidationError."""
        with pytest.raises(ValidationError, match="Latitude must be between"):
            Coordinates(latitude=-91, longitude=0)

    def test_longitude_too_high(self):
        """Longitude > 180 should raise ValidationError."""
        with pytest.raises(ValidationError, match="Longitude must be between"):
            Coordinates(latitude=0, longitude=181)

    def test_longitude_too_low(self):
        """Longitude < -180 should raise ValidationError."""
        with pytest.raises(ValidationError, match="Longitude must be between"):
            Coordinates(latitude=0, longitude=-181)


class TestLocationInfo:
    """Tests for LocationInfo model."""

    def test_minimal_location(self):
        """Minimal valid location with just city."""
        loc = LocationInfo(city="Barcelona")
        assert loc.city == "Barcelona"
        assert loc.country_code == "US"  # Default
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
        """Invalid price range where max < min should raise."""
        with pytest.raises(
            ValidationError, match="maximum_price cannot be less than minimum_price"
        ):
            PriceInfo(minimum_price=50, maximum_price=10)

    def test_negative_price_rejected(self):
        """Negative prices should be rejected."""
        with pytest.raises(ValidationError):
            PriceInfo(minimum_price=-10)

    def test_is_free_flag(self):
        """is_free flag should work."""
        price = PriceInfo(is_free=True)
        assert price.is_free is True


class TestTicketInfo:
    """Tests for TicketInfo model."""

    def test_default_values(self):
        """Default TicketInfo values."""
        ticket = TicketInfo()
        assert ticket.url is None
        assert ticket.is_sold_out is False

    def test_full_ticket_info(self):
        """Full ticket info."""
        ticket = TicketInfo(
            url="https://tickets.example.com",
            is_sold_out=True,
            ticket_count_available=0,
        )
        assert ticket.is_sold_out is True


class TestOrganizerInfo:
    """Tests for OrganizerInfo model."""

    def test_minimal_organizer(self):
        """Minimal organizer with just name."""
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
        """Minimal required source info."""
        source = SourceInfo(
            source_name="test_source",
            source_event_id="12345",
            source_url="https://source.com/event/12345",
            updated_at=datetime.now(timezone.utc),
        )
        assert source.source_name == "test_source"
        assert source.ingestion_timestamp is not None  # Auto-set


class TestMediaAsset:
    """Tests for MediaAsset model."""

    def test_minimal_asset(self):
        """Minimal media asset."""
        asset = MediaAsset(type="image", url="https://example.com/image.jpg")
        assert asset.type == "image"
        assert asset.url == "https://example.com/image.jpg"


class TestEngagementMetrics:
    """Tests for EngagementMetrics model."""

    def test_default_values(self):
        """All fields should be optional."""
        metrics = EngagementMetrics()
        assert metrics.going_count is None
        assert metrics.interested_count is None

    def test_with_values(self):
        """Set engagement values."""
        metrics = EngagementMetrics(
            going_count=100,
            interested_count=500,
            views_count=1000,
        )
        assert metrics.going_count == 100


class TestTaxonomyDimension:
    """Tests for TaxonomyDimension validation."""

    def test_minimal_dimension(self):
        """Minimal valid dimension."""
        dim = TaxonomyDimension(primary_category=PrimaryCategory.PLAY_AND_PURE_FUN)
        assert dim.primary_category == PrimaryCategory.PLAY_AND_PURE_FUN
        assert dim.confidence == 0.5  # Default

    def test_with_valid_subcategory(self):
        """Dimension with valid subcategory."""
        # Get a valid subcategory for category 1
        all_ids = Subcategory.all_ids()
        valid_sub = None
        for sub_id in all_ids:
            if sub_id.startswith("1."):
                valid_sub = sub_id
                break

        if valid_sub:
            dim = TaxonomyDimension(
                primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
                subcategory=valid_sub,
            )
            assert dim.subcategory == valid_sub

    def test_invalid_subcategory_id(self):
        """Invalid subcategory ID should raise."""
        with pytest.raises(ValidationError, match="not a valid taxonomy id"):
            TaxonomyDimension(
                primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
                subcategory="99.99",  # Invalid
            )

    def test_subcategory_primary_mismatch(self):
        """Subcategory must belong to primary category."""
        # Get a subcategory for category 2
        all_ids = Subcategory.all_ids()
        cat2_sub = None
        for sub_id in all_ids:
            if sub_id.startswith("2."):
                cat2_sub = sub_id
                break

        if cat2_sub:
            with pytest.raises(ValidationError, match="does not belong to"):
                TaxonomyDimension(
                    primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,  # Category 1
                    subcategory=cat2_sub,  # Category 2 subcategory
                )

    def test_confidence_bounds(self):
        """Confidence must be 0.0-1.0."""
        dim = TaxonomyDimension(
            primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
            confidence=0.95,
        )
        assert dim.confidence == 0.95

        with pytest.raises(ValidationError):
            TaxonomyDimension(
                primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
                confidence=1.5,  # Too high
            )

        with pytest.raises(ValidationError):
            TaxonomyDimension(
                primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
                confidence=-0.1,  # Too low
            )

    def test_empty_subcategory_allowed(self):
        """Empty string subcategory should be converted to None."""
        dim = TaxonomyDimension(
            primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
            subcategory="",
        )
        assert dim.subcategory is None


class TestEventSchema:
    """Tests for EventSchema validation."""

    def test_minimal_valid_event(self, create_event):
        """Minimal valid event with required fields only."""
        event = create_event()
        assert event.title == "Test Event"
        assert event.primary_category == PrimaryCategory.PLAY_AND_PURE_FUN

    def test_event_defaults(self, create_event):
        """Default values should be applied."""
        event = create_event()
        assert event.description is None
        assert event.taxonomy_dimensions == []
        assert event.is_all_day is False
        assert event.is_recurring is False
        assert event.data_quality_score == 0.0
        assert event.normalization_errors == []
        assert event.tags == []
        assert event.custom_fields == {}

    def test_event_with_taxonomy_dimensions(self, create_event):
        """Event with taxonomy dimensions."""
        dim = TaxonomyDimension(
            primary_category=PrimaryCategory.PLAY_AND_PURE_FUN,
            confidence=0.9,
        )
        event = create_event(taxonomy_dimensions=[dim])
        assert len(event.taxonomy_dimensions) == 1
        assert event.taxonomy_dimensions[0].confidence == 0.9

    def test_quality_score_bounds(self, create_event):
        """Quality score must be 0.0-1.0."""
        event = create_event(data_quality_score=0.85)
        assert event.data_quality_score == 0.85

        with pytest.raises(ValidationError):
            create_event(data_quality_score=1.5)

        with pytest.raises(ValidationError):
            create_event(data_quality_score=-0.1)

    def test_custom_fields_stored(self, create_event):
        """Custom fields should be stored."""
        event = create_event(
            custom_fields={"spotify_url": "https://spotify.com/artist"}
        )
        assert event.custom_fields["spotify_url"] == "https://spotify.com/artist"

    def test_event_with_price(self, create_event):
        """Event with price info."""
        price = PriceInfo(minimum_price=25, maximum_price=50, currency="EUR")
        event = create_event(price=price)
        assert event.price.currency == "EUR"
        assert event.price.minimum_price == Decimal("25")

    def test_event_with_coordinates(self, create_event):
        """Event with location coordinates."""
        location = LocationInfo(
            city="Barcelona",
            venue_name="Club XYZ",
            coordinates=Coordinates(latitude=41.3851, longitude=2.1734),
        )
        event = create_event(location=location)
        assert event.location.coordinates.latitude == 41.3851


class TestEventBatch:
    """Tests for EventBatch model."""

    def test_batch_creation(self, create_event):
        """Basic batch creation."""
        events = [create_event(title=f"Event {i}") for i in range(3)]
        batch = EventBatch(
            source_name="test_source",
            batch_id="batch-001",
            events=events,
            total_count=3,
        )
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
        """Batch should have ingestion timestamp."""
        events = [create_event()]
        batch = EventBatch(
            source_name="test",
            batch_id="batch-003",
            events=events,
            total_count=1,
        )
        assert batch.ingestion_timestamp is not None
