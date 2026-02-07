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
docker exec -it experience_postgres psql -U experience_user -l
```

### List tables

```bash
docker exec -it experience_postgres psql -U experience_user -d event_intelligence -c "\dt"
```

Expect:
```text
experience_categories
experience_subcategories
experience_activities
```


### Load taxonomy latest version

When there is a new version of the taxonomy:

```bash
# Start DB
docker compose up -d
# Export env (if running locally)
export $(cat services/api/.env | xargs)
# Run ETL
uv run python -m services.api.src.ingestion.taxonomy_loader
# Expect: ✅ Taxonomy successfully loaded.
```
