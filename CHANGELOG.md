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
