# Memory Service

Runnable project skeleton for the Higgsfield memory-service challenge.

This setup currently includes the application foundation, the Sprint 1 memory
schema and HTTP contract surface, Sprint 2 rule-based memory extraction, and
Sprint 3 fact evolution. Sprint 4 adds optional OpenAI LLM extraction on top of
the rule-based fallback. Sprint 5 adds memory embeddings and hybrid recall.
Sprint 6 wires `/search` to the same retrieval layer and adds a recall quality
fixture.

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
tests/fixtures/         Recall quality fixture data
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
- `/search` uses the same hybrid retrieval path as `/recall`, but returns
  structured ranked results instead of prompt-ready prose.
- `tests/fixtures/recall_quality.json` covers employment, location, pet,
  preference, and opinion evolution probes.

## Architecture Notes

- `turns` is the raw conversation archive.
- `memories` stores normalized facts, preferences, opinions, and events.
- `memory_evidence` stores the quote and turn that justify each memory.
- Extraction is layered: rule-based extraction handles obvious facts locally;
  optional LLM extraction adds coverage for nuanced memories.
- Fact evolution keeps history: a conflicting same-key memory supersedes the old
  active memory instead of deleting it.
- Recall is hybrid: pgvector handles semantic similarity, Postgres FTS handles
  exact words/entities, then RRF-style scoring merges both lists.

## Originality And Tradeoffs

This service intentionally avoids copying another memory provider's API shape or
pipeline. The core design is evidence-first: every memory points back to source
quotes, reinforcement raises confidence through repeated evidence, and database
constraints protect active memory slots.

Current tradeoffs:

- Rule-based extraction is deliberately narrow and deterministic.
- LLM extraction is optional so local development and tests do not require API
  access.
- `/recall` has hybrid retrieval but not LLM reranking yet.
- Embeddings are created only when `OPENAI_API_KEY` is configured.

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
