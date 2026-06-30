# WZ Knowledge Fabric MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan step by step. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable, research-only WZ Knowledge Fabric slice with rights gates, deterministic artifacts, evidence-bound retrieval, CLI/API entrypoints, and Obsidian insight export.

**Architecture:** Create an isolated Python 3.12 project under `wz-knowledge-fabric/`. Keep `weightiz-main` runtime untouched. Implement small typed modules that can later be backed by Postgres/pgvector while tests exercise deterministic local behavior.

**Tech Stack:** Python 3.12, uv, Typer, FastAPI, SQLAlchemy, Alembic, PostgreSQL/pgvector via docker compose, Redis/RQ, Pydantic, pytest.

---

### Task 1: Bootstrap Tests And Guardrail Files

**Files:**
- Create: `AGENTS.md`
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `docker-compose.yml`
- Create: `config/*.yaml`
- Create: `tests/*.py`
- Create: `tests/fixtures/signals_threads/episode.html`

- [ ] **Step 1: Write failing tests**

Write tests for the rights gate, hashing/storage, chunking, ontology aliases,
claim evidence validation, context-pack determinism, Obsidian raw-transcript
exclusion, cost cache idempotency, DB table metadata, CLI help, and official
transcript fixture ingestion.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest
```

Expected: tests fail because the `wzkf` package modules do not exist yet.

### Task 2: Implement Minimal MVP Modules

**Files:**
- Create: `src/wzkf/**/*.py`
- Create: `alembic.ini`
- Create: `src/wzkf/db/migrations/env.py`
- Create: `src/wzkf/db/migrations/versions/0001_initial.py`

- [ ] **Step 1: Implement only the APIs described by the tests**

Create small Pydantic and dataclass models for source decisions, artifacts,
chunks, concepts, claims, search results, context packs, and Obsidian insights.

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest
```

Expected: all MVP tests pass.

### Task 3: Record Evidence And Gaps

**Files:**
- Create: `weightiz-decision-vault/40-implementation-logs/2026-06-30-wz-knowledge-fabric-mvp.md`

- [ ] **Step 1: Record implementation note**

Include branch, HEAD, files touched, commands run, results, evidence links,
open risks, and follow-ups. Mark network harvesters, real embeddings, and live
Postgres verification as partial unless executed.

- [ ] **Step 2: Final verification**

Run:

```bash
uv run pytest
git status --short --branch --ignore-submodules=none
```

Expected: tests pass and dirty files are limited to the new project plus the
new vault note, with pre-existing dirty files preserved.
