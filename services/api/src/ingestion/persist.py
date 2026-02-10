# Persistence layer for ingested data
"""
Persistence Layer for Event Ingestion.

Handles the atomic upsert of EventSchema objects into the relational
PostgreSQL schema, managing foreign key relationships and transactions.
"""

import logging
from typing import List

from src.schemas.event import EventSchema
from src.schemas.taxonomy import get_primary_category_value_to_id_map

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
        self._value_to_id = get_primary_category_value_to_id_map()

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
            # 1. Location
            location_id = self._persist_location(cur, event)

            # 2. Source
            source_id = self._persist_source(cur, event)

            # 3. Organizer
            organizer_id = self._persist_organizer(cur, event)

            # 4. Event (central spine)
            event_id = self._persist_event(
                cur, event, location_id, source_id, organizer_id
            )

            # 5. Price snapshot
            self._persist_price_snapshot(cur, event, event_id)

            # 6. Taxonomy mappings + emotional outputs
            self._persist_taxonomy_mappings(cur, event, event_id)

            # 7. Engagement snapshot
            self._persist_engagement_snapshot(cur, event, event_id)

            # 8. Ticket info
            self._persist_ticket_info(cur, event, event_id)

            # 9. Media assets
            self._persist_media_assets(cur, event, event_id)

            # 10. Tags
            self._persist_tags(cur, event, event_id)

            # 11. Artists
            self._persist_artists(cur, event, event_id)

            # 12. Normalization errors
            self._persist_normalization_errors(cur, event, event_id)

    # ------------------------------------------------------------------
    # 1. Location
    # ------------------------------------------------------------------

    def _persist_location(self, cur, event: EventSchema):
        loc = event.location
        lat = loc.coordinates.latitude if loc.coordinates else None
        lng = loc.coordinates.longitude if loc.coordinates else None

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
                lat,
                lng,
                loc.timezone,
            ),
        )
        res = cur.fetchone()
        if res:
            return res[0]

        # Fallback lookup on conflict
        cur.execute(
            """
            SELECT location_id FROM locations
            WHERE venue_name IS NOT DISTINCT FROM %s
              AND city = %s
              AND country_code = %s
            LIMIT 1;
            """,
            (loc.venue_name, loc.city, loc.country_code),
        )
        return cur.fetchone()[0]

    # ------------------------------------------------------------------
    # 2. Source
    # ------------------------------------------------------------------

    def _persist_source(self, cur, event: EventSchema):
        src = event.source

        cur.execute(
            """
            INSERT INTO sources (
                source_name, source_event_id, source_url,
                compressed_html, ingestion_timestamp
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (source_name, source_event_id)
            DO UPDATE SET updated_at = NOW()
            RETURNING source_id;
            """,
            (
                src.source_name,
                src.source_event_id,
                src.source_url,
                src.compressed_html,
                src.ingestion_timestamp,
            ),
        )
        return cur.fetchone()[0]

    # ------------------------------------------------------------------
    # 3. Organizer
    # ------------------------------------------------------------------

    def _persist_organizer(self, cur, event: EventSchema):
        org = event.organizer

        cur.execute(
            """
            INSERT INTO organizers (
                name, url, email, phone, image_url, follower_count, verified
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                url = COALESCE(EXCLUDED.url, organizers.url),
                updated_at = NOW()
            RETURNING organizer_id;
            """,
            (
                org.name,
                org.url,
                org.email,
                org.phone,
                org.image_url,
                org.follower_count,
                org.verified,
            ),
        )
        return cur.fetchone()[0]

    # ------------------------------------------------------------------
    # 4. Event (central spine)
    # ------------------------------------------------------------------

    def _persist_event(self, cur, event: EventSchema, location_id, source_id, organizer_id):
        # Convert PrimaryCategory enum value to taxonomy ID
        primary_cat_id = self._value_to_id.get(event.primary_category)

        cur.execute(
            """
            INSERT INTO events (
                title, description, primary_category_id,
                event_type, event_format, capacity, age_restriction,
                start_datetime, end_datetime, duration_minutes,
                is_all_day, is_recurring, recurrence_pattern,
                location_id, organizer_id, source_id,
                data_quality_score, updated_at
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, NOW()
            )
            ON CONFLICT DO NOTHING
            RETURNING event_id;
            """,
            (
                event.title,
                event.description,
                primary_cat_id,
                event.event_type,
                event.format,
                event.capacity,
                event.age_restriction,
                event.start_datetime,
                event.end_datetime,
                event.duration_minutes,
                event.is_all_day,
                event.is_recurring,
                event.recurrence_pattern,
                location_id,
                organizer_id,
                source_id,
                event.data_quality_score,
            ),
        )
        res = cur.fetchone()
        if res:
            return res[0]

        # Event already exists — fetch by source
        cur.execute(
            "SELECT event_id FROM events WHERE source_id = %s",
            (source_id,),
        )
        return cur.fetchone()[0]

    # ------------------------------------------------------------------
    # 5. Price snapshot
    # ------------------------------------------------------------------

    def _persist_price_snapshot(self, cur, event: EventSchema, event_id):
        p = event.price
        cur.execute(
            """
            INSERT INTO price_snapshots (
                event_id, currency, is_free,
                minimum_price, maximum_price,
                early_bird_price, standard_price, vip_price,
                price_raw_text
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                event_id,
                p.currency,
                p.is_free,
                p.minimum_price,
                p.maximum_price,
                p.early_bird_price,
                p.standard_price,
                p.vip_price,
                p.price_raw_text,
            ),
        )

    # ------------------------------------------------------------------
    # 6. Taxonomy mappings + emotional outputs
    # ------------------------------------------------------------------

    def _persist_taxonomy_mappings(self, cur, event: EventSchema, event_id):
        for dim in event.taxonomy_dimensions:
            cur.execute(
                """
                INSERT INTO event_taxonomy_mappings (
                    event_id, subcategory_id, activity_id, activity_name,
                    energy_level, social_intensity, cognitive_load,
                    physical_involvement, cost_level, time_scale,
                    environment, risk_level, age_accessibility, repeatability
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING mapping_id;
                """,
                (
                    event_id,
                    dim.subcategory,
                    dim.activity_id,
                    dim.activity_name,
                    dim.energy_level,
                    dim.social_intensity,
                    dim.cognitive_load,
                    dim.physical_involvement,
                    dim.cost_level,
                    dim.time_scale,
                    dim.environment,
                    dim.risk_level,
                    dim.age_accessibility,
                    dim.repeatability,
                ),
            )
            mapping_id = cur.fetchone()[0]

            # Persist emotional outputs for this mapping
            for emotion in dim.emotional_output:
                cur.execute(
                    """
                    INSERT INTO activity_emotional_outputs (activity_id, emotion_name)
                    VALUES (%s, %s)
                    ON CONFLICT (activity_id, emotion_name) DO NOTHING
                    RETURNING emotional_output_id;
                    """,
                    (dim.activity_id, emotion),
                )
                res = cur.fetchone()
                if res:
                    emo_id = res[0]
                else:
                    cur.execute(
                        "SELECT emotional_output_id FROM activity_emotional_outputs "
                        "WHERE activity_id = %s AND emotion_name = %s",
                        (dim.activity_id, emotion),
                    )
                    emo_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO event_emotional_outputs (mapping_id, emotional_output_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (mapping_id, emo_id),
                )

    # ------------------------------------------------------------------
    # 7. Engagement snapshot
    # ------------------------------------------------------------------

    def _persist_engagement_snapshot(self, cur, event: EventSchema, event_id):
        if not event.engagement:
            return

        eng = event.engagement
        cur.execute(
            """
            INSERT INTO engagement_snapshots (
                event_id, going_count, interested_count, views_count,
                shares_count, comments_count, likes_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            (
                event_id,
                eng.going_count,
                eng.interested_count,
                eng.views_count,
                eng.shares_count,
                eng.comments_count,
                eng.likes_count,
            ),
        )

    # ------------------------------------------------------------------
    # 8. Ticket info
    # ------------------------------------------------------------------

    def _persist_ticket_info(self, cur, event: EventSchema, event_id):
        ti = event.ticket_info
        if not (ti.url or ti.is_sold_out or ti.ticket_count_available is not None):
            return

        cur.execute(
            """
            INSERT INTO ticket_info (
                event_id, url, is_sold_out,
                ticket_count_available, early_bird_deadline
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO UPDATE SET
                is_sold_out = EXCLUDED.is_sold_out,
                ticket_count_available = EXCLUDED.ticket_count_available,
                updated_at = NOW();
            """,
            (
                event_id,
                ti.url,
                ti.is_sold_out,
                ti.ticket_count_available,
                ti.early_bird_deadline,
            ),
        )

    # ------------------------------------------------------------------
    # 9. Media assets
    # ------------------------------------------------------------------

    def _persist_media_assets(self, cur, event: EventSchema, event_id):
        for asset in event.media_assets:
            cur.execute(
                """
                INSERT INTO media_assets (
                    event_id, type, url, title, description, width, height
                ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    event_id,
                    asset.type,
                    asset.url,
                    asset.title,
                    asset.description,
                    asset.width,
                    asset.height,
                ),
            )

    # ------------------------------------------------------------------
    # 10. Tags
    # ------------------------------------------------------------------

    def _persist_tags(self, cur, event: EventSchema, event_id):
        for tag_name in event.tags:
            cur.execute(
                """
                INSERT INTO tags (tag_name) VALUES (%s)
                ON CONFLICT (tag_name) DO NOTHING
                RETURNING tag_id;
                """,
                (tag_name,),
            )
            res = cur.fetchone()
            if res:
                tag_id = res[0]
            else:
                cur.execute(
                    "SELECT tag_id FROM tags WHERE tag_name = %s",
                    (tag_name,),
                )
                tag_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO event_tags (event_id, tag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (event_id, tag_id),
            )

    # ------------------------------------------------------------------
    # 11. Artists
    # ------------------------------------------------------------------

    def _persist_artists(self, cur, event: EventSchema, event_id):
        for artist in event.artists:
            cur.execute(
                """
                INSERT INTO artists (
                    name, soundcloud_url, spotify_url, instagram_url, genre
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING artist_id;
                """,
                (
                    artist.name,
                    artist.soundcloud_url,
                    artist.spotify_url,
                    artist.instagram_url,
                    artist.genre,
                ),
            )
            res = cur.fetchone()
            if res:
                artist_id = res[0]
            else:
                cur.execute(
                    "SELECT artist_id FROM artists WHERE name = %s",
                    (artist.name,),
                )
                artist_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO event_artists (event_id, artist_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (event_id, artist_id),
            )

    # ------------------------------------------------------------------
    # 12. Normalization errors
    # ------------------------------------------------------------------

    def _persist_normalization_errors(self, cur, event: EventSchema, event_id):
        for error_msg in event.normalization_errors:
            cur.execute(
                """
                INSERT INTO normalization_errors (
                    event_id, error_message
                ) VALUES (%s, %s);
                """,
                (event_id, error_msg),
            )
