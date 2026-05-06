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
