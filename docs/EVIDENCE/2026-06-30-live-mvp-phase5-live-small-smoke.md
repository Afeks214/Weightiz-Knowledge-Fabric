# WZKF Live MVP Phase 5 Small Live Smoke Evidence

Date: 2026-06-30
Generated: 2026-06-30 18:10:17 IDT
Workspace: `<weightiz-workspace>`
Project: `<wzkf-root>`

## Status

**PARTIAL**

Phase 5 small live-source smoke is now proven. This is not the final
acceptance-scale live MVP. The proven scope is:

- one live podcast RSS feed using an official transcript URL
- one live arXiv Atom query
- one live OpenAlex metadata query
- one live Crossref metadata query
- one live GitHub clone at a fixed commit
- live PostgreSQL migration with pgvector
- raw/canonical artifact storage
- parent/child chunk persistence
- mock embeddings persisted to Postgres
- deterministic concepts, claims, context pack, API artifacts, and Obsidian
  insight-note export
- rerun idempotency for the same DB/storage path

The unproven scope is still:

- acceptance-scale ingestion of 5 podcast episodes, 20 papers, and 2 repos
- a single command sequence that routes the whole ingestion through Redis/RQ
  workers
- live paid OpenAI embedding execution
- production LLM extraction adapters
- production-grade section-aware chunking for papers, formulas, tables, and code

## Current Verification

Command:

```bash
.venv/bin/uv run pytest
```

Output:

```text
collected 87 items
...
======================== 87 passed, 1 warning in 1.42s =========================
```

Command:

```bash
.venv/bin/uv run wzkf sources validate
```

Output:

```text
sources.yaml valid: 17 sources
```

Command:

```bash
DOCKER_API_VERSION=1.43 docker compose ps
```

Output:

```text
NAME                             IMAGE                    COMMAND                  SERVICE    CREATED             STATUS          PORTS
wz-knowledge-fabric-postgres-1   pgvector/pgvector:pg16   "docker-entrypoint.s..." postgres   About an hour ago   Up 39 minutes   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
wz-knowledge-fabric-redis-1      redis:7-alpine           "docker-entrypoint.s..." redis      About an hour ago   Up 39 minutes   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
```

## Isolated Live Database

Fresh database:

```text
created_database=wzkf_live_smoke_1782832081
```

Alembic output:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, initial schema
INFO  [alembic.runtime.migration] Running upgrade 0001_initial -> 0002_live_mvp_schema, live MVP schema compatibility
```

The migration emitted this SQLAlchemy reflection warning:

```text
SAWarning: Did not recognize type 'vector' of column 'embedding_vector'
```

Interpretation: migration still succeeded and pgvector was usable; this warning
is from SQLAlchemy reflection not recognizing the extension type during the
conditional migration check.

## Live-Small Smoke Command

Command:

```bash
.venv/bin/uv run wzkf smoke live-small \
  --database-url postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf_live_smoke_1782832081 \
  --storage-root <live-small-run-root>
```

First run output:

```text
live-small status=PASS
evidence_path=<live-small-run-root>/evidence/live-small-smoke.json
counts documents=5 raw_artifacts=5 child_chunks=254 embeddings=254 concepts=1 claims=5 context_packs=1
api_search_status=200 api_search_result_count=10 api_context_status=200
context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075 obsidian_notes=6 cost_operations=254
```

Rerun output against the same DB/storage path:

```text
live-small status=PASS
evidence_path=<live-small-run-root>/evidence/live-small-smoke.json
counts documents=5 raw_artifacts=5 child_chunks=254 embeddings=254 concepts=1 claims=5 context_packs=1
api_search_status=200 api_search_result_count=10 api_context_status=200
context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075 obsidian_notes=6 cost_operations=254
```

Interpretation: the rerun kept the same document/chunk/embedding/concept/claim/
context-pack counts and the same context-pack hash. This proves idempotency for
the small live smoke path.

## Evidence JSON

Path:

```text
<live-small-run-root>/evidence/live-small-smoke.json
```

Extracted values:

```text
evidence_status=PASS
evidence_document_count=5
evidence_raw_artifact_count=5
evidence_child_chunk_count=254
evidence_embedding_count=254
evidence_cost_operations=254
evidence_context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075
evidence_api_search_status=200
evidence_api_search_result_count=10
evidence_api_context_status=200
evidence_obsidian_note_count=6
```

Source URLs:

```text
https://share.transistor.fm/s/6b6fe1af
http://arxiv.org/abs/1105.4789v1
https://openalex.org/W2088503847
https://doi.org/10.1017/cbo9781316683040.014
https://github.com/janestreet/ppx_expect
```

## Database Row Counts

```text
documents_rows=5
raw_artifacts_rows=5
parent_chunks_rows=5
child_chunks_rows=254
embeddings_rows=254
concepts_rows=1
concept_aliases_rows=1
claims_rows=5
jobs_rows=5
costs_rows=5
context_packs_rows=1
```

## Raw Artifact Retrieval Methods

```text
retrieval_method=academic_metadata_api:2
retrieval_method=arxiv_atom:1
retrieval_method=github_clone:1
retrieval_method=podcast_rss_transcript:1
```

This proves the DB can distinguish live RSS transcript ingestion, arXiv Atom
metadata ingestion, academic metadata API ingestion, and GitHub clone ingestion.

## Document Provenance Rows

```text
document={"id": "01775005d41a5e031fbfbcf5", "type": "paper", "title": "Is the Electronic Open Limit Order Book Inevitable?", "url": "https://openalex.org/W2088503847", "license_status": "metadata_only", "source_hash": "66050120554865151166e9388b134559840d7ef480fd4271fb525be01795338f", "canonical_hash": "b645f1edbcec4c16df8e1e7f41fc283b7d85dddaa7716ffa8c6949f62c3d0a05"}
document={"id": "86fa09593a49e5795490f7a9", "type": "podcast_episode", "title": "What comes after smartphones, with Snap CEO Evan Spiegel", "url": "https://share.transistor.fm/s/6b6fe1af", "license_status": "official_public_research_private", "source_hash": "0ea3cd35cc3665b17c379646b49341527ac6fbf5c4d4171c65db7664b5fa5794", "canonical_hash": "b9ffb524f63161f0f830fac5a3967a466f0a348c0c763056d84b3d058cf2482b"}
document={"id": "88d71d806cd25cad5adeb0a9", "type": "paper", "title": "Limit Order Book Data", "url": "https://doi.org/10.1017/cbo9781316683040.014", "license_status": "metadata_only", "source_hash": "4cb3c5aa96c82a58b59fc274e4f3bffdee5f850bd661467833c744671d4ce163", "canonical_hash": "a977e54c7e584eabe4e6979a4e39d7a6babd0b78d71c2a17fa1a5dbc2b29a9a7"}
document={"id": "9ea62a8bc708cd67e194f300", "type": "paper", "title": "Stochastic Price Dynamics Implied By the Limit Order Book", "url": "http://arxiv.org/abs/1105.4789v1", "license_status": "open_metadata_pdf_allowed", "source_hash": "d3642753cd6757b1ff612d84a54e1c8c64b40d83c5932b6591ac2595807879e4", "canonical_hash": "7b801814c475e5bf9ae7a484260ba3eb5f8e4af33c7f1592379bd185e516d7d4"}
document={"id": "ab089dafa378f082caccadfa", "type": "github_repo", "title": "janestreet/ppx_expect fixture repository", "url": "https://github.com/janestreet/ppx_expect", "license_status": "private_research_only", "source_hash": "54a2e16013b3e124466189739a2d00cd4c22bdc1ec4e67c2d82b5111ce45023c", "canonical_hash": "fa590a686d1bdf7bd9f007dbb7c64acb7d5cc108f1f38eb6f64ff0e63f6088ec"}
```

## API Artifacts

API artifact paths:

```text
<live-small-run-root>/artifacts/api-search.json
<live-small-run-root>/artifacts/api-context-pack.json
```

Extracted API values:

```text
api_search_abstain=false
api_search_result_count=10
search_1=doc:01775005d41a5e031fbfbcf5 child:e44946b8ce03e1b66cc11173 parent:fb8be787a06f88437e1be1ec source:https://openalex.org/W2088503847 hash:03313c917f6c3e947f7528477b0b630c924dfc8a81996b0cc120b105c36f24ea score:5.206873
search_2=doc:01775005d41a5e031fbfbcf5 child:1954f67b29ed1bbd168be898 parent:fb8be787a06f88437e1be1ec source:https://openalex.org/W2088503847 hash:0b0f0784a88e465ba264d3bc7ed41b9588fc92683b94c106fb71b5ded095ed33 score:4.811786
search_3=doc:86fa09593a49e5795490f7a9 child:7cd70d4ff5c5b63b9a618200 parent:848728e568ff974982c5ec0b source:https://share.transistor.fm/s/6b6fe1af hash:9247aac6b1fcfb12fa00475e3f9fe538aae1681497df494cb0e0f9f2d10710b5 score:4.807750
api_context_abstain=false
api_context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075
api_context_child_count=10
```

## GitHub Clone Proof

Remote HEAD and cloned commit:

```text
d36acdd3fb1409cd6422fe3064741251fe585061
```

Selected paths:

```text
LICENSE.md
README.mdx
src/dune
src/ppx_expect.ml
src/ppx_expect.mli
```

## Obsidian Export

The live-small smoke exported 6 insight/concept notes:

```text
Concept - Limit Order Book.md
Is the Electronic Open Limit Order Book Inevitable.md
Limit Order Book Data.md
Stochastic Price Dynamics Implied By the Limit Order Book.md
What comes after smartphones with Snap CEO Evan Spiegel.md
janestreetppx_expect fixture repository.md
```

The exporter writes `raw_transcript_exported: false` in note frontmatter.

## Files Changed In This Phase

- `<wzkf-root>/src/wzkf/smoke/live_small.py`
- `<wzkf-root>/src/wzkf/smoke/__init__.py`
- `<wzkf-root>/src/wzkf/cli.py`
- `<wzkf-root>/src/wzkf/ingest/fixture_ingestor.py`
- `<wzkf-root>/src/wzkf/storage/raw_store.py`
- `<wzkf-root>/src/wzkf/db/repositories.py`
- `<wzkf-root>/src/wzkf/db/alembic_config.py`
- `<wzkf-root>/src/wzkf/db/migrations/env.py`
- `<wzkf-root>/src/wzkf/harvesters/academic_metadata.py`
- `<wzkf-root>/src/wzkf/harvesters/github_repo.py`
- `<wzkf-root>/config/sources.yaml`
- `<wzkf-root>/tests/test_live_small_smoke.py`
- `<wzkf-root>/tests/test_alembic_config.py`
- `<wzkf-root>/tests/test_academic_metadata_clients.py`
- `<wzkf-root>/tests/test_fixture_paper_repo_ingestion.py`
- `<wzkf-root>/tests/test_cli_help.py`
- `<wzkf-root>/README.md`

## Final Phase 5 Verdict

**PASS for the small live-source smoke.**

**PARTIAL for the overall goal**, because final acceptance requires an
acceptance-scale run and a single command sequence that proves Redis/RQ workers
inside the full live ingestion path, not just the separate Phase 4 RQ proof and
this direct live-small smoke.
