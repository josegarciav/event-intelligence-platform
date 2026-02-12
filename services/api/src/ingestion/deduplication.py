"""
Module for event deduplication strategies.

Provides multiple deduplication strategies using the Strategy pattern:
- ExactMatchDeduplicator: Match by title + venue + date (exact)
- FuzzyMatchDeduplicator: Fuzzy match for typos/variations (not yet implemented)
- CompositeDeduplicator: Chain multiple strategies
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional

from src.schemas.event import EventSchema


class DeduplicationStrategy(str, Enum):
    """Available deduplication strategies."""

    EXACT = "exact"
    FUZZY = "fuzzy"  # Not yet implemented
    METADATA = "metadata"  # Not yet implemented
    COMPOSITE = "composite"  # Not yet implemented


class EventDeduplicator(ABC):
    """Abstract base for deduplication strategies."""

    @abstractmethod
    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """Deduplicate events and return unique set."""
        pass


class ExactMatchDeduplicator(EventDeduplicator):
    """Match by title + venue + date (exact)."""

    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """
        Deduplicate events using exact matching on title, venue, and date.

        Returns:
            List of unique events (first occurrence kept)
        """
        seen = set()
        unique_events = []

        for event in events:
            venue_name = event.location.venue_name or "unknown_venue"
            key = (event.title, venue_name, str(event.start_datetime))

            if key not in seen:
                seen.add(key)
                unique_events.append(event)

        return unique_events


class FuzzyMatchDeduplicator(EventDeduplicator):
    """
    Fuzzy match for typos/variations.

    NOT YET IMPLEMENTED - falls back to exact match.
    TODO: Implement with rapidfuzz or difflib
    """

    def __init__(self, threshold: float = 0.85):
        """
        Initialize with similarity threshold.

        Args:
            threshold: Similarity threshold (0.0-1.0) for matching
        """
        self.threshold = threshold

    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """
        Deduplicate events using fuzzy matching.

        NOTE: Not yet implemented - falls back to exact match.

        Returns:
            List of unique events
        """
        # TODO: Implement with rapidfuzz or difflib
        # For now, fall back to exact match
        return ExactMatchDeduplicator().deduplicate(events)


class MetadataDeduplicator(EventDeduplicator):
    """
    Match by multiple metadata fields with weights.

    NOT YET IMPLEMENTED - falls back to exact match.
    TODO: Implement weighted similarity scoring
    """

    def __init__(self, weights: Optional[dict] = None):
        """
        Initialize with field weights.

        Args:
            weights: Dict of field -> weight (e.g., {'title': 0.4, 'venue': 0.3})
        """
        self.weights = weights or {
            "title": 0.4,
            "venue": 0.3,
            "date": 0.2,
            "artists": 0.1,
        }

    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """
        Deduplicate events using weighted metadata matching.

        NOTE: Not yet implemented - falls back to exact match.

        Returns:
            List of unique events
        """
        # TODO: Implement weighted similarity scoring
        return ExactMatchDeduplicator().deduplicate(events)


class CompositeDeduplicator(EventDeduplicator):
    """Chain multiple deduplication strategies."""

    def __init__(self, strategies: Optional[List[EventDeduplicator]] = None):
        """
        Initialize with list of strategies to chain.

        Args:
            strategies: List of deduplicators to apply in sequence
        """
        self.strategies = strategies or [ExactMatchDeduplicator()]

    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """
        Apply each strategy in sequence.

        Returns:
            List of unique events after all strategies applied
        """
        result = events
        for strategy in self.strategies:
            result = strategy.deduplicate(result)
        return result


def get_deduplicator(
    strategy: DeduplicationStrategy = DeduplicationStrategy.EXACT,
) -> EventDeduplicator:
    """
    Create a deduplicator instance for the given strategy.

    Args:
        strategy: DeduplicationStrategy enum value

    Returns:
        Configured EventDeduplicator instance
    """
    if strategy == DeduplicationStrategy.EXACT:
        return ExactMatchDeduplicator()
    elif strategy == DeduplicationStrategy.FUZZY:
        return FuzzyMatchDeduplicator()
    elif strategy == DeduplicationStrategy.METADATA:
        return MetadataDeduplicator()
    elif strategy == DeduplicationStrategy.COMPOSITE:
        return CompositeDeduplicator()
    else:
        return ExactMatchDeduplicator()
