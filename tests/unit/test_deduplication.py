"""
Unit tests for the deduplication module.

Tests all deduplication strategies:
- ExactMatchDeduplicator
- FuzzyMatchDeduplicator (stub)
- MetadataDeduplicator (stub)
- CompositeDeduplicator
- get_deduplicator factory function
"""

from datetime import datetime, timezone


from src.ingestion.deduplication import (
    CompositeDeduplicator,
    DeduplicationStrategy,
    ExactMatchDeduplicator,
    FuzzyMatchDeduplicator,
    MetadataDeduplicator,
    get_deduplicator,
)


class TestDeduplicationStrategy:
    """Tests for the DeduplicationStrategy enum."""

    def test_strategy_enum_values(self):
        """All 4 strategies should exist in the enum."""
        assert DeduplicationStrategy.EXACT.value == "exact"
        assert DeduplicationStrategy.FUZZY.value == "fuzzy"
        assert DeduplicationStrategy.METADATA.value == "metadata"
        assert DeduplicationStrategy.COMPOSITE.value == "composite"

    def test_strategy_string_conversion(self):
        """Enum values should match their string representations."""
        assert str(DeduplicationStrategy.EXACT.value) == "exact"
        assert str(DeduplicationStrategy.FUZZY.value) == "fuzzy"
        assert str(DeduplicationStrategy.METADATA.value) == "metadata"
        assert str(DeduplicationStrategy.COMPOSITE.value) == "composite"


class TestExactMatchDeduplicator:
    """Tests for ExactMatchDeduplicator."""

    def test_deduplicate_no_duplicates(self, sample_events):
        """All unique events should pass through unchanged."""
        deduplicator = ExactMatchDeduplicator()
        result = deduplicator.deduplicate(sample_events)

        assert len(result) == len(sample_events)
        assert result == sample_events

    def test_deduplicate_with_duplicates(self, duplicate_events):
        """Duplicates should be removed, keeping the first occurrence."""
        deduplicator = ExactMatchDeduplicator()
        result = deduplicator.deduplicate(duplicate_events)

        # Should have 3 events (4 input - 1 duplicate)
        assert len(result) == 3

        # The first occurrence of "Duplicate Event" should be kept
        titles = [e.title for e in result]
        assert titles.count("Duplicate Event") == 1
        assert "Unique Event 1" in titles
        assert "Unique Event 2" in titles

    def test_deduplicate_empty_list(self):
        """Empty input should return empty output."""
        deduplicator = ExactMatchDeduplicator()
        result = deduplicator.deduplicate([])

        assert result == []

    def test_deduplicate_single_event(self, sample_event):
        """Single event should pass through unchanged."""
        deduplicator = ExactMatchDeduplicator()
        result = deduplicator.deduplicate([sample_event])

        assert len(result) == 1
        assert result[0] == sample_event

    def test_deduplicate_none_venue_name(self, create_event):
        """Events with None venue_name should use 'unknown_venue' fallback."""
        deduplicator = ExactMatchDeduplicator()

        # Create two events with None venue_name but same title and datetime
        base_datetime = datetime(2024, 6, 15, 20, 0, tzinfo=timezone.utc)
        event1 = create_event(
            title="No Venue Event",
            venue_name=None,
            start_datetime=base_datetime,
        )
        event2 = create_event(
            title="No Venue Event",
            venue_name=None,
            start_datetime=base_datetime,
        )

        result = deduplicator.deduplicate([event1, event2])

        # Should be treated as duplicates (both use "unknown_venue" fallback)
        assert len(result) == 1
        assert result[0] == event1

    def test_deduplicate_same_title_different_venue(self, create_event):
        """Events with same title but different venue are NOT duplicates."""
        deduplicator = ExactMatchDeduplicator()

        base_datetime = datetime(2024, 6, 15, 20, 0, tzinfo=timezone.utc)
        event1 = create_event(
            title="Same Title",
            venue_name="Venue A",
            start_datetime=base_datetime,
        )
        event2 = create_event(
            title="Same Title",
            venue_name="Venue B",
            start_datetime=base_datetime,
        )

        result = deduplicator.deduplicate([event1, event2])

        assert len(result) == 2

    def test_deduplicate_same_venue_different_title(self, create_event):
        """Events with same venue but different title are NOT duplicates."""
        deduplicator = ExactMatchDeduplicator()

        base_datetime = datetime(2024, 6, 15, 20, 0, tzinfo=timezone.utc)
        event1 = create_event(
            title="Title A",
            venue_name="Same Venue",
            start_datetime=base_datetime,
        )
        event2 = create_event(
            title="Title B",
            venue_name="Same Venue",
            start_datetime=base_datetime,
        )

        result = deduplicator.deduplicate([event1, event2])

        assert len(result) == 2

    def test_deduplicate_same_title_venue_different_datetime(self, create_event):
        """Events with same title and venue but different datetime are NOT duplicates."""
        deduplicator = ExactMatchDeduplicator()

        event1 = create_event(
            title="Same Event",
            venue_name="Same Venue",
            start_datetime=datetime(2024, 6, 15, 20, 0, tzinfo=timezone.utc),
        )
        event2 = create_event(
            title="Same Event",
            venue_name="Same Venue",
            start_datetime=datetime(2024, 6, 16, 20, 0, tzinfo=timezone.utc),
        )

        result = deduplicator.deduplicate([event1, event2])

        assert len(result) == 2

    def test_deduplicate_preserves_order(self, create_event):
        """First occurrence of a duplicate should be kept, order preserved."""
        deduplicator = ExactMatchDeduplicator()

        base_datetime = datetime(2024, 6, 15, 20, 0, tzinfo=timezone.utc)

        # Create events with specific identifiable event_ids
        event1 = create_event(
            title="Duplicate",
            venue_name="Venue",
            start_datetime=base_datetime,
        )
        event2 = create_event(
            title="Unique",
            venue_name="Other Venue",
            start_datetime=base_datetime,
        )
        event3 = create_event(
            title="Duplicate",
            venue_name="Venue",
            start_datetime=base_datetime,
        )  # Duplicate of event1

        result = deduplicator.deduplicate([event1, event2, event3])

        assert len(result) == 2
        # First occurrence (event1) should be kept, not event3
        assert result[0].event_id == event1.event_id
        assert result[1].event_id == event2.event_id


class TestFuzzyMatchDeduplicator:
    """Tests for FuzzyMatchDeduplicator (currently a stub)."""

    def test_init_default_threshold(self):
        """Default threshold should be 0.85."""
        deduplicator = FuzzyMatchDeduplicator()
        assert deduplicator.threshold == 0.85

    def test_init_custom_threshold(self):
        """Custom threshold should be accepted."""
        deduplicator = FuzzyMatchDeduplicator(threshold=0.9)
        assert deduplicator.threshold == 0.9

    def test_deduplicate_falls_back_to_exact(self, duplicate_events):
        """Currently falls back to exact match behavior."""
        fuzzy = FuzzyMatchDeduplicator()
        exact = ExactMatchDeduplicator()

        fuzzy_result = fuzzy.deduplicate(duplicate_events)
        exact_result = exact.deduplicate(duplicate_events)

        # Should produce same results as exact match (fallback)
        assert len(fuzzy_result) == len(exact_result)

    def test_threshold_stored(self):
        """Threshold should be stored for future use."""
        threshold = 0.75
        deduplicator = FuzzyMatchDeduplicator(threshold=threshold)
        assert deduplicator.threshold == threshold


class TestMetadataDeduplicator:
    """Tests for MetadataDeduplicator (currently a stub)."""

    def test_init_default_weights(self):
        """Default weights should be set."""
        deduplicator = MetadataDeduplicator()
        expected_weights = {
            "title": 0.4,
            "venue": 0.3,
            "date": 0.2,
            "artists": 0.1,
        }
        assert deduplicator.weights == expected_weights

    def test_init_custom_weights(self):
        """Custom weights should be accepted."""
        custom_weights = {"title": 0.5, "venue": 0.5}
        deduplicator = MetadataDeduplicator(weights=custom_weights)
        assert deduplicator.weights == custom_weights

    def test_deduplicate_falls_back_to_exact(self, duplicate_events):
        """Currently falls back to exact match behavior."""
        metadata = MetadataDeduplicator()
        exact = ExactMatchDeduplicator()

        metadata_result = metadata.deduplicate(duplicate_events)
        exact_result = exact.deduplicate(duplicate_events)

        # Should produce same results as exact match (fallback)
        assert len(metadata_result) == len(exact_result)

    def test_weights_stored(self):
        """Weights should be stored for future use."""
        weights = {"title": 0.6, "venue": 0.4}
        deduplicator = MetadataDeduplicator(weights=weights)
        assert deduplicator.weights == weights


class TestCompositeDeduplicator:
    """Tests for CompositeDeduplicator."""

    def test_init_default_strategies(self):
        """Default should be a list with ExactMatchDeduplicator."""
        deduplicator = CompositeDeduplicator()
        assert len(deduplicator.strategies) == 1
        assert isinstance(deduplicator.strategies[0], ExactMatchDeduplicator)

    def test_init_custom_strategies(self):
        """Custom strategies should be accepted."""
        strategies = [ExactMatchDeduplicator(), FuzzyMatchDeduplicator()]
        deduplicator = CompositeDeduplicator(strategies=strategies)
        assert len(deduplicator.strategies) == 2
        assert isinstance(deduplicator.strategies[0], ExactMatchDeduplicator)
        assert isinstance(deduplicator.strategies[1], FuzzyMatchDeduplicator)

    def test_deduplicate_single_strategy(self, duplicate_events):
        """Works correctly with a single strategy."""
        deduplicator = CompositeDeduplicator(strategies=[ExactMatchDeduplicator()])
        result = deduplicator.deduplicate(duplicate_events)

        # Same as ExactMatchDeduplicator alone
        assert len(result) == 3

    def test_deduplicate_chains_strategies(self, duplicate_events):
        """Each strategy operates on the output of the previous one."""
        # Use two exact match deduplicators - second should have no effect
        # since first already removed duplicates
        deduplicator = CompositeDeduplicator(
            strategies=[ExactMatchDeduplicator(), ExactMatchDeduplicator()]
        )
        result = deduplicator.deduplicate(duplicate_events)

        # Should still be 3 - second strategy has nothing to remove
        assert len(result) == 3

    def test_deduplicate_empty_strategies(self, duplicate_events):
        """Empty strategies list falls back to default (ExactMatchDeduplicator).

        Due to 'strategies or [default]' in __init__, an empty list is falsy
        and triggers the default behavior.
        """
        deduplicator = CompositeDeduplicator(strategies=[])
        result = deduplicator.deduplicate(duplicate_events)

        # Empty list is falsy, so falls back to default ExactMatchDeduplicator
        # which removes duplicates (4 -> 3)
        assert len(result) == 3
        assert isinstance(deduplicator.strategies[0], ExactMatchDeduplicator)


class TestGetDeduplicator:
    """Tests for the get_deduplicator factory function."""

    def test_get_exact_deduplicator(self):
        """Should return ExactMatchDeduplicator for EXACT strategy."""
        deduplicator = get_deduplicator(DeduplicationStrategy.EXACT)
        assert isinstance(deduplicator, ExactMatchDeduplicator)

    def test_get_fuzzy_deduplicator(self):
        """Should return FuzzyMatchDeduplicator for FUZZY strategy."""
        deduplicator = get_deduplicator(DeduplicationStrategy.FUZZY)
        assert isinstance(deduplicator, FuzzyMatchDeduplicator)

    def test_get_metadata_deduplicator(self):
        """Should return MetadataDeduplicator for METADATA strategy."""
        deduplicator = get_deduplicator(DeduplicationStrategy.METADATA)
        assert isinstance(deduplicator, MetadataDeduplicator)

    def test_get_composite_deduplicator(self):
        """Should return CompositeDeduplicator for COMPOSITE strategy."""
        deduplicator = get_deduplicator(DeduplicationStrategy.COMPOSITE)
        assert isinstance(deduplicator, CompositeDeduplicator)

    def test_default_strategy(self):
        """No argument should return ExactMatchDeduplicator (default)."""
        deduplicator = get_deduplicator()
        assert isinstance(deduplicator, ExactMatchDeduplicator)
