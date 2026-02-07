# Postgres Infrastructure

Local PostgreSQL instance for the Event Intelligence Platform.

## Purpose

Provides:

- Event taxonomy storage
- Artist / venue relational mapping
- Enrichment output persistence

Initialized automatically via SQL scripts in `/init`.

---

## Usage

### Start database

```bash
docker compose up -d
```

### Stop database

```bash
docker compose down
```

### Reset database (destructive)

```bash
docker compose down -v
docker compose up -d
```


### List DBs

```bash
docker exec -it experience_postgres psql -U experience -l
```

### List tables

```bash
docker exec -it experience_postgres psql -U experience -d event_intelligence -c "\dt"
```


### Load taxonomy latest version

When there is a new version of the taxonomy:

```bash
# Start DB
docker compose up -d
# Export env (if running locally)
export $(grep -v '^#' services/api/.env | xargs)
# Run ETL
uv run python -m services.api.src.ingestion.taxonomy_loader
# Expect: ✅ Taxonomy successfully loaded.
```


Using the Terminal (pSQL):

```bash
psql -h localhost -p 5433 -U experience -d event_intelligence
```
