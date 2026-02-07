"""
services.api.src.main

FastAPI entrypoint for the Event Intelligence Platform.

Responsibilities
----------------
• API initialization
• Health monitoring
• Taxonomy query endpoints
• PostgreSQL connectivity

Environment
-----------
Requires DATABASE_URL in SQLAlchemy format, e.g.:

postgresql://user:password@host:port/event_intelligence
"""

from __future__ import annotations

import os
from typing import Generator

import psycopg2
from fastapi import Depends, FastAPI, HTTPException
from psycopg2.extensions import connection as _connection
from pydantic import BaseModel
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# APP INITIALIZATION
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Event Intelligence API",
    version="1.0.0",
    description="API for querying the Human Experience Taxonomy.",
)


# ---------------------------------------------------------------------------
# DATABASE CONFIGURATION
# ---------------------------------------------------------------------------

def parse_database_url(database_url: str) -> dict:
    """
    Parse DATABASE_URL into psycopg2 connection parameters.

    Parameters
    ----------
    database_url : str
        SQLAlchemy-style database connection string.

    Returns
    -------
    dict
        psycopg2-compatible connection arguments.
    """
    parsed = urlparse(database_url)

    return {
        "host": parsed.hostname,
        "port": parsed.port,
        "dbname": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": parsed.password,
    }


def get_connection() -> _connection:
    """
    Create a new PostgreSQL database connection.

    Returns
    -------
    psycopg2.extensions.connection
        Active database connection.

    Raises
    ------
    RuntimeError
        If DATABASE_URL is missing.
    """
    database_url: str | None = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set."
        )

    conn_params = parse_database_url(database_url)

    return psycopg2.connect(**conn_params)


def get_db() -> Generator[_connection, None, None]:
    """
    FastAPI dependency that yields a database connection.

    Ensures proper connection cleanup after request lifecycle.

    Yields
    ------
    psycopg2.extensions.connection
        Active database connection.
    """
    conn = get_connection()

    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# RESPONSE MODELS
# ---------------------------------------------------------------------------

class Category(BaseModel):
    """
    Experience category response model.
    """

    category_id: str
    name: str
    description: str | None


# ---------------------------------------------------------------------------
# HEALTH ENDPOINT
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Monitoring"])
def health_check() -> dict[str, str]:
    """
    API health check endpoint.

    Returns
    -------
    dict
        Service status indicator.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# TAXONOMY ENDPOINTS
# ---------------------------------------------------------------------------

@app.get(
    "/categories",
    response_model=list[Category],
    tags=["Taxonomy"],
)
def list_categories(
    db: _connection = Depends(get_db),
) -> list[Category]:
    """
    Retrieve all experience categories.

    Parameters
    ----------
    db : psycopg2.extensions.connection
        Injected database connection.

    Returns
    -------
    list[Category]
        List of experience categories.

    Raises
    ------
    HTTPException
        If database query fails.
    """
    try:
        cur = db.cursor()

        cur.execute(
            """
            SELECT
                category_id,
                name,
                description
            FROM experience_categories
            ORDER BY name;
            """
        )

        rows = cur.fetchall()

        cur.close()

        return [
            Category(
                category_id=row[0],
                name=row[1],
                description=row[2],
            )
            for row in rows
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}",
        )
