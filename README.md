# Memory Service

This is a service which handles the memeory for ai agents 
like injests conversations,stores raw data,also extracts 
structured memeories and so on

Actually there are main six sprints where I did the core work. In the first
sprint I focused on the app foundation, schema, and HTTP contract surface.
Sprint 2 adds rule-based memory extraction, and Sprint 3 adds fact evolution.
Sprint 4 adds optional OpenAI LLM extraction on top of the rule-based fallback.
Sprint 5 adds memory embeddings and hybrid recall. Sprint 6 wires `/search` to
the same retrieval layer and adds a recall quality fixture. The latest iteration
adds canonical memory slots and direct superseded history in recall context.

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
{ "status": "ok", "database": "ok" }
```

Run the full smoke flow:

```bash
bash scripts/smoke.sh
```

The smoke script covers health, turn ingestion, user memory inspection, recall,
search, Stripe -> Notion supersession, and cleanup. It uses a unique smoke user
by default.

Optional overrides:

```bash
BASE_URL=http://localhost:8080 bash scripts/smoke.sh
MEMORY_AUTH_TOKEN=secret bash scripts/smoke.sh
USER_ID=my-test-user bash scripts/smoke.sh
```

Open Swagger UI:

```text
http://localhost:8080/docs
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
scripts/smoke.sh        End-to-end Docker smoke flow
scripts/test.sh         Live endpoint test runner for a running Docker stack
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
- Canonical memory `slot` values normalize equivalent keys such as
  `employment.company` and `employment.current_company`.
- Partial unique indexes enforce one active memory per user/slot or session/slot.
- `POST /turns` takes a scoped Postgres advisory lock per memory slot before
  resolving facts.
- Alembic migrations run automatically from the Docker CMD before uvicorn starts.
- New or reinforced memories get embeddings when `OPENAI_API_KEY` is configured.
- `/recall` uses pgvector cosine search plus Postgres FTS, merges rankings with
  RRF-style scoring, applies confidence/session boosts, and returns prompt-ready
  context with citations.
- `/recall` includes direct superseded history for active facts, e.g.
  `employment.current_company: Notion (previously Stripe; ...)`.
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
- Slot canonicalization is the conflict boundary: `key` preserves the extracted
  shape, while `slot` decides reinforcement, supersession, advisory locks, and
  active uniqueness.
- Recall is hybrid: pgvector handles semantic similarity, Postgres FTS handles
  exact words/entities, then RRF-style scoring merges both lists.

## Originality And Tradeoffs

This service intentionally avoids copying another memory provider's API shape or
pipeline. The core design is evidence-first: every memory points back to source
quotes, reinforcement raises confidence through repeated evidence, and database
constraints protect active memory slots.

Current tradeoffs:

- Rule-based extraction is deliberately narrow and deterministic.
- OpenAI API access is required for the full LLM extraction and embedding path.
  Without it, the service runs in deterministic fallback mode.
- `/recall` has hybrid retrieval but not LLM reranking yet.
- Embeddings are created only when `OPENAI_API_KEY` is configured.

## LLM Configuration

```env
OPENAI_API_KEY=
OPENAI_EXTRACT_MODEL=gpt-5-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
```

For the full intended platform behavior, set `OPENAI_API_KEY`. The service uses
OpenAI in two places:

- `gpt-5-mini` extracts structured memories from raw turns.
- `text-embedding-3-small` creates vectors for pgvector semantic recall.

If `OPENAI_API_KEY` is empty, the service still runs with rule-based extraction
and Postgres FTS, but recall quality is lower and semantic vector search is not
available.

`gpt-5-mini` is the default extraction model because this sprint uses a
well-defined structured JSON task. The extractor asks for strict schema output
and converts valid results into the same internal memory candidates as the
rule-based extractor.

`text-embedding-3-small` is the default embedding model. If no OpenAI key is
configured, ingestion and recall still work through rule-based extraction and
Postgres FTS.

## Swagger Smoke Test

Use `http://localhost:8080/docs` and run this scenario from Swagger.

### 1. Health

Call:

```text
GET /health
```

Expected:

```json
{
  "status": "ok",
  "database": "ok"
}
```

### 2. Create The First Turn

Call `POST /turns`:

```json
{
  "session_id": "session-berlin-1",
  "user_id": "user-1",
  "messages": [
    {
      "role": "user",
      "content": "I just moved to Berlin from NYC. I work at Stripe. My dog Biscuit is adjusting."
    },
    {
      "role": "assistant",
      "content": "Berlin sounds like a great move."
    }
  ],
  "timestamp": "2026-05-07T10:00:00Z",
  "metadata": {
    "source": "swagger-test"
  }
}
```

Expected `201`:

```json
{
  "id": "..."
}
```

This should create the raw turn and structured memories such as:

- `location.current_city = Berlin`
- `location.previous_city = NYC`
- `employment.current_company = Stripe`
- `pet.dog.name = Biscuit`

### 3. Inspect User Memories

Call:

```text
GET /users/user-1/memories
```

Expected shape:

```json
{
  "memories": [
    {
      "type": "fact",
      "key": "location.current_city",
      "value": "Berlin",
      "active": true,
      "confirmation_count": 1
    }
  ]
}
```

The real response contains more fields. Check `key`, `value`, `active`,
`supersedes`, and `superseded_by`.

### 4. Recall Location And Pet

Call `POST /recall`:

```json
{
  "query": "Where does the user live and what is the dog's name?",
  "session_id": "session-berlin-2",
  "user_id": "user-1",
  "max_tokens": 512
}
```

Expected shape:

```json
{
  "context": "## Known facts about this user\n- location.current_city: Berlin ...\n- pet.dog.name: Biscuit ...",
  "citations": [
    {
      "turn_id": "...",
      "score": 0.9,
      "snippet": "I just moved to Berlin from NYC..."
    }
  ]
}
```

### 5. Search For Biscuit

Call `POST /search`:

```json
{
  "query": "dog Biscuit",
  "session_id": "session-berlin-2",
  "user_id": "user-1",
  "limit": 10
}
```

Expected shape:

```json
{
  "results": [
    {
      "content": "pet.dog.name: Biscuit",
      "score": 0.9,
      "session_id": "session-berlin-1",
      "metadata": {
        "key": "pet.dog.name",
        "active": true
      }
    }
  ]
}
```

### 6. Test Supersession: Stripe To Notion

Create a second turn with `POST /turns`:

```json
{
  "session_id": "session-work-2",
  "user_id": "user-1",
  "messages": [
    {
      "role": "user",
      "content": "I just joined Notion."
    }
  ],
  "timestamp": "2026-05-07T11:00:00Z",
  "metadata": {
    "source": "swagger-test"
  }
}
```

Then call:

```text
GET /users/user-1/memories
```

Expected:

- `Stripe` is `active: false`
- `Notion` is `active: true`
- `supersedes` and `superseded_by` link the two memories

Then call `POST /recall`:

```json
{
  "query": "Where does the user work?",
  "session_id": "session-work-3",
  "user_id": "user-1",
  "max_tokens": 512
}
```

Expected context:

```text
employment.current_company: Notion (previously Stripe; confidence ...; updated ...)
```

Example successful response:

```json
{
  "context": "## Known facts about this user\n- employment.current_company: Notion (previously Stripe; confidence 0.90; updated 2026-05-07)\n- location.current_city: Berlin (confidence 0.92; updated 2026-05-07)\n- location.previous_city: NYC (confidence 0.88; updated 2026-05-07)\n- event.recent_move: Moved to Berlin from NYC (confidence 0.90; updated 2026-05-07)\n- pet.dog.name: Biscuit (confidence 0.86; updated 2026-05-07)\n- event.pet_dog_adjusting: Dog Biscuit is adjusting to the move (confidence 0.90; updated 2026-05-07)",
  "citations": [
    {
      "turn_id": "...",
      "score": 1.0135,
      "snippet": "I just joined Notion."
    }
  ]
}
```

### 7. Delete The User

Call:

```text
DELETE /users/user-1
```

Expected: `204 No Content`.

Then verify:

```text
GET /users/user-1/memories
```

Expected:

```json
{
  "memories": []
}
```

## Tests

Start Docker first:

```bash
docker compose up --build
```

Then run the live endpoint test script:

```bash
bash scripts/test.sh
```

This script does not start Docker. It assumes the API is already running and
then tests the real HTTP endpoints:

- `GET /health`
- `POST /turns`
- `GET /users/{user_id}/memories`
- `POST /recall`
- `POST /search`
- `DELETE /sessions/{session_id}`
- `DELETE /users/{user_id}`
- invalid payload checks that must return `422`
- cleanup checks that memories are removed


Thank you ! For seeing this work.GL and HF in eveything!