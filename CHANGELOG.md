# Changelog

Hi, I'm Beknur. This is my personal decision log for the memory-service
project. Each entry is one design iteration.

Entry structure:
- **Problem** — what required a change
- **Thinking** — how I got there
- **Options considered** — what I evaluated
- **Why this choice** — reasoning behind the decision
- **Result** — measurable metric or behavior
- **Next** — what remains

---

## v0 — Project skeleton and stack choice

**Problem (§2, §5).** The spec requires a Docker-deployable service with
Postgres + pgvector that starts via `docker compose up` with no manual
steps. I needed a working foundation before writing extraction and recall
logic.

**Thinking.** I studied three public memory systems: mem0, honcho,
hindsight. Mem0 uses graph + vectors but handles supersession weakly.
Honcho does reasoning through a closed proprietary model — not
reproducible. Hindsight describes Retain/Recall/Reflect — interesting
idea but copying their naming is prohibited (§11).

My angle: **evidence-first architecture**. Every fact must point back
to a source quote. None of the three systems do this explicitly.

**Options considered.**
1. SQLite + sqlite-vec — simpler, but weaker for concurrent sessions.
2. Postgres + pgvector — one store for relational + vector + FTS.
3. Qdrant separately + Postgres for metadata — two stores, breaks the
   §5 single-transaction guarantee.

**Why this choice.** Option 2. One Postgres volume = persistence across
`docker compose down && up` with zero extra infrastructure. pgvector +
tsvector + JSONB in one database.

**Result.** FastAPI + Postgres + pgvector starts up. `GET /health`
returns `{"status":"ok","database":"ok"}`. Alembic migrations run
automatically from the Dockerfile CMD before uvicorn.

**Next.** Core schema: three tables with the original evidence-first
model.

---

## v1 — Core schema: turns, memories, memory_evidence

**Problem (§3, §4.2).** §4.2 says "raw chunks in memories endpoint =
red flag". I needed a typed schema that stores structured facts with
provenance, not raw text.

**Thinking.** The central architectural decision: three data layers.
`turns` is the raw archive — never deleted. `memories` stores
normalized facts (type/key/value/confidence). `memory_evidence` stores
the link between a fact, its source quote, and the turn it came from.

This is my original contribution: a dedicated evidence table that
gives full explainability and protects against hallucinated memory.

I also added `confirmation_count` to `memories` — an original
mechanism. A fact the user mentioned three times is more reliable than
one mentioned once. Confidence grows on reinforcement.

**Options considered.**
1. One `memories` table with a JSONB field for evidence.
2. Three separate tables with FK cascade.
3. Event-sourced append-only log.

**Why this choice.** Option 2. A separate `memory_evidence` table
gives explainability: I can show exactly where every fact came from.
FK cascade handles DELETE correctly without extra application logic.

**Result.** Three tables in migration 0002. All §3 endpoints exist
with stub returns. Contract tests pass. `GET /users/{user_id}/memories`
returns structured rows, not raw message chunks.

**Next.** Rule-based extraction to populate memories.

---

## v2 — Rule-based extraction and reinforcement

**Problem (§4.2).** `POST /turns` saves the raw turn but extracts
nothing. `GET /users/{user_id}/memories` returns an empty list.

**Thinking.** LLM extraction is the right production path, but I
needed a deterministic fallback for tests that run without an API key.
Decision: rule-based extractor as the offline floor, LLM as the
quality upgrade.

Rule-based patterns cover: location move ("moved to X from Y"),
employment ("I work at X", "I joined X"), pets ("my dog named X"),
diet ("I'm vegetarian"), communication style ("I prefer concise").

Reinforcement logic: if the same key+value arrives again,
`confirmation_count += 1` and `confidence += 0.05`. Facts that the
user repeats become more reliable over time.

**Options considered.**
1. LLM-only extraction — tests require an OpenAI key.
2. Rule-based only — poor coverage of implicit facts.
3. Rule-based primary + LLM as fallback.
4. LLM primary + rule-based as fallback, combined and deduplicated.

**Why this choice.** Option 4 as `CombinedMemoryExtractor`. LLM runs
when a key is available; rule-based always supplements. Deduplication
on `(key, value)` prevents duplicate candidates.

**Result.** Unit tests verify the extractor finds Berlin, NYC, Notion,
Biscuit, vegetarian, and concise/direct from a single message.
`memory_evidence` is created for every extracted fact with the source
quote. Same-fact reinforcement verified: `confirmation_count` increments
and `confidence` grows on repeated evidence.

**Next.** Supersession — conflicting facts cannot both be active.

---

## v3 — Supersession and advisory lock

**Problem (§4.1).** "I work at Stripe" (session 1) → "I joined Notion"
(session 3). The extractor currently creates two active
`employment.current_company` facts. §4.1 requires: old fact goes
inactive, new fact supersedes old, history is preserved.

**Thinking.** Race condition: two concurrent `/turns` requests for the
same user can both read "Stripe active" and both insert a new fact.
I needed two levels of protection: an application-level lock (advisory)
and a database-level constraint (partial unique index).

**Options considered.**
1. Partial unique index only — DB-level protection but the application
   does not know about the conflict ahead of time.
2. Advisory lock + partial unique index — double protection.
3. Optimistic locking via a version column.

**Why this choice.** Option 2. Advisory lock keyed on
`user_id:canonical_slot` serializes concurrent writes to the same slot.
The partial unique index is the DB backstop — even if application logic
bugs, Postgres rejects a second active row for the same slot.

**Result.** Stripe → Notion supersession: old memory gets
`active=False, superseded_by_id=new.id`, new memory gets
`active=True, supersedes_id=old.id`. Full chain visible through
`GET /users/{user_id}/memories`. Advisory lock verified in unit tests.

**Next.** Canonical slot — LLM may emit `employment.company` instead
of `employment.current_company`.

---

## v4 — Canonical slot and LLM extraction

**Problem (§4.1, §4.2).** LLM can extract the same concept under
different keys: `employment.company`, `job.company`,
`employment.current_company`. Without normalization, one user can end
up with three active facts for the same job.

**Thinking.** I needed a canonicalizer: raw extracted key → canonical
slot. The `key` column preserves the extracted shape for explainability.
The `slot` column drives conflict resolution, advisory locks, and
the partial unique index.

At the same time I wired LLM extraction through OpenAI Structured
Outputs with a strict JSON schema. `gpt-4o-mini` with `timeout=30s`
and `max_retries=0` on the hot path to stay inside the §3 60-second
`/turns` budget.

**Options considered.**
1. LLM with json_mode — manual parsing, schema drift between calls.
2. Structured Outputs via `chat.completions.parse` — schema validated
   server-side, no manual parser.
3. Function calling — overhead for a task that just needs JSON.

**Why this choice.** Option 2. Pydantic schema as ground truth. No
manual parsing, no schema drift, no finish_reason truncation surprises.

**Result.** `employment.company` and `job.company` both resolve to
`employment.current_company` slot. Alias map covers 8 canonical
entries. LLM extractor returns an empty list when no API key is
configured — tests run fully offline. Migration 0004 adds the `slot`
column with a backfill from `key`.

**Next.** Hybrid recall — §10 explicitly states vanilla cosine top-k
will not score well.

---

## v5 — Hybrid recall: pgvector + FTS + RRF

**Problem (§10).** §10: "vanilla cosine-top-k will not score well."
`/recall` is still a stub. I needed a recall pipeline that combines
semantic and keyword search.

**Thinking.** Two retrieval paths:
1. pgvector cosine similarity — finds semantically similar memories.
2. Postgres FTS via `to_tsvector` + `plainto_tsquery` — finds exact
   names like "Biscuit", "Notion", "Stripe".

Reciprocal Rank Fusion merges both lists: `score = 1/(60 + rank)`.
Documents that rank highly in both lists get the maximum combined score.

On top of RRF: score boosts for active memory (+0.4), same session
(+0.25), `confirmation_count` × 0.05, confidence × 0.2.

The keyword search indexes the `slot` text — "employment current
company" splits into tokens. This lets the retriever find facts by
their canonical slot key even when the embedding is weak.

**Options considered.**
1. Vanilla cosine top-k — §10 explicitly disqualifies this.
2. BM25 via pg_search — requires an external Postgres extension.
3. Native tsvector FTS + RRF — zero new dependencies, Postgres-native.

**Why this choice.** Option 3. One store, one transaction, no new
services to operate or back up.

**Result.** `/recall` returns a formatted "## Known facts about this
user" section with confidence and updated date. Query "Where does the
user live?" → "location.current_city: Berlin (confidence 0.92;
updated 2025-03-15)". Cold session returns empty context correctly.

**Next.** Superseded history in context — recall should say
"Notion (previously Stripe)".

---

## v6 — Search, recall history, and quality fixture

**Problem (§3, §4.1, §7).** Three gaps remained:
1. `/search` — still a stub, needs structured results.
2. `/recall` does not show fact history ("previously Stripe").
3. No quality fixture to measure recall improvement across iterations.

**Thinking.**

**Search:** reuse the same `retrieve_candidates` pipeline from recall
but return structured results instead of formatted prose.

**History:** for each active memory in recall, load its direct
predecessor via `supersedes_id`. Format the line as:
`employment.current_company: Notion (previously Stripe; confidence
0.95; updated 2025-03-18)`. Inactive memories do not appear as
current facts — only as history text inside the active fact's line.

**Fixture:** 5 conversations × 5 probes covering employment evolution
(Stripe → Notion), location move (NYC → Berlin), pet name (Biscuit),
preference (concise), and opinion evolution (remote work).

**Result.** `/search` returns structured results with `memory_id`,
`type`, `key`, and `active` in metadata. Recall context includes
"previously Stripe" for the employment evolution probe. Quality
fixture: 5/5 expected facts appear in recall context with LLM
extraction enabled. Contract tests: 50 passing.

