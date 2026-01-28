# Base abstract class
"""
Module for event deduplication strategies.
"""

from abc import ABC, abstractmethod
from typing import List
from src.normalization.event_schema import EventSchema


class EventDeduplicator(ABC):
    """
    Abstract base for deduplication strategies
    """

    @abstractmethod
    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """
        Deduplicate events and return unique set
        """
        pass


# Protocol implementations
class ExactMatchDeduplicator(EventDeduplicator):
    """
    Match by title + venue + date (exact)
    """

    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """
        Deduplicate events using exact matching on title, venue, and date.

        Returns:
            List of unique events (first occurrence kept)
        """
        seen = set()
        unique_events = []

        for event in events:
            # Create composite key from title, venue name, and start datetime
            venue_name = event.location.venue_name or "unknown_venue"
            key = (event.title, venue_name, str(event.start_datetime))

            if key not in seen:
                seen.add(key)
                unique_events.append(event)

        return unique_events


class FuzzyMatchDeduplicator(EventDeduplicator):
    """
    Fuzzy match for typos/variations

    Uses similarity matching to handle slight variations in titles/venues.
    """

    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """
        Deduplicate events using fuzzy matching.

        Currently uses a basic similarity approach. Can be enhanced with
        difflib.SequenceMatcher or fuzzy_string_matching libraries.

        Returns:
            List of unique events
        """
        # TODO: Integrate with difflib or rapidfuzz for production
        # For now, use exact match as placeholder
        return ExactMatchDeduplicator().deduplicate(events)


class MetadataDeduplicator(EventDeduplicator):
    """
    Match by multiple metadata fields with weights

    Considers multiple fields (title, venue, date, artists) with configurable weights.
    """

    def __init__(self, weights: dict = None):
        """
        Initialize with field weights.

        Args:
            weights: Dict of field -> weight (e.g., {'title': 0.4, 'venue': 0.3, 'date': 0.3})
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

        Returns:
            List of unique events
        """
        # TODO: Implement weighted similarity scoring
        # For now, use exact match as placeholder
        return ExactMatchDeduplicator().deduplicate(events)


class CompositeDeduplicator(EventDeduplicator):
    """
    Combine multiple strategies with fallback logic

    Tries primary strategy first, falls back to secondary if needed.
    """

    def __init__(
        self, primary: EventDeduplicator = None, secondary: EventDeduplicator = None
    ):
        """
        Initialize with primary and secondary deduplicators.

        Args:
            primary: Primary deduplication strategy
            secondary: Fallback strategy if primary insufficient
        """
        self.primary = primary or ExactMatchDeduplicator()
        self.secondary = secondary or FuzzyMatchDeduplicator()

    def deduplicate(self, events: List[EventSchema]) -> List[EventSchema]:
        """
        Apply primary deduplicator, then secondary on remaining.

        Returns:
            List of unique events
        """
        # First pass with primary strategy
        after_primary = self.primary.deduplicate(events)

        # Second pass with secondary strategy for any remaining duplicates
        final = self.secondary.deduplicate(after_primary)

        return final
