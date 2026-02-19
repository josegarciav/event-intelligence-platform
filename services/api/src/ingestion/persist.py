# Persistence layer for ingested data
"""
Persistence Layer for Event Ingestion.

Handles the atomic upsert of EventSchema objects into the relational
PostgreSQL schema, managing foreign key relationships and transactions.
"""

import logging
from datetime import date

from psycopg2.extras import execute_values

from src.schemas.event import EventSchema
from src.schemas.taxonomy import primary_category_to_id

logger = logging.getLogger(__name__)


class EventDataWriter:
    """
    Handles persisting normalized EventSchema objects to the PostgreSQL database.

    Implements the 'Data Mapper' pattern to bridge the gap between Python
    objects and the relational schema.
    """

    def __init__(self, db_connection) -> None:
        """Initialize with an active psycopg2 connection."""
        self.conn = db_connection
        # Metadata cache for foreign key verification (issue #8)
        self._valid_primary_categories = set()
        self._valid_subcategories = set()
        self._valid_activities = set()
        self._load_metadata_cache()

    def _load_metadata_cache(self) -> None:
        """Load valid IDs from taxonomy tables into memory for verification."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT primary_category_id FROM primary_categories")
                self._valid_primary_categories = {row[0] for row in cur.fetchall()}

                cur.execute("SELECT subcategory_id FROM subcategories")
                self._valid_subcategories = {row[0] for row in cur.fetchall()}

                cur.execute("SELECT activity_id FROM activities_metadata")
                self._valid_activities = {str(row[0]) for row in cur.fetchall()}
        except Exception as e:
            logger.error(f"Failed to load metadata cache: {e}")

    def persist_batch(self, events: list[EventSchema]) -> int:
        """
        Persist a list of events to the database.

        Each event is persisted in its own transaction. If one event fails,
        it is rolled back, but previously successful events remain committed
        and the process continues for the rest of the batch.

        Returns:
            int: Number of successfully persisted events.
        """
        success_count = 0
        for event in events:
            try:
                self._persist_single_event(event)
                self.conn.commit()
                success_count += 1
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Failed to persist event '{event.title}': {e}")
                continue

        return success_count

    def _persist_single_event(self, event: EventSchema) -> None:
        """Handle the atomic insertion of a single event and its related child records."""
        with self.conn.cursor() as cur:
            # Date guard: skip updates for past events that already exist in DB
            cur.execute("SELECT 1 FROM events WHERE event_id = %s", (event.event_id,))
            existing = cur.fetchone()
            if existing:
                event_date = (
                    event.start_datetime.date() if event.start_datetime else None
                )
                if event_date and event_date < date.today():
                    logger.debug(
                        f"Skipping update for past event '{event.title}' ({event_date})"
                    )
                    return

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
            ON CONFLICT (city, country_code, (COALESCE(venue_name, '')))
            DO UPDATE SET
                street_address = COALESCE(EXCLUDED.street_address, locations.street_address),
                state_or_region = COALESCE(EXCLUDED.state_or_region, locations.state_or_region),
                postal_code = COALESCE(EXCLUDED.postal_code, locations.postal_code),
                latitude = COALESCE(EXCLUDED.latitude, locations.latitude),
                longitude = COALESCE(EXCLUDED.longitude, locations.longitude),
                timezone = COALESCE(EXCLUDED.timezone, locations.timezone)
            WHERE
                locations.street_address IS DISTINCT FROM COALESCE(EXCLUDED.street_address, locations.street_address)
                OR locations.state_or_region IS DISTINCT FROM COALESCE(EXCLUDED.state_or_region, locations.state_or_region)
                OR locations.postal_code IS DISTINCT FROM COALESCE(EXCLUDED.postal_code, locations.postal_code)
                OR locations.latitude IS DISTINCT FROM COALESCE(EXCLUDED.latitude, locations.latitude)
                OR locations.longitude IS DISTINCT FROM COALESCE(EXCLUDED.longitude, locations.longitude)
                OR locations.timezone IS DISTINCT FROM COALESCE(EXCLUDED.timezone, locations.timezone)
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

        # Fallback lookup when no changes (WHERE was false) or on conflict
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
                compressed_html, ingestion_timestamp, source_updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_name, source_event_id)
            DO UPDATE SET
                compressed_html = COALESCE(EXCLUDED.compressed_html, sources.compressed_html),
                source_url = COALESCE(EXCLUDED.source_url, sources.source_url),
                source_updated_at = COALESCE(EXCLUDED.source_updated_at, sources.source_updated_at),
                ingestion_timestamp = EXCLUDED.ingestion_timestamp
            WHERE
                sources.compressed_html IS DISTINCT FROM COALESCE(EXCLUDED.compressed_html, sources.compressed_html)
                OR sources.source_url IS DISTINCT FROM COALESCE(EXCLUDED.source_url, sources.source_url)
                OR sources.source_updated_at IS DISTINCT FROM COALESCE(EXCLUDED.source_updated_at, sources.source_updated_at)
                OR sources.ingestion_timestamp IS DISTINCT FROM EXCLUDED.ingestion_timestamp
            RETURNING source_id;
            """,
            (
                src.source_name,
                src.source_event_id,
                src.source_url,
                src.compressed_html,
                src.ingestion_timestamp,
                src.source_updated_at,
            ),
        )
        res = cur.fetchone()
        if res:
            return res[0]

        # Fallback lookup when no changes
        cur.execute(
            """
            SELECT source_id FROM sources
            WHERE source_name = %s AND source_event_id = %s
            LIMIT 1;
            """,
            (src.source_name, src.source_event_id),
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
                email = COALESCE(EXCLUDED.email, organizers.email),
                phone = COALESCE(EXCLUDED.phone, organizers.phone),
                image_url = COALESCE(EXCLUDED.image_url, organizers.image_url),
                follower_count = COALESCE(EXCLUDED.follower_count, organizers.follower_count),
                verified = EXCLUDED.verified,
                updated_at = NOW()
            WHERE
                organizers.url IS DISTINCT FROM COALESCE(EXCLUDED.url, organizers.url)
                OR organizers.email IS DISTINCT FROM COALESCE(EXCLUDED.email, organizers.email)
                OR organizers.phone IS DISTINCT FROM COALESCE(EXCLUDED.phone, organizers.phone)
                OR organizers.image_url IS DISTINCT FROM COALESCE(EXCLUDED.image_url, organizers.image_url)
                OR organizers.follower_count IS DISTINCT FROM COALESCE(EXCLUDED.follower_count, organizers.follower_count)
                OR organizers.verified IS DISTINCT FROM EXCLUDED.verified
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
        res = cur.fetchone()
        if res:
            return res[0]

        # Fallback lookup when no changes
        cur.execute(
            "SELECT organizer_id FROM organizers WHERE name = %s LIMIT 1;",
            (org.name,),
        )
        return cur.fetchone()[0]

    # ------------------------------------------------------------------
    # 4. Event (central spine)
    # ------------------------------------------------------------------

    def _persist_event(
        self, cur, event: EventSchema, location_id, source_id, organizer_id
    ):
        # Convert primary category value to taxonomy ID
        primary_cat_value = (
            event.taxonomy_dimension.primary_category
            if event.taxonomy_dimension
            else None
        )
        primary_cat_id = (
            primary_category_to_id(primary_cat_value) if primary_cat_value else None
        )

        # Issue #8: Verify primary_category_id exists
        if primary_cat_id and primary_cat_id not in self._valid_primary_categories:
            logger.warning(
                f"Event '{event.title}': primary_category_id '{primary_cat_id}' not found in metadata. Setting to NULL."
            )
            primary_cat_id = None

        cur.execute(
            """
            INSERT INTO events (
                event_id, title, description, primary_category_id,
                event_type, event_format, capacity, age_restriction,
                start_datetime, end_datetime, duration_minutes,
                is_all_day, is_recurring, recurrence_pattern,
                location_id, organizer_id, source_id,
                data_quality_score, updated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, NOW()
            )
            ON CONFLICT (event_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                primary_category_id = EXCLUDED.primary_category_id,
                event_type = EXCLUDED.event_type,
                event_format = EXCLUDED.event_format,
                capacity = EXCLUDED.capacity,
                age_restriction = EXCLUDED.age_restriction,
                start_datetime = EXCLUDED.start_datetime,
                end_datetime = EXCLUDED.end_datetime,
                duration_minutes = EXCLUDED.duration_minutes,
                is_all_day = EXCLUDED.is_all_day,
                is_recurring = EXCLUDED.is_recurring,
                recurrence_pattern = EXCLUDED.recurrence_pattern,
                location_id = EXCLUDED.location_id,
                organizer_id = EXCLUDED.organizer_id,
                source_id = EXCLUDED.source_id,
                data_quality_score = EXCLUDED.data_quality_score,
                updated_at = NOW()
            WHERE
                events.title IS DISTINCT FROM EXCLUDED.title
                OR events.description IS DISTINCT FROM EXCLUDED.description
                OR events.primary_category_id IS DISTINCT FROM EXCLUDED.primary_category_id
                OR events.event_type IS DISTINCT FROM EXCLUDED.event_type
                OR events.event_format IS DISTINCT FROM EXCLUDED.event_format
                OR events.capacity IS DISTINCT FROM EXCLUDED.capacity
                OR events.age_restriction IS DISTINCT FROM EXCLUDED.age_restriction
                OR events.start_datetime IS DISTINCT FROM EXCLUDED.start_datetime
                OR events.end_datetime IS DISTINCT FROM EXCLUDED.end_datetime
                OR events.duration_minutes IS DISTINCT FROM EXCLUDED.duration_minutes
                OR events.location_id IS DISTINCT FROM EXCLUDED.location_id
                OR events.organizer_id IS DISTINCT FROM EXCLUDED.organizer_id
                OR events.source_id IS DISTINCT FROM EXCLUDED.source_id
                OR events.data_quality_score IS DISTINCT FROM EXCLUDED.data_quality_score
            RETURNING event_id;
            """,
            (
                event.event_id,
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

        # No changes — event_id is deterministic, return directly
        return event.event_id

    # ------------------------------------------------------------------
    # 5. Price snapshot
    # ------------------------------------------------------------------

    def _persist_price_snapshot(self, cur, event: EventSchema, event_id):
        p = event.price
        cur.execute(
            """
            INSERT INTO price_snapshots (
                event_id, currency_code, is_free,
                minimum_price, maximum_price,
                early_bird_price, standard_price, vip_price,
                price_raw_text
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                event_id,
                p.currency_code,
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
        # 1. Cleanup existing mappings (cascades to event_emotional_outputs)
        cur.execute(
            "DELETE FROM event_taxonomy_mappings WHERE event_id = %s", (event_id,)
        )

        if not event.taxonomy_dimension:
            return

        # 2. Filter and prepare mapping data
        valid_dims_with_act = []
        mapping_rows = []
        for dim in [event.taxonomy_dimension]:
            sub_id = dim.subcategory
            if sub_id and sub_id not in self._valid_subcategories:
                logger.warning(
                    f"Event '{event.title}': subcategory_id '{sub_id}' "
                    "not found in metadata. Skipping this dimension mapping."
                )
                continue

            act_id = dim.activity_id
            if act_id and str(act_id) not in self._valid_activities:
                logger.warning(
                    f"Event '{event.title}': activity_id '{act_id}' not found in metadata. Setting to NULL."
                )
                act_id = None

            valid_dims_with_act.append((dim, act_id))
            mapping_rows.append(
                (
                    event_id,
                    sub_id,
                    act_id,
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
                    None,  # unconstrained_primary_category (future LLM)
                    None,  # unconstrained_subcategory (future LLM)
                    None,  # unconstrained_activity (future LLM)
                )
            )

        if not mapping_rows:
            return

        # 3. Bulk insert mappings
        execute_values(
            cur,
            """
            INSERT INTO event_taxonomy_mappings (
                event_id, subcategory_id, activity_id, activity_name,
                energy_level, social_intensity, cognitive_load,
                physical_involvement, cost_level, time_scale,
                environment, risk_level, age_accessibility, repeatability,
                unconstrained_primary_category, unconstrained_subcategory,
                unconstrained_activity
            ) VALUES %s
            RETURNING mapping_id;
            """,
            mapping_rows,
        )
        mapping_ids = [row[0] for row in cur.fetchall()]

        # 4. Handle Emotional Outputs
        # Collect all unique (activity_id, emotion) pairs to upsert into metadata
        emotion_metadata_pairs = set()
        for dim, act_id in valid_dims_with_act:
            if act_id:
                for emotion in dim.emotional_output:
                    emotion_metadata_pairs.add((act_id, emotion))

        if not emotion_metadata_pairs:
            return

        # Bulk upsert emotional outputs metadata
        emotion_metadata_rows = list(emotion_metadata_pairs)
        execute_values(
            cur,
            """
            INSERT INTO activity_emotional_outputs (activity_id, emotion_name)
            VALUES %s
            ON CONFLICT (activity_id, emotion_name) DO UPDATE SET emotion_name = EXCLUDED.emotion_name
            RETURNING emotional_output_id, activity_id, emotion_name;
            """,
            emotion_metadata_rows,
        )
        # Create map of (str(activity_id), emotion_name) -> emotional_output_id
        emo_id_map = {(str(row[1]), row[2]): row[0] for row in cur.fetchall()}

        # 5. Bulk insert event_emotional_outputs associations
        event_emo_rows = []
        for i, (dim, act_id) in enumerate(valid_dims_with_act):
            if act_id:
                mapping_id = mapping_ids[i]
                for emotion in dim.emotional_output:
                    emo_id = emo_id_map.get((str(act_id), emotion))
                    if emo_id:
                        event_emo_rows.append((mapping_id, emo_id))

        if event_emo_rows:
            execute_values(
                cur,
                """
                INSERT INTO event_emotional_outputs (mapping_id, emotional_output_id)
                VALUES %s ON CONFLICT DO NOTHING;
                """,
                event_emo_rows,
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
                url = EXCLUDED.url,
                is_sold_out = EXCLUDED.is_sold_out,
                ticket_count_available = EXCLUDED.ticket_count_available,
                updated_at = NOW()
            WHERE
                ticket_info.url IS DISTINCT FROM EXCLUDED.url
                OR ticket_info.is_sold_out IS DISTINCT FROM EXCLUDED.is_sold_out
                OR ticket_info.ticket_count_available IS DISTINCT FROM EXCLUDED.ticket_count_available;
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
        # 1. Cleanup existing records
        cur.execute("DELETE FROM media_assets WHERE event_id = %s", (event_id,))

        if not event.media_assets:
            return

        # 2. Bulk insert
        asset_data = [
            (event_id, a.type, a.url, a.title, a.description, a.width, a.height)
            for a in event.media_assets
        ]
        execute_values(
            cur,
            """
            INSERT INTO media_assets (
                event_id, type, url, title, description, width, height
            ) VALUES %s;
            """,
            asset_data,
        )

    # ------------------------------------------------------------------
    # 10. Tags
    # ------------------------------------------------------------------

    def _persist_tags(self, cur, event: EventSchema, event_id):
        # 1. Cleanup existing associations
        cur.execute("DELETE FROM event_tags WHERE event_id = %s", (event_id,))

        if not event.tags:
            return

        # 2. Bulk upsert tags to get IDs
        unique_tags = list(set(event.tags))
        tag_data = [(t,) for t in unique_tags]

        # We use DO UPDATE SET tag_name = EXCLUDED.tag_name to ensure RETURNING tag_id
        # works for both new and existing records.
        execute_values(
            cur,
            """
            INSERT INTO tags (tag_name) VALUES %s
            ON CONFLICT (tag_name) DO UPDATE SET tag_name = EXCLUDED.tag_name
            RETURNING tag_id;
            """,
            tag_data,
        )
        tag_ids = [row[0] for row in cur.fetchall()]

        # 3. Bulk insert event_tags relationships
        rel_data = [(event_id, tid) for tid in tag_ids]
        execute_values(
            cur,
            "INSERT INTO event_tags (event_id, tag_id) VALUES %s ON CONFLICT DO NOTHING;",
            rel_data,
        )

    # ------------------------------------------------------------------
    # 11. Artists
    # ------------------------------------------------------------------

    def _persist_artists(self, cur, event: EventSchema, event_id):
        # 1. Cleanup existing associations
        cur.execute("DELETE FROM event_artists WHERE event_id = %s", (event_id,))

        if not event.artists:
            return

        # 2. Bulk upsert artists to get IDs
        seen_names = set()
        unique_artists = []
        for a in event.artists:
            if a.name not in seen_names:
                unique_artists.append(a)
                seen_names.add(a.name)

        artist_data = [
            (a.name, a.soundcloud_url, a.spotify_url, a.instagram_url, a.genre)
            for a in unique_artists
        ]

        execute_values(
            cur,
            """
            INSERT INTO artists (name, soundcloud_url, spotify_url, instagram_url, genre)
            VALUES %s
            ON CONFLICT (name) DO UPDATE SET
                soundcloud_url = COALESCE(EXCLUDED.soundcloud_url, artists.soundcloud_url),
                spotify_url = COALESCE(EXCLUDED.spotify_url, artists.spotify_url),
                instagram_url = COALESCE(EXCLUDED.instagram_url, artists.instagram_url),
                genre = COALESCE(EXCLUDED.genre, artists.genre)
            RETURNING artist_id;
            """,
            artist_data,
        )
        artist_ids = [row[0] for row in cur.fetchall()]

        # 3. Bulk insert event_artists relationships
        rel_data = [(event_id, aid) for aid in artist_ids]
        execute_values(
            cur,
            "INSERT INTO event_artists (event_id, artist_id) VALUES %s ON CONFLICT DO NOTHING;",
            rel_data,
        )

    # ------------------------------------------------------------------
    # 12. Normalization errors
    # ------------------------------------------------------------------

    def _persist_normalization_errors(self, cur, event: EventSchema, event_id):
        # 1. Cleanup existing records
        cur.execute("DELETE FROM normalization_errors WHERE event_id = %s", (event_id,))

        if not event.normalization_errors:
            return

        # 2. Bulk insert
        error_data = [
            (event_id, err.severity, err.message) for err in event.normalization_errors
        ]
        execute_values(
            cur,
            "INSERT INTO normalization_errors (event_id, severity, error_message) VALUES %s;",
            error_data,
        )
