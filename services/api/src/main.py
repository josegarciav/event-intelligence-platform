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

import logging
from collections.abc import Generator
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.pool
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extensions import connection as _connection
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from src.configs.settings import get_settings

logger = logging.getLogger(__name__)

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
        logger.exception("Failed to initialize database pool: %s", e)

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
# RATE LIMITING
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# CORS MIDDLEWARE
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# SECURITY HEADERS MIDDLEWARE
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that injects security-related HTTP response headers on every request."""

    async def dispatch(self, request: Request, call_next):
        """Add security headers to the response and pass through to the next handler."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)


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
@limiter.limit("60/minute")
def list_categories(
    request: Request,
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

        cur.execute("""
            SELECT
                primary_category_id,
                name,
                description
            FROM primary_categories
            ORDER BY name;
            """)

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
        logger.exception("Database query failed: %s", e)
        raise HTTPException(status_code=500, detail="An internal error occurred.")
