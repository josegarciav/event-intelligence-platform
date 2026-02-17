"""
src.main.

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

from collections.abc import Generator
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.pool
from fastapi import Depends, FastAPI, HTTPException
from psycopg2.extensions import connection as _connection
from pydantic import BaseModel

from src.configs.settings import get_settings

# ---------------------------------------------------------------------------
# GLOBAL SETTINGS
# ---------------------------------------------------------------------------

settings = get_settings()

# ---------------------------------------------------------------------------
# APP INITIALIZATION
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown events."""
    # Initialize the database connection pool on startup
    try:
        get_pool()
    except Exception as e:
        # Log error or handle as needed; for now, we let it fail startup if DB is required
        print(f"Failed to initialize database pool: {e}")

    yield

    # Shutdown: Close all connections in the pool
    global _POOL
    if _POOL is not None:
        _POOL.closeall()


app = FastAPI(
    title="Event Intelligence API",
    version="1.0.0",
    description="API for querying the Human Experience Taxonomy.",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# DATABASE CONFIGURATION
# ---------------------------------------------------------------------------


# Global connection pool instance
_POOL: psycopg2.pool.ThreadedConnectionPool | None = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """
    Get or initialize the database connection pool.

    Returns
    -------
    psycopg2.pool.ThreadedConnectionPool
        The active connection pool.
    """
    global _POOL
    if _POOL is None:
        conn_params = settings.get_psycopg2_params()

        # Using ThreadedConnectionPool for thread-safety in FastAPI sync routes
        _POOL = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            **conn_params,
        )
    return _POOL


def get_db() -> Generator[_connection, None, None]:
    """
    Yield a database connection from the pool.

    Ensures the connection is returned to the pool after the request lifecycle.

    Yields
    ------
    psycopg2.extensions.connection
        Active database connection.
    """
    pool = get_pool()
    conn = pool.getconn()

    try:
        yield conn
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# RESPONSE MODELS
# ---------------------------------------------------------------------------


class Category(BaseModel):
    """Experience category response model."""

    primary_category_id: str
    name: str
    description: str | None


# ---------------------------------------------------------------------------
# HEALTH ENDPOINT
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Monitoring"])
def health_check() -> dict[str, str]:
    """
    Check API health.

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
                primary_category_id,
                name,
                description
            FROM primary_categories
            ORDER BY name;
            """
        )

        rows = cur.fetchall()

        cur.close()

        return [
            Category(
                primary_category_id=row[0],
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
