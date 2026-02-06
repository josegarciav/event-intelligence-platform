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
