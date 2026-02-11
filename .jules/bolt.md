## 2025-01-31 - Database Connection Pooling
**Learning:** The FastAPI backend was creating a new PostgreSQL connection for every request, adding significant latency. In a Python FastAPI app with sync routes, `psycopg2.pool.ThreadedConnectionPool` is necessary for thread-safe connection reuse.
**Action:** Always use connection pooling for database-backed services. Use FastAPI's `lifespan` to ensure the pool is properly closed on shutdown.
