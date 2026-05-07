# Changelog

## v0 - Project skeleton setup

**What changed:** Added FastAPI, Postgres/pgvector, Alembic, Docker Compose,
environment settings, package layout, and setup-level tests.

**Why:** The project needs a runnable foundation before implementing memory
extraction, recall, search, and fact evolution.

**Result:** The service can boot, expose `/health`, and verify database
connectivity.

## v1 - Sprint 1 core schema and contract stubs

**What changed:** Added `turns`, `memories`, and `memory_evidence` models and
migration. Implemented the full HTTP contract surface with raw turn persistence,
empty recall/search stubs, user memory inspection, and session/user cleanup.

**Why:** The memory service needs stable storage and API boundaries before
adding rule-based extraction, LLM extraction, supersession, and hybrid recall.

**Result:** Sprint 1 unit and contract tests pass. Recall quality is still
intentionally empty until the retrieval sprint.

## v2 - Sprint 2 rule-based extraction and reinforcement

**What changed:** Added a deterministic rule-based extractor for basic location,
employment, pet, diet, and communication-style memories. Wired extraction into
`POST /turns`, added `memory_evidence` writes, and implemented reinforcement for
same key/value facts through `confirmation_count` and confidence boosts.

**Why:** The service needs real structured memory before adding LLM extraction or
hybrid recall. Rule-based extraction also provides a fallback path for obvious
facts.

**Result:** Unit coverage verifies extracted memories, evidence creation, and
same-fact reinforcement. Supersession is intentionally deferred to Sprint 3.

## v3 - Sprint 3 supersession correctness

**What changed:** Added conflicting-fact resolution for same-key memories. New
facts supersede the old active fact with `supersedes_id` and `superseded_by_id`;
same key/value still reinforces. Added partial unique indexes for active
user/key and session/key slots, plus scoped Postgres advisory locks during turn
ingestion.

**Why:** The service must preserve history while returning only the current fact.
Database constraints and transaction locks protect the invariant that one slot
has only one active memory.

**Result:** Unit coverage verifies Stripe -> Notion style supersession,
reinforcement behavior, and advisory lock usage.

## v3.1 - Startup migrations

**What changed:** Added automatic Alembic migrations during container startup.
This now runs through Docker CMD before uvicorn starts.

**Why:** `docker compose up` should be enough to boot a ready service with the
latest schema.

**Result:** Startup migration behavior is covered by a Dockerfile contract test.

## v4 - Sprint 4 LLM extraction layer

**What changed:** Added optional OpenAI LLM extraction using the Responses API
with strict structured output. The LLM extractor returns the same memory
candidate shape as the rule-based extractor, then the combined extractor merges
and deduplicates both outputs.

**Why:** Rule-based extraction is a reliable fallback for obvious facts, but the
challenge rewards extraction of implicit facts, nuanced preferences, and
opinions. The LLM layer is the quality path while preserving local fallback
behavior.

**Result:** Mocked tests cover valid structured output, missing API key fallback,
malformed model output fallback, and rule-based plus LLM deduplication.

## v5 - Sprint 5 hybrid recall

**What changed:** Added optional OpenAI embeddings with `text-embedding-3-small`
and stores vectors on memories when available. Implemented `/recall` using
pgvector cosine candidates plus Postgres FTS candidates, merged with RRF-style
ranking and boosted by active status, same-session scope, confidence, and
confirmation count.

**Why:** The challenge explicitly penalizes vanilla vector search. Recall needs a
hybrid path that can answer semantic queries and exact keyword/entity queries.

**Result:** Unit coverage verifies embedding storage, cold recall, and keyword
recall for prompts such as "Where does the user live?" using stored structured
memories and evidence citations.

## v6 - Sprint 6 search and quality fixture

**What changed:** Wired `/search` to the same hybrid retrieval layer as
`/recall`, returning structured ranked results with memory metadata, evidence
snippets, and turn citations. Added a recall quality fixture covering
employment, location, pet, preference, and opinion evolution probes.

**Why:** Submission quality needs a reusable retrieval path and a repeatable
fixture for checking whether memory behavior improves as extraction and recall
get stronger.

**Result:** Unit coverage verifies structured search results and fixture
coverage. README now documents architecture, backing store, extraction, recall,
fact evolution, originality, and current tradeoffs.

## v7 - Docker startup correctness

**What changed:** Made Dockerfile startup the migration source of truth:
`alembic upgrade head && uvicorn ...`. Removed the stale lifespan migration
expectation from tests.

**Why:** Running migrations in FastAPI lifespan caused confusing startup
behavior while Docker already had the correct pre-uvicorn migration boundary.

**Result:** Startup coverage now checks the real Docker command. Fast suite is
46 passing tests plus 1 opt-in Docker persistence test.

## v8 - Canonical memory slots

**What changed:** Added internal `slot` storage for canonical conflict keys.
Equivalent extracted keys such as `employment.company`, `job.company`, and
`employment.current_company` now resolve to one active slot.

**Why:** Raw extracted keys are too brittle. Without a canonical slot, LLM and
rule-based extraction can create duplicate current facts for the same concept.

**Result:** Slot tests cover alias normalization, advisory locks, partial unique
indexes, reinforcement, and supersession. Fixture category coverage is now 5/5:
employment, location, pet, preference, and opinion evolution.

## v9 - Recall history context

**What changed:** Recall now attaches the direct superseded fact for active
memories and formats context with previous values, e.g. `Notion (previously
Stripe)`.

**Why:** Returning only the current fact hides useful evolution. The agent should
know both the current answer and the immediately previous state when relevant.

**Result:** Employment evolution coverage now asserts 1/1 current-plus-previous
context behavior, while inactive memories still do not appear as current facts.
