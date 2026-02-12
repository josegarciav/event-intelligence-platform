"""
Shared pytest fixtures for the Event Intelligence Platform test suite.

Provides reusable fixtures for creating EventSchema test objects.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import pytest

from src.schemas.event import (
    EventSchema,
    EventFormat,
    LocationInfo,
    OrganizerInfo,
    PrimaryCategory,
    SourceInfo,
)


@pytest.fixture
def create_event():
    """
    Return a function that creates EventSchema objects with sensible defaults.

    Factory fixture to create EventSchema instances for testing.
    All defaults can be overridden via keyword arguments.

    Example:
        event = create_event(title="My Event", venue_name="Club XYZ")
    """

    def _create_event(
        title: str = "Test Event",
        venue_name: Optional[str] = "Test Venue",
        start_datetime: Optional[datetime] = None,
        **kwargs,
    ) -> EventSchema:
        if start_datetime is None:
            start_datetime = datetime(2024, 6, 15, 20, 0, tzinfo=timezone.utc)

        defaults = {
            "event_id": str(uuid.uuid4()),
            "title": title,
            "primary_category": PrimaryCategory.PLAY_AND_PURE_FUN,
            "start_datetime": start_datetime,
            "location": LocationInfo(
                venue_name=venue_name,
                city="Barcelona",
                country_code="ES",
            ),
            "format": EventFormat.IN_PERSON,
            "organizer": OrganizerInfo(name="Test Organizer"),
            "source": SourceInfo(
                source_name="test",
                source_event_id=str(uuid.uuid4()),
                source_url="https://test.com/event",
                source_updated_at=datetime.now(timezone.utc),
            ),
        }

        # Merge defaults with provided kwargs
        defaults.update(kwargs)

        return EventSchema(**defaults)  # type: ignore[arg-type]

    return _create_event


@pytest.fixture
def sample_event(create_event):
    """
    Return a single default test event.

    Useful for tests that need a basic event to work with.
    """
    return create_event()


@pytest.fixture
def sample_events(create_event):
    """
    Return a list of varied test events with different attributes.

    Contains 4 unique events at different venues and times.
    """
    return [
        create_event(
            title="Electronic Night",
            venue_name="Club Alpha",
            start_datetime=datetime(2024, 6, 15, 22, 0, tzinfo=timezone.utc),
        ),
        create_event(
            title="Jazz Evening",
            venue_name="Jazz Cafe",
            start_datetime=datetime(2024, 6, 16, 20, 0, tzinfo=timezone.utc),
        ),
        create_event(
            title="Rock Concert",
            venue_name="Stadium Arena",
            start_datetime=datetime(2024, 6, 17, 19, 0, tzinfo=timezone.utc),
        ),
        create_event(
            title="Comedy Show",
            venue_name="Comedy Club",
            start_datetime=datetime(2024, 6, 18, 21, 0, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def duplicate_events(create_event):
    """
    Return a list of events that contains duplicates.

    Contains:
    - 2 events with identical (title, venue, datetime) - duplicates
    - 2 unique events

    The ExactMatchDeduplicator should keep only the first occurrence of duplicates.
    """
    base_datetime = datetime(2024, 6, 15, 22, 0, tzinfo=timezone.utc)

    return [
        create_event(
            title="Duplicate Event",
            venue_name="Same Venue",
            start_datetime=base_datetime,
        ),
        create_event(
            title="Unique Event 1",
            venue_name="Different Venue",
            start_datetime=base_datetime,
        ),
        create_event(
            title="Duplicate Event",
            venue_name="Same Venue",
            start_datetime=base_datetime,
        ),  # Duplicate of first
        create_event(
            title="Unique Event 2",
            venue_name="Another Venue",
            start_datetime=datetime(2024, 6, 16, 20, 0, tzinfo=timezone.utc),
        ),
    ]
