# Memory Service

Runnable project skeleton for the Higgsfield memory-service challenge.

This setup currently includes the application foundation, the Sprint 1 memory
schema and HTTP contract surface, Sprint 2 rule-based memory extraction, and
Sprint 3 fact evolution. Embeddings, LLM extraction, and hybrid recall will be
added in later iterations.

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
- `POST /turns` stores the raw turn and extracts basic structured memories.
- Basic rule-based extraction handles location moves, employment, pets, diet,
  and communication-style preferences.
- Every extracted memory gets `memory_evidence`.
- Repeated same key/value facts reinforce existing memory confidence and
  `confirmation_count`.
- Conflicting same-key facts supersede the old active memory instead of creating
  two current facts.
- Partial unique indexes enforce one active memory per user/key or session/key
  slot.
- `POST /turns` takes a scoped Postgres advisory lock per memory slot before
  resolving facts.
- Alembic migrations run automatically during FastAPI startup before the service
  begins serving requests.
- `/recall` and `/search` intentionally return empty stub responses until the retrieval sprint.
- Embeddings, LLM extraction, and hybrid recall are deferred.

## Tests

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
