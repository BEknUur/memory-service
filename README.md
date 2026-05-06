# Memory Service

Runnable project skeleton for the Higgsfield memory-service challenge.

This setup currently includes the application foundation plus the Sprint 1
memory schema and HTTP contract surface. Memory extraction, fact evolution,
embeddings, and hybrid recall will be added in later iterations.

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
  api/routes/          Contract endpoints
  config.py             Environment settings
  db/                   SQLAlchemy async engine and models
  main.py               FastAPI app factory
tests/                  Setup-level tests
migrations/             Alembic migrations
```

## Current Status

- FastAPI app skeleton is present.
- Postgres is the backing store.
- pgvector is enabled by the first Alembic migration.
- Core tables are defined: `turns`, `memories`, and `memory_evidence`.
- Contract endpoints exist for turns, recall, search, users, and sessions.
- `POST /turns` stores the raw turn.
- `/recall` and `/search` intentionally return empty stub responses until the retrieval sprint.
- Extraction, reinforcement, supersession, embeddings, and hybrid recall are deferred.

## Tests

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
