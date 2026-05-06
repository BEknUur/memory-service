# Memory Service

Runnable project skeleton for the Higgsfield memory-service challenge.

This setup intentionally includes only the application foundation: FastAPI,
Postgres with pgvector, environment configuration, Alembic migrations, Docker
Compose, and a `/health` endpoint. Memory extraction, recall, search, and fact
evolution will be added in later iterations.

## Run

```bash
cp .env.example .env
docker compose up --build
```

Then check:

```bash
curl http://localhost:8080/health
```

Expected healthy response:

```json
{"status":"ok","database":"ok"}
```

## Project Structure

```text
src/memory_service/
  api/routes/health.py  FastAPI health endpoint
  config.py             Environment settings
  db/                   SQLAlchemy async engine and Alembic metadata
  main.py               FastAPI app factory
tests/                  Setup-level tests
migrations/             Alembic migrations
```

## Current Status

- FastAPI app skeleton is present.
- Postgres is the backing store.
- pgvector is enabled by the first Alembic migration.
- Only `GET /health` is implemented for now.
- Contract endpoints for memory behavior are intentionally deferred.

## Tests

```bash
pip install -e ".[dev]"
pytest
ruff check . 
```
## Current situations
Then i will do so you can use the docker for testing but now it's ok
