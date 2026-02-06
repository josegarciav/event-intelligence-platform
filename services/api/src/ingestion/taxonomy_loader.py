"""
taxonomy_loader.py

ETL pipeline to load the Human Experience Taxonomy JSON
into Postgres relational tables.

Usage:
    python -m ingestion.taxonomy_loader
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# ENV LOADING
# ---------------------------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parents[2]

TAXONOMY_PATH: Path = (
    BASE_DIR / "src/assets/human_experience_taxonomy_master.json"
)


# ---------------------------------------------------------------------------
# DATABASE CONNECTION
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
    Create PostgreSQL connection using DATABASE_URL.

    Returns
    -------
    psycopg2.extensions.connection
        Active database connection.
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL not found in environment variables."
        )

    conn_params = parse_database_url(database_url)

    return psycopg2.connect(**conn_params)


# ---------------------------------------------------------------------------
# TAXONOMY LOADING
# ---------------------------------------------------------------------------

def load_taxonomy() -> dict:
    """
    Load taxonomy JSON file.

    Returns
    -------
    dict
        Parsed taxonomy structure.
    """
    if not TAXONOMY_PATH.exists():
        raise FileNotFoundError(
            f"Taxonomy file not found at: {TAXONOMY_PATH}"
        )

    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# INSERT FUNCTIONS
# ---------------------------------------------------------------------------

def insert_category(cur, category: dict, meta: dict) -> None:
    """
    Insert top-level experience category.

    Parameters
    ----------
    cur : psycopg2.cursor
        Active database cursor.
    category : dict
        Category payload.
    meta : dict
        Taxonomy metadata.
    """
    cur.execute(
        """
        INSERT INTO experience_categories
        (category_id, name, description, taxonomy_version, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (category_id) DO NOTHING;
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
    cur,
    sub: dict,
    category_id: str,
) -> None:
    """
    Insert experience subcategory.

    Parameters
    ----------
    cur : psycopg2.cursor
        Active database cursor.
    sub : dict
        Subcategory payload.
    category_id : str
        Parent category identifier.
    """
    cur.execute(
        """
        INSERT INTO experience_subcategories
        (subcategory_id, category_id, name)
        VALUES (%s, %s, %s)
        ON CONFLICT (subcategory_id) DO NOTHING;
        """,
        (
            sub["id"],
            category_id,
            sub["name"],
        ),
    )


def insert_activity(
    cur,
    activity: dict,
    subcategory_id: str,
) -> None:
    """
    Insert experience activity and attributes.

    Parameters
    ----------
    cur : psycopg2.cursor
        Active database cursor.
    activity : dict
        Activity payload.
    subcategory_id : str
        Parent subcategory identifier.
    """
    cur.execute(
        """
        INSERT INTO experience_activities (
            activity_id,
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (activity_id) DO NOTHING;
        """,
        (
            activity["activity_id"],
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


# ---------------------------------------------------------------------------
# ETL PIPELINE
# ---------------------------------------------------------------------------

def run_etl() -> None:
    """
    Execute taxonomy ingestion pipeline.

    Steps
    -----
    1. Load taxonomy JSON
    2. Connect to Postgres
    3. Insert categories
    4. Insert subcategories
    5. Insert activities
    6. Commit transaction
    """
    print("Loading taxonomy...")
    data = load_taxonomy()

    print("Connecting to database...")
    conn = get_connection()
    cur = conn.cursor()

    for category in data["categories"]:

        insert_category(cur, category, data)

        for sub in category["subcategories"]:

            insert_subcategory(
                cur,
                sub,
                category["category_id"],
            )

            for activity in sub["activities"]:

                insert_activity(
                    cur,
                    activity,
                    sub["id"],
                )

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Taxonomy successfully loaded.")


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_etl()
