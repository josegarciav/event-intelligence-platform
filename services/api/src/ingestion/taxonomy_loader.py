"""
taxonomy_loader.py

Loads Human Experience Taxonomy into relational ontology tables.

Tables populated:

• primary_categories
• subcategories
• activities_metadata
• subcategory_values
• activity_emotional_outputs
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# ENV
# ---------------------------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

TAXONOMY_PATH = BASE_DIR / "src/assets/human_experience_taxonomy_master.json"


# ---------------------------------------------------------------------------
# DB CONNECTION
# ---------------------------------------------------------------------------


def parse_database_url(database_url: str) -> dict:
    """
    Parse SQLAlchemy-style DATABASE_URL into psycopg2 parameters.

    Parameters
    ----------
    database_url : str
        Database connection string.

    Returns
    -------
    dict
        psycopg2 connection configuration.
    """
    parsed = urlparse(database_url)

    return {
        "host": parsed.hostname,
        "port": parsed.port,
        "dbname": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": parsed.password,
    }


def get_connection() -> psycopg2.extensions.connection:
    """
    Establish a new database connection using DATABASE_URL.
    """

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL not set")

    return psycopg2.connect(**parse_database_url(database_url))


# ---------------------------------------------------------------------------
# LOAD JSON
# ---------------------------------------------------------------------------


def load_taxonomy() -> dict:
    """Load taxonomy JSON file."""
    if not TAXONOMY_PATH.exists():
        raise FileNotFoundError(TAXONOMY_PATH)

    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# INSERT FUNCTIONS
# ---------------------------------------------------------------------------


def insert_primary_category(
    cur: psycopg2.extensions.cursor, category: dict, meta: dict
) -> None:
    """Insert top-level experience category."""
    cur.execute(
        """
        INSERT INTO primary_categories
        (primary_category_id, name, description, taxonomy_version, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (primary_category_id) DO NOTHING;
        """,
        (
            category["category_id"],
            category["category"],
            category.get("description"),
            meta.get("version"),
            meta.get("created_at"),
        ),
    )


def insert_subcategory(
    cur: psycopg2.extensions.cursor, sub: dict, category_id: str
) -> None:
    """Insert subcategory metadata."""
    cur.execute(
        """
        INSERT INTO subcategories
        (subcategory_id, primary_category_id, name)
        VALUES (%s, %s, %s)
        ON CONFLICT (subcategory_id) DO NOTHING;
        """,
        (
            sub["id"],
            category_id,
            sub["name"],
        ),
    )


def insert_activity_metadata(
    cur: psycopg2.extensions.cursor,
    activity: dict,
    category_id: str,
    subcategory_id: str,
) -> None:
    """Insert activity metadata."""
    cur.execute(
        """
        INSERT INTO activities_metadata (
            activity_id,
            primary_category_id,
            subcategory_id,
            name,
            energy_level,
            social_intensity,
            cognitive_load,
            physical_involvement,
            cost_level,
            time_scale,
            environment,
            risk_level,
            age_accessibility,
            repeatability,
            notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (activity_id) DO NOTHING;
        """,
        (
            activity["activity_id"],
            category_id,
            subcategory_id,
            activity["name"],
            activity.get("energy_level"),
            activity.get("social_intensity"),
            activity.get("cognitive_load"),
            activity.get("physical_involvement"),
            activity.get("cost_level"),
            activity.get("time_scale"),
            activity.get("environment"),
            activity.get("risk_level"),
            activity.get("age_accessibility"),
            activity.get("repeatability"),
            activity.get("notes"),
        ),
    )


def insert_subcategory_value(
    cur: psycopg2.extensions.cursor, subcategory_id: str, value: str
) -> None:
    """Insert subcategory psychological value."""
    cur.execute(
        """
        INSERT INTO subcategory_values (
            subcategory_id,
            value_name
        )
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING;
        """,
        (
            subcategory_id,
            value,
        ),
    )


def insert_activity_emotion(
    cur: psycopg2.extensions.cursor, activity_id: str, emotion: str
) -> None:
    """Insert emotional output associated with an activity."""
    cur.execute(
        """
        INSERT INTO activity_emotional_outputs (
            activity_id,
            emotion_name
        )
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING;
        """,
        (
            activity_id,
            emotion,
        ),
    )


# ---------------------------------------------------------------------------
# ETL
# ---------------------------------------------------------------------------


def run_etl():

    print("Loading taxonomy...")
    data = load_taxonomy()

    print("Connecting to database...")
    conn = get_connection()
    cur = conn.cursor()

    for category in data["categories"]:

        insert_primary_category(cur, category, data)

        for sub in category["subcategories"]:

            insert_subcategory(
                cur,
                sub,
                category["category_id"],
            )

            # ---------------------------
            # Subcategory values
            # ---------------------------

            for value in sub.get("values", []):

                insert_subcategory_value(
                    cur,
                    sub["id"],
                    value,
                )

            # ---------------------------
            # Activities
            # ---------------------------

            for activity in sub["activities"]:

                insert_activity_metadata(
                    cur,
                    activity,
                    category["category_id"],
                    sub["id"],
                )

                # Emotional outputs

                for emotion in activity.get("emotional_output", []):

                    insert_activity_emotion(
                        cur,
                        activity["activity_id"],
                        emotion,
                    )

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Full taxonomy ontology loaded.")


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_etl()
