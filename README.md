# WZ Knowledge Fabric

Research-only, evidence-backed ingestion and retrieval for Weightiz research.

Canonical truth lives in PostgreSQL plus deterministic raw/canonical artifact
storage. Obsidian is an insight export layer only.

## What This Is

WZ Knowledge Fabric is a research-only text knowledge system for podcasts,
academic metadata, open-source repositories, and legally available research
artifacts. It is designed to make every useful answer traceable back to source
URLs, document IDs, chunk IDs, hashes, and rights decisions.

It is not a trading system. It does not produce target prices, execution
instructions, live portfolio decisions, or financial advice.

## Current Truth State

### Proven

- Local live MVP acceptance passes on Docker Postgres/pgvector and Redis/RQ.
- Source registry validation passes for 17 configured sources.
- Alembic migrations create the live MVP schema and pgvector extension.
- `wzkf smoke live-small` ingests a five-document live-small corpus:
  one RSS transcript source, one arXiv Atom record, two academic metadata API
  records, and one GitHub repository clone.
- The live-small corpus persists documents, raw artifacts, parent/child chunks,
  embeddings, claims, processing jobs, costs, concepts, and context packs.
- Postgres full-text search plus pgvector retrieval returns cited child chunks.
- FastAPI search and context-pack paths are exercised by the acceptance script.
- Obsidian export writes insight/concept notes with `raw_transcript_exported:
  false`.
- Rerunning the live-small smoke preserves counts and context-pack hash.

### Not Proven

- Production deployment, hosting, TLS, auth, monitoring, and HA.
- Paid live OpenAI embedding execution.
- Broad-scale ingestion across all target source families.
- Search relevance benchmarks, reranking, and production-grade ranking quality.
- Licensed current Reuters/LSEG full-text ingestion.
- Production data retention, backup, restore, and access-control procedures.

## Architecture

```mermaid
flowchart TD
    A["Source Registry"] --> B["Rights / ABSTAIN Gate"]
    B --> C["Harvesters: RSS, arXiv, academic APIs, GitHub"]
    C --> D["Raw Artifact Store"]
    D --> E["Canonical Text Store"]
    E --> F["Parent / Child Chunking"]
    F --> G["Postgres Metadata + pgvector"]
    G --> H["Hybrid Search"]
    G --> I["Concepts and Evidence-Bound Claims"]
    H --> J["Context Packs With Citations"]
    I --> J
    J --> K["CLI / FastAPI"]
    J --> L["Obsidian Insight Export"]
```

## Evidence

Repository evidence lives under `docs/EVIDENCE/`.

Key artifacts:

- `docs/EVIDENCE/WZKF_CODEBASE_PROOF_MATRIX_2026-06-30.md`
- `docs/EVIDENCE/acceptance-summary.example.json`
- `docs/EVIDENCE/acceptance-command-log.example.txt`

The acceptance example is sanitized for public repo use. Runtime paths are
represented as placeholders such as `<wzkf-root>` and `<acceptance-run-root>`.

## Guardrails

- No paywall bypass.
- No YouTube scraping.
- No unlicensed current Reuters/LSEG full-text ingestion.
- No trading recommendations, target prices, order routing, or financial
  advice.
- Claims without `evidence_child_chunk_ids` must ABSTAIN.
- Re-running the same operation must not duplicate work or duplicate cost.

## Rights And ABSTAIN Policy

Every source must pass through a rights decision before full-text use. Unknown
or unauthorized source material is not guessed through. It becomes
`ABSTAINED`, `METADATA_ONLY`, `LICENSE_REQUIRED`, or
`UNKNOWN_REQUIRES_REVIEW`, depending on the configured source policy.

Claims and generated knowledge are evidence-bound. A claim without
`evidence_child_chunk_ids` is invalid unless it carries an explicit abstain
reason.

## Obsidian Policy

Obsidian is an export surface only. The canonical source of truth remains
Postgres plus raw/canonical artifact storage. Raw transcripts are not exported
to Obsidian by default; exported notes contain concise summaries, concepts,
evidence references, document IDs, chunk IDs, hashes, and deep links.

## Local Setup

Required runtime:

```bash
python3.12 --version
uv --version
```

Install:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Start services:

```bash
docker compose up -d
uv run alembic upgrade head
```

CLI:

```bash
uv run wzkf --help
uv run wzkf sources validate
uv run wzkf ingest podcast --source signals_threads --fixture tests/fixtures/signals_threads/episode.html
uv run wzkf ingest podcast --source signals_threads --rss-feed tests/fixtures/podcast_rss/signals_threads_feed.xml --transcript-fixture tests/fixtures/signals_threads/episode.html
uv run wzkf ingest papers --query qfin_market_microstructure --fixture tests/fixtures/papers/arxiv_qfin.xml
uv run wzkf ingest papers --query qfin_market_microstructure --atom tests/fixtures/papers/arxiv_qfin.xml
uv run wzkf ingest academic --provider openalex --query qfin_market_microstructure --fixture tests/fixtures/academic_metadata/openalex_work.json
uv run wzkf ingest academic --provider openalex --query qfin_market_microstructure --search-query "limit order book" --api-key "$WZKF_OPENALEX_API_KEY"
uv run wzkf ingest repo --source janestreet_ppx_expect --fixture tests/fixtures/repos/janestreet_ppx_expect
uv run wzkf ingest news --source reuters_21578 --fixture tests/fixtures/reuters/reuters_21578_metadata.json
uv run wzkf process document --document-id <document_id>
export WZKF_OPENAI_API_KEY=<runtime-provided-key>
uv run wzkf process document --document-id <document_id> --embedding-provider openai --embedding-model text-embedding-3-small
uv run wzkf process all --pending
uv run wzkf jobs status
uv run wzkf jobs enqueue-rq --document-id <document_id> --redis-url redis://localhost:6379/0
uv run wzkf jobs work-rq --redis-url redis://localhost:6379/0 --burst --max-jobs 1
uv run wzkf costs report
uv run wzkf ontology review
uv run wzkf search "limit order book market depth"
uv run wzkf search "limit order book market depth" --database-url postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf --embedding-model test-vector --query-embedding 0,1
uv run wzkf context-pack "Jane Street expect tests and Weightiz artifact validation"
uv run wzkf context-pack "limit order book market depth" --database-url postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf --embedding-model test-vector --query-embedding 0,1
uv run wzkf export obsidian --changed-only
uv run wzkf smoke live-small --database-url postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf --storage-root /tmp/wzkf-live-small
```

Live Postgres schema verification:

```bash
docker compose up -d
DATABASE_URL=postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf uv run alembic upgrade head
```

Isolated live-small smoke:

```bash
db=wzkf_live_smoke_$(date +%s)
uv run python - <<PY
import psycopg
from psycopg import sql
with psycopg.connect("postgresql://wzkf:wzkf@localhost:5432/postgres", autocommit=True) as conn:
    conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier("$db")))
PY
DATABASE_URL=postgresql+psycopg://wzkf:wzkf@localhost:5432/$db uv run alembic upgrade head
uv run wzkf smoke live-small \
  --database-url postgresql+psycopg://wzkf:wzkf@localhost:5432/$db \
  --storage-root /tmp/wzkf-live-small-$db
uv run wzkf smoke live-small \
  --database-url postgresql+psycopg://wzkf:wzkf@localhost:5432/$db \
  --storage-root /tmp/wzkf-live-small-$db
```

Single-command live MVP acceptance sequence:

```bash
scripts/run_live_mvp_acceptance.sh
```

The acceptance script runs tests, source validation, Docker Compose,
Postgres/Redis connectivity checks, a fresh Alembic migration, the live-small
smoke through Redis/RQ-backed mock embedding jobs, a rerun idempotency check,
Postgres/pgvector search, context-pack generation, API artifact checks, and
Obsidian export checks. It writes an auditable log and summary under
`/tmp/wzkf-live-mvp-acceptance-<timestamp>/`.

## MVP Slice

The first reviewable slice covers:

- source registry and rights gate
- deterministic raw/canonical file storage
- parent-child chunking
- concept alias resolution for limit-order-book synonyms
- evidence-bound claim validation
- deterministic structured extraction for summaries, claims, concepts, methods,
  formulas, caveats, implementation patterns, and Weightiz hooks
- legal harvesters for Podcasting 2.0 RSS transcript tags, arXiv Atom feeds,
  OpenAlex, Crossref, Unpaywall, CORE metadata fixtures, approved GitHub repo
  file selection, and Reuters-21578 metadata-only records
- cached academic metadata API clients for OpenAlex/Crossref/CORE query
  requests and Unpaywall DOI lookups, with injectable transports for tests;
  OpenAlex query requests can use the public API without an API key, while
  optional API-key/mailto config is preserved when supplied
- CLI academic ingestion can use the cached client path with `--search-query`
  or `--doi`, then records the returned metadata into the local manifest corpus
- academic API source registry entries for arXiv, Semantic Scholar, OpenAlex,
  Crossref, Unpaywall, and CORE with metadata-first rights decisions
- DOI-backed academic metadata de-duplication across providers, preserving
  provider/source/PDF provenance in the manifest
- deterministic context packs
- child-chunk retrieval with parent-context expansion for context packs
- manifest-backed ontology store with canonical concepts, aliases, evidence
  chunk IDs, document IDs, confidence scores, and review items
- hybrid text/vector ranking over persisted mock embeddings in local and
  SQLAlchemy-backed paths
- file-backed local processing jobs, cached embedding operations, and a
  cost-ledger report path keyed by input hash, prompt hash, model name, and
  config hash
- Redis/RQ embedding job enqueue and burst-worker execution over the same
  idempotent local job/cost manifests
- an OpenAI-compatible embedding adapter for live processing, fail-closed when
  no runtime API key is provided; mock embeddings remain the default test and
  local path, and API keys are not written to job, cache, or cost manifests
- Obsidian insight-note and concept-note export without raw transcripts, with a
  content-hash changed-only ledger
- CLI and FastAPI entrypoints over the local manifest-backed corpus, including
  documents, concepts, local embedding jobs, and costs
- CLI and FastAPI search/context-pack entrypoints can use live Postgres FTS +
  pgvector retrieval when a database URL is configured, while retaining local
  manifest fallback
- SQLAlchemy model metadata and Alembic migrations for live Postgres with
  pgvector installed, canonical `jobs` and `costs` tables, and an
  `embeddings.embedding_vector` column for live similarity search
- SQLite-tested idempotent repository methods for documents, chunks,
  embeddings, claims, jobs, costs, and context packs
- Postgres full-text plus pgvector hybrid search SQL that returns child chunk,
  parent chunk, document, source URL, chunk hash, text/vector scores, and final
  score
- `wzkf smoke live-small` can ingest one official RSS transcript, one arXiv
  Atom record, one OpenAlex metadata record, one Crossref metadata record, and
  one GitHub repository clone into live Postgres/pgvector, then build
  embeddings, concepts, claims, context packs, API artifacts, and Obsidian
  insight notes idempotently

Live Docker, Postgres migration, Postgres FTS + pgvector retrieval, and
Redis/RQ embedding workers have local proof points. The CLI and FastAPI
entrypoints still default to the local manifest-backed corpus unless
`DATABASE_URL` or `--database-url` is supplied. A small live-source smoke is
proven, but acceptance-scale ingestion, a Redis/RQ-backed end-to-end live
ingestion command, and live OpenAI embedding execution remain unproven unless
credentials and target provider access are supplied.
