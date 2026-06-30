# WZKF Live MVP Acceptance Sequence Evidence

Date: 2026-06-30
Generated: 2026-06-30 18:27:08 IDT
Workspace: `<weightiz-workspace>`
Project: `<wzkf-root>`

## Verdict

```text
SMALL LIVE MVP ACCEPTANCE SEQUENCE: PASS
FULL ORIGINAL 5/20/2 ACCEPTANCE: NOT PROVEN
OVERALL GOAL STATUS: PARTIAL
```

This evidence note records the first single-command sequence that proved the
small live MVP path with live Docker services, a fresh Postgres database,
Alembic migrations, Redis/RQ embedding jobs, Postgres/pgvector retrieval,
context-pack generation, API artifacts, Obsidian exports, and rerun
idempotency.

It does not prove production readiness. It also does not prove the larger final
acceptance scale from the 15th user question: 5 podcast episodes, 20 academic
papers, and 2 GitHub repositories.

## Command

Run from:

```text
<wzkf-root>
```

Command:

```bash
bash -n scripts/run_live_mvp_acceptance.sh && scripts/run_live_mvp_acceptance.sh
```

Exit code:

```text
0
```

## Run Artifacts

```text
run_root=<acceptance-run-root>
database=wzkf_acceptance_1782833086
storage_root=<acceptance-run-root>/live-small-storage
redis_url=redis://localhost:6379/0
queue_name=wzkf-acceptance-1782833086
summary_path=<acceptance-run-root>/acceptance-summary.json
log_path=<acceptance-run-root>/acceptance.log
first_evidence=<acceptance-run-root>/first-live-small-smoke.json
second_evidence=<acceptance-run-root>/second-live-small-smoke.json
cli_context_pack=<acceptance-run-root>/cli-context-pack.json
```

## Test And Registry Proof

Pytest:

```text
collected 88 items
======================== 88 passed, 1 warning in 0.99s =========================
```

Source registry:

```text
sources.yaml valid: 17 sources
```

## Live Infrastructure Proof

Docker Compose:

```text
wz-knowledge-fabric-postgres-1   pgvector/pgvector:pg16   Up About an hour   0.0.0.0:5432->5432/tcp
wz-knowledge-fabric-redis-1      redis:7-alpine           Up About an hour   0.0.0.0:6379->6379/tcp
```

Connectivity checks:

```text
postgres_select_1=1
redis_ping=true
```

## Real Migration Proof

Fresh database:

```text
created_database=wzkf_acceptance_1782833086
```

Alembic output:

```text
Running upgrade  -> 0001_initial, initial schema
Running upgrade 0001_initial -> 0002_live_mvp_schema, live MVP schema compatibility
```

Schema verification:

```text
tables=alembic_version,child_chunks,claims,concept_aliases,concepts,context_packs,costs,document_concepts,documents,embeddings,jobs,parent_chunks,raw_artifacts,relations,sources
expected_missing=none
extensions=plpgsql,vector
alembic_version=0002_live_mvp_schema
```

The migration emitted this SQLAlchemy reflection warning:

```text
SAWarning: Did not recognize type 'vector' of column 'embedding_vector'
```

Interpretation: the migration completed and the `vector` extension was present.
The warning is from SQLAlchemy reflection, not a failed migration.

## RQ Worker Proof

First live-small run:

```text
Worker ... finished executing 5 jobs, quitting
live-small status=PASS
counts documents=5 raw_artifacts=5 child_chunks=254 embeddings=254 concepts=1 claims=5 context_packs=1
api_search_status=200 api_search_result_count=10 api_context_status=200
context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075 obsidian_notes=6 cost_operations=254
rq worked=true succeeded=5 failed=0 pending=0
```

Second run against the same DB/storage:

```text
Worker ... done, quitting
live-small status=PASS
counts documents=5 raw_artifacts=5 child_chunks=254 embeddings=254 concepts=1 claims=5 context_packs=1
api_search_status=200 api_search_result_count=10 api_context_status=200
context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075 obsidian_notes=6 cost_operations=254
rq worked=false succeeded=5 failed=0 pending=0
```

Interpretation:

- The first run executed five RQ jobs.
- The second run found no new RQ work.
- Counts, cost operations, and the context-pack hash stayed stable.
- This proves idempotency for the small live path.

## DB Counts

Final acceptance assertions:

```json
{
  "child_chunks": 254,
  "claims": 5,
  "concept_aliases": 1,
  "concepts": 1,
  "context_packs": 1,
  "costs": 5,
  "documents": 5,
  "embeddings": 254,
  "jobs": 5,
  "parent_chunks": 5,
  "raw_artifacts": 5
}
```

## Retrieval Methods

```json
{
  "academic_metadata_api": 2,
  "arxiv_atom": 1,
  "github_clone": 1,
  "podcast_rss_transcript": 1
}
```

This proves that the small live path did not just relabel fixtures. It wrote
separate live retrieval-method evidence into Postgres for RSS transcript,
arXiv Atom, OpenAlex/Crossref metadata, and GitHub clone inputs.

## Source URLs

```text
https://share.transistor.fm/s/6b6fe1af
http://arxiv.org/abs/1105.4789v1
https://openalex.org/W2088503847
https://doi.org/10.1017/cbo9781316683040.014
https://github.com/janestreet/ppx_expect
```

## Context-Pack And Search Proof

CLI search output:

```text
5.21  01775005d41a5e031fbfbcf5  e44946b8ce03e1b66cc11173  https://openalex.org/W2088503847
4.81  01775005d41a5e031fbfbcf5  1954f67b29ed1bbd168be898  https://openalex.org/W2088503847
4.81  86fa09593a49e5795490f7a9  7cd70d4ff5c5b63b9a618200  https://share.transistor.fm/s/6b6fe1af
```

CLI context-pack summary:

```text
cli_context_abstain=false
cli_context_pack_hash=ee9271964e95d01ecdf217541873e2aeefe08a378e57ef3189e8c91c8e920231
cli_context_child_count=10
cli_context_citation_1=doc:01775005d41a5e031fbfbcf5 child:e44946b8ce03e1b66cc11173 source:https://openalex.org/W2088503847 hash:03313c917f6c3e947f7528477b0b630c924dfc8a81996b0cc120b105c36f24ea
cli_context_citation_2=doc:01775005d41a5e031fbfbcf5 child:1954f67b29ed1bbd168be898 source:https://openalex.org/W2088503847 hash:0b0f0784a88e465ba264d3bc7ed41b9588fc92683b94c106fb71b5ded095ed33
cli_context_citation_3=doc:86fa09593a49e5795490f7a9 child:7cd70d4ff5c5b63b9a618200 source:https://share.transistor.fm/s/6b6fe1af hash:9247aac6b1fcfb12fa00475e3f9fe538aae1681497df494cb0e0f9f2d10710b5
```

API artifact summary:

```text
search_status=200
search_result_count=10
context_status=200
context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075
```

## Obsidian Export Proof

```text
obsidian_notes=6
```

Exported Markdown note names:

```text
Concept - Limit Order Book.md
Is the Electronic Open Limit Order Book Inevitable.md
Limit Order Book Data.md
Stochastic Price Dynamics Implied By the Limit Order Book.md
What comes after smartphones with Snap CEO Evan Spiegel.md
janestreetppx_expect fixture repository.md
```

## Canonical Storage Proof

Direct DB query confirmed each document row has:

- `id`
- `document_type`
- `canonical_url`
- `license_status`
- `source_hash`
- `canonical_hash`
- `raw_path`
- `canonical_text_path`
- joined raw artifact `retrieval_method`
- joined raw artifact `sha256`

Example podcast row:

```text
id=86fa09593a49e5795490f7a9
type=podcast_episode
url=https://share.transistor.fm/s/6b6fe1af
license_status=official_public_research_private
source_hash=0ea3cd35cc3665b17c379646b49341527ac6fbf5c4d4171c65db7664b5fa5794
canonical_hash=b9ffb524f63161f0f830fac5a3967a466f0a348c0c763056d84b3d058cf2482b
retrieval_method=podcast_rss_transcript
raw_path=<acceptance-run-root>/live-small-storage/raw/86fa09593a49e5795490f7a9/text/0ea3cd35cc3665b17c379646b49341527ac6fbf5c4d4171c65db7664b5fa5794.txt
canonical_text_path=<acceptance-run-root>/live-small-storage/canonical/86fa09593a49e5795490f7a9/b9ffb524f63161f0f830fac5a3967a466f0a348c0c763056d84b3d058cf2482b.txt
```

## Final Boundary

Proven:

```text
One-command small live MVP proof for:
1 real podcast transcript source
3 live academic metadata records
1 real GitHub repository
Redis/RQ-backed mock embedding jobs
live Postgres/pgvector schema and retrieval
API search/context artifacts
Obsidian insight export
rerun idempotency
all tests passing
```

Not proven:

```text
5 real podcast episodes
20 real academic papers
2 real GitHub repositories
live paid OpenAI embeddings
production OpenAI/Anthropic structured extraction
production semantic chunking for papers/formulas/tables/code
production deployment, auth, backups, monitoring, and worker orchestration
```
