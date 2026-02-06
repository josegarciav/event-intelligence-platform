# API entrypoint for the Event Intelligence Platform
"""
main.py

API entrypoint for the Event Intelligence Platform.
Handles routing, health checks, and taxonomy queries.
"""

from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2


app = FastAPI(
    title="Event Intelligence API",
    version="1.0.0",
)


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "experience_db",
    "user": "experience_user",
    "password": "experience_pass",
}


def get_connection():
    """Create database connection."""
    return psycopg2.connect(**DB_CONFIG)


@app.get("/health")
def health_check():
    """API health check endpoint."""
    return {"status": "ok"}


@app.get("/categories")
def list_categories():
    """Return all experience categories."""

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT category_id, name, description
        FROM experience_categories;
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "category_id": r[0],
            "name": r[1],
            "description": r[2],
        }
        for r in rows
    ]
