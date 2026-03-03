
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

All commands can be run from the repo root or from `infra/postgres/`.

### Start database

```bash
docker compose -f infra/postgres/docker-compose.yml up -d
```

### Stop database

```bash
docker compose -f infra/postgres/docker-compose.yml down
```

### Reset database (destructive)

Destroys the volume so all `init/` scripts re-run from scratch on next start:

```bash
docker compose -f infra/postgres/docker-compose.yml down -v
docker compose -f infra/postgres/docker-compose.yml up -d
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
docker compose -f infra/postgres/docker-compose.yml up -d
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
