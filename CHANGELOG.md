# Changelog

## v0 - Project skeleton setup

**What changed:** Added FastAPI, Postgres/pgvector, Alembic, Docker Compose,
environment settings, package layout, and setup-level tests.

**Why:** The project needs a runnable foundation before implementing memory
extraction, recall, search, and fact evolution.

**Result:** The service can boot, expose `/health`, and verify database
connectivity.
