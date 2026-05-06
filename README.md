# Memory Service

Runnable project skeleton for the Higgsfield memory-service challenge.

This setup currently includes the application foundation, the Sprint 1 memory
schema and HTTP contract surface, Sprint 2 rule-based memory extraction, and
Sprint 3 fact evolution. Sprint 4 adds optional OpenAI LLM extraction on top of
the rule-based fallback. Sprint 5 adds memory embeddings and hybrid recall.

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
- Optional LLM extraction uses OpenAI Responses API structured outputs when
  `OPENAI_API_KEY` is configured.
- If no OpenAI key is configured or the LLM returns malformed output, the
  service continues with rule-based extraction.
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
- New or reinforced memories get embeddings when `OPENAI_API_KEY` is configured.
- `/recall` uses pgvector cosine search plus Postgres FTS, merges rankings with
  RRF-style scoring, applies confidence/session boosts, and returns prompt-ready
  context with citations.
- `/search` is still a structured-result stub until the next sprint.

## LLM Configuration

```env
OPENAI_API_KEY=
OPENAI_EXTRACT_MODEL=gpt-5-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
```

`gpt-5-mini` is the default extraction model because this sprint uses a
well-defined structured JSON task. The extractor asks for strict schema output
and converts valid results into the same internal memory candidates as the
rule-based extractor.

`text-embedding-3-small` is the default embedding model. If no OpenAI key is
configured, ingestion and recall still work through rule-based extraction and
Postgres FTS.

## Tests

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
