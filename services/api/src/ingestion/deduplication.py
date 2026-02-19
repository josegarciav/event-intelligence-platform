"""
Module for event deduplication strategies.

Provides multiple deduplication strategies using the Strategy pattern:
- ExactMatchDeduplicator: Match by title + venue + date (exact)
- FuzzyMatchDeduplicator: Fuzzy match for typos/variations via difflib
- MetadataDeduplicator: Weighted multi-field similarity scoring
- CompositeDeduplicator: Chain multiple strategies
"""

from abc import ABC, abstractmethod
from difflib import SequenceMatcher
from enum import Enum

from src.schemas.event import EventSchema


class DeduplicationStrategy(str, Enum):
    """Available deduplication strategies."""

    EXACT = "exact"
    FUZZY = "fuzzy"
    METADATA = "metadata"
    COMPOSITE = "composite"


class EventDeduplicator(ABC):
    """Abstract base for deduplication strategies."""

    @abstractmethod
    def deduplicate(self, events: list[EventSchema]) -> list[EventSchema]:
        """Deduplicate events and return unique set."""
        pass


class ExactMatchDeduplicator(EventDeduplicator):
    """Match by title + venue + date (exact)."""

    def deduplicate(self, events: list[EventSchema]) -> list[EventSchema]:
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
    Fuzzy title match for typos and slight variations in event names.

    Uses difflib.SequenceMatcher to detect near-duplicate events. Two events
    are considered duplicates when they share the same date and their titles
    have a similarity ratio >= threshold.
    """

    def __init__(self, threshold: float = 0.85):
        """
        Initialize with similarity threshold.

        Args:
            threshold: Similarity threshold (0.0-1.0) for title matching
        """
        self.threshold = threshold

    def deduplicate(self, events: list[EventSchema]) -> list[EventSchema]:
        """
        Deduplicate events using fuzzy title matching grouped by date.

        Two events on the same day whose titles match with ratio >= threshold
        are treated as duplicates; the first occurrence is kept.

        Returns:
            List of unique events
        """
        unique_events: list[EventSchema] = []

        for event in events:
            is_duplicate = False
            event_date = event.start_datetime.date()
            event_title = event.title.lower()

            for kept in unique_events:
                if kept.start_datetime.date() != event_date:
                    continue
                ratio = SequenceMatcher(None, event_title, kept.title.lower()).ratio()
                if ratio >= self.threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_events.append(event)

        return unique_events


class MetadataDeduplicator(EventDeduplicator):
    """
    Match by multiple metadata fields with configurable weights.

    Computes a weighted similarity score across title, venue, date, and artists.
    Events whose combined score >= SIMILARITY_THRESHOLD are considered duplicates.
    """

    SIMILARITY_THRESHOLD = 0.8

    def __init__(self, weights: dict | None = None):
        """
        Initialize with field weights.

        Args:
            weights: Dict of field -> weight (e.g., {'title': 0.4, 'venue': 0.3}).
                     Weights are normalized so they need not sum to 1.0.
        """
        self.weights = weights or {
            "title": 0.4,
            "venue": 0.3,
            "date": 0.2,
            "artists": 0.1,
        }

    def deduplicate(self, events: list[EventSchema]) -> list[EventSchema]:
        """
        Deduplicate events using weighted metadata similarity scoring.

        Each candidate is compared against already-accepted events. If the
        weighted similarity score exceeds SIMILARITY_THRESHOLD, the candidate
        is treated as a duplicate and discarded.

        Returns:
            List of unique events (first occurrence kept)
        """
        unique_events: list[EventSchema] = []

        for event in events:
            is_duplicate = any(
                self._similarity_score(event, kept) >= self.SIMILARITY_THRESHOLD
                for kept in unique_events
            )
            if not is_duplicate:
                unique_events.append(event)

        return unique_events

    def _similarity_score(self, a: EventSchema, b: EventSchema) -> float:
        """Compute normalized weighted similarity score between two events (0.0-1.0)."""
        weight_sum = sum(self.weights.values())
        if weight_sum == 0:
            return 0.0

        total = 0.0

        # Title similarity
        title_sim = SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()
        total += title_sim * self.weights.get("title", 0)

        # Venue similarity
        venue_a = (a.location.venue_name or "").lower()
        venue_b = (b.location.venue_name or "").lower()
        if venue_a and venue_b:
            venue_sim = SequenceMatcher(None, venue_a, venue_b).ratio()
        elif not venue_a and not venue_b:
            venue_sim = 1.0
        else:
            venue_sim = 0.0
        total += venue_sim * self.weights.get("venue", 0)

        # Date similarity: 1.0 at same second, 0.0 at >= 24 hours apart
        date_diff_s = abs((a.start_datetime - b.start_datetime).total_seconds())
        date_sim = max(0.0, 1.0 - date_diff_s / 86400)
        total += date_sim * self.weights.get("date", 0)

        # Artist overlap (Jaccard similarity over name sets)
        artists_a = {ar.name.lower() for ar in a.artists if ar.name}
        artists_b = {ar.name.lower() for ar in b.artists if ar.name}
        if artists_a or artists_b:
            union = len(artists_a | artists_b)
            artist_sim = len(artists_a & artists_b) / union if union > 0 else 0.0
        else:
            artist_sim = 1.0  # no artists on either side → no artist-based divergence
        total += artist_sim * self.weights.get("artists", 0)

        return total / weight_sum


class CompositeDeduplicator(EventDeduplicator):
    """Chain multiple deduplication strategies."""

    def __init__(self, strategies: list[EventDeduplicator] | None = None):
        """
        Initialize with list of strategies to chain.

        Args:
            strategies: List of deduplicators to apply in sequence
        """
        self.strategies = strategies or [ExactMatchDeduplicator()]

    def deduplicate(self, events: list[EventSchema]) -> list[EventSchema]:
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
