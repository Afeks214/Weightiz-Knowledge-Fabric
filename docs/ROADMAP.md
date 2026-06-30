# WZ Knowledge Fabric Roadmap

This roadmap is claim-bounded. It separates what is proven by current
verification from what remains partial or not proven.

## PROVEN

- `uv run pytest` passes for the current test suite.
- `uv run wzkf sources validate` validates the configured source registry.
- Docker Compose starts local Postgres/pgvector and Redis.
- Alembic migrates an isolated Postgres database to `0002_live_mvp_schema`.
- `scripts/run_live_mvp_acceptance.sh` passes end to end on a local machine with
  Docker available.
- `wzkf smoke live-small` ingests:
  - one RSS transcript source,
  - one arXiv Atom record,
  - one OpenAlex metadata record,
  - one Crossref metadata record,
  - one GitHub repository clone.
- The live-small path persists provenance, raw artifacts, canonical files,
  parent chunks, child chunks, embeddings, claims, jobs, costs, concepts, and
  context packs.
- Redis/RQ executes embedding jobs on the first live-small run.
- A second live-small run preserves core counts and context-pack hash.
- Postgres full-text plus pgvector search returns cited chunks.
- Context packs include document IDs, child chunk IDs, source URLs, and chunk
  hashes.
- Obsidian insight/concept notes export with `raw_transcript_exported: false`.

## PARTIAL

- Live external source ingestion is proven only for the small acceptance corpus.
- Embedding infrastructure supports OpenAI but acceptance uses mock embeddings.
- FastAPI endpoints exist and are exercised through `TestClient`, not as a
  hosted service.
- Source policies cover target families, but full operational license workflows
  are not implemented.
- Repository file selection skips obvious secret-like paths, but full secret
  scanning of cloned third-party repositories is not implemented.
- Cost accounting records local operation counts and zero-cost mock embeddings;
  provider-specific paid usage accounting is not proven.

## NOT_PROVEN

- Production deployment, authentication, TLS, observability, and HA.
- Paid OpenAI embedding execution in acceptance.
- Large-corpus ingestion across all target podcasts, repositories, academic
  sources, and datasets.
- Search relevance quality against a benchmark set.
- Reranking, score normalization, and query evaluation.
- HNSW/IVFFlat pgvector index performance.
- Licensed current Reuters/LSEG full-text ingestion.
- Production backup, restore, retention, and access-control procedures.

## NEXT PHASE

1. Keep GitHub Actions CI green for tests and source validation; decide whether
   the Docker acceptance job should remain manual or become a required runner
   gate.
2. Add CodeQL and dependency/security scanning.
3. Add OpenLineage-style run manifests for ingestion and processing runs.
4. Add Pydantic schemas for source, rights, academic query, and extraction
   config files.
5. Add structured logging with run IDs, job IDs, document IDs, and source IDs.
6. Add a retrieval benchmark with golden questions and expected citations.
7. Add pgvector HNSW index migration and performance notes.
8. Add data quality scoring per source and document.
9. Add production deployment checklist with auth, TLS, secrets, backup, and
   monitoring gates.
10. Add public security policy and disclosure process.
