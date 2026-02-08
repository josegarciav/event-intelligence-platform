# Persistence layer for ingested data
"""
Persistence Layer for Event Ingestion.

Handles the atomic upsert of EventSchema objects into the relational
PostgreSQL schema, managing foreign key relationships and transactions.
"""

import logging
from typing import List, Optional

import psycopg2
from psycopg2.extras import execute_values

from src.schemas.event import EventSchema

logger = logging.getLogger(__name__)


class EventDataWriter:
    """
    Handles persisting normalized EventSchema objects to the PostgreSQL database.

    Implements the 'Data Mapper' pattern to bridge the gap between Python
    objects and the relational schema.
    """

    def __init__(self, db_connection) -> None:
        """
        Initialize with an active psycopg2 connection.
        """
        self.conn = db_connection

    def persist_batch(self, events: List[EventSchema]) -> int:
        """
        Persists a list of events to the database.

        Returns:
            int: Number of successfully persisted events.
        """
        success_count = 0
        for event in events:
            try:
                self._persist_single_event(event)
                success_count += 1
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Failed to persist event '{event.title}': {e}")
                continue

        self.conn.commit()
        return success_count

    def _persist_single_event(self, event: EventSchema) -> None:
        """
        Handles the atomic insertion of a single event and its related child records.
        """
        with self.conn.cursor() as cur:
            # 1. Persist Location first (needed for foreign key in events)
            loc = event.location
            cur.execute(
                """
                INSERT INTO locations (
                    venue_name, street_address, city, state_or_region, 
                    postal_code, country_code, latitude, longitude, timezone
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING location_id;
                """,
                (
                    loc.venue_name,
                    loc.street_address,
                    loc.city,
                    loc.state_or_region,
                    loc.postal_code,
                    loc.country_code,
                    loc.latitude,
                    loc.longitude,
                    loc.timezone,
                ),
            )
            res = cur.fetchone()
            # If CONFLICT, find the existing ID
            if not res:
                cur.execute(
                    "SELECT location_id FROM locations WHERE venue_name = %s AND street_address = %s",
                    (loc.venue_name, loc.street_address),
                )
                location_id = cur.fetchone()[0]
            else:
                location_id = res[0]

            # 2. Persist Source info
            cur.execute(
                """
                INSERT INTO sources (source_name, source_event_id, source_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_name, source_event_id) 
                DO UPDATE SET last_updated_from_source = NOW()
                RETURNING source_id;
                """,
                (event.source_name, event.source_event_id, event.source_url),
            )
            source_id = cur.fetchone()[0]

            # 3. Persist Event (The Central Spine)
            cur.execute(
                """
                INSERT INTO events (
                    title, description, primary_category_id, start_datetime, 
                    end_datetime, location_id, source_id, data_quality_score, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT DO NOTHING 
                RETURNING event_id;
                """,
                (
                    event.title,
                    event.description,
                    event.primary_category_id,
                    event.start_datetime,
                    event.end_datetime,
                    location_id,
                    source_id,
                    event.data_quality_score,
                ),
            )
            res = cur.fetchone()
            if not res:
                # If event exists, we might want to update it. For now, fetch ID.
                cur.execute(
                    "SELECT event_id FROM events WHERE source_id = %s", (source_id,)
                )
                event_id = cur.fetchone()[0]
            else:
                event_id = res[0]

            # 4. Persist Price Snapshot (if available)
            if event.price:
                cur.execute(
                    """
                    INSERT INTO price_snapshots (
                        event_id, currency, is_free, minimum_price, maximum_price, standard_price
                    ) VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        event_id,
                        event.price.currency,
                        event.price.is_free,
                        event.price.min_price,
                        event.price.max_price,
                        event.price.standard_price,
                    ),
                )

            # 5. Persist Taxonomy Mapping
            cur.execute(
                """
                INSERT INTO event_taxonomy_mappings (
                    event_id, subcategory_id, activity_name, energy_level, environment
                ) VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    event_id,
                    event.subcategory_id,
                    event.activity_name,
                    event.energy_level,
                    event.environment,
                ),
            )
