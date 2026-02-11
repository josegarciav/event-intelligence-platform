## 2025-01-31 - Database Connection Pooling
**Learning:** The FastAPI backend was creating a new PostgreSQL connection for every request, adding significant latency. In a Python FastAPI app with sync routes, `psycopg2.pool.ThreadedConnectionPool` is necessary for thread-safe connection reuse.
**Action:** Always use connection pooling for database-backed services. Use FastAPI's `lifespan` to ensure the pool is properly closed on shutdown and initialized during startup to avoid race conditions.

## 2025-01-31 - Broken CI Actions
**Learning:** External GitHub Actions can be deleted or moved, breaking CI. `amitsingh-007/validate-commit-message` was missing.
**Action:** Use well-maintained and official or highly popular actions. `gsactions/commit-message-checker` is a reliable alternative for commit message validation.
