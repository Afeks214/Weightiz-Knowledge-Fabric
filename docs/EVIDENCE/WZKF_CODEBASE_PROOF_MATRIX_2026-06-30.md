# WZKF Codebase Proof Matrix - 2026-06-30

## Executive Verdict

**Seal objective traced:** `WZKF-REPO-SEAL-AND-INSTITUTIONAL-DD-001`.

**Claim status:** `LIVE LOCAL MVP PROVEN`.

This does **not** mean production-scale deployment is proven. It means the
current checkout contains a working WZ Knowledge Fabric MVP that was freshly
verified on 2026-06-30 21:52:51 IDT through the repository acceptance script.

The verified slice includes:

- Python 3.12 package and CLI entrypoint.
- Source registry and rights gate.
- Docker Postgres with pgvector plus Redis.
- Alembic migration to the live MVP schema.
- Live-small ingestion from one RSS transcript source, one arXiv Atom record,
  two academic metadata API sources, and one GitHub repository clone.
- Deterministic raw/canonical storage.
- Parent/child chunks.
- Mock embeddings persisted into Postgres with pgvector-compatible vectors.
- Redis/RQ-backed embedding jobs.
- Cost/cache manifests.
- Evidence-bound claims.
- Postgres full-text plus pgvector retrieval.
- Context-pack generation with document IDs, child chunk IDs, source URLs, and
  chunk hashes.
- FastAPI search/context endpoints exercised through `TestClient`.
- Obsidian insight/concept export with `raw_transcript_exported: false`.
- Rerun idempotency checks for core counts, cost operations, and context hash.

**Hard boundary:** this proves a local live MVP, not production scale, not paid
OpenAI embedding execution, not broad corpus coverage, not a hosted API, and not
external deployment readiness.

## Scope

Workspace:

```text
<weightiz-workspace>
```

WZKF codebase:

```text
<wzkf-root>
```

Current superproject HEAD observed during this report:

```text
c2af216b90d22c5efa3c7c76dc235018370b473a
```

Fresh acceptance run:

```text
Command:
scripts/run_live_mvp_acceptance.sh

Working directory:
<wzkf-root>

Exit code:
0

Run root:
<acceptance-run-root>

Run timestamp:
2026-06-30 21:52:51 IDT
```

## Correction Of The Attached Stale Report

The attached report at
`<user-home>/.codex/attachments/8932eb5b-5e7c-4d83-a7bc-64c40165bcb1/pasted-text.txt`
is not an accurate description of the current checkout.

| Old attachment claim | Current truth | Current evidence |
| --- | --- | --- |
| Code path is `src/wzk/` | Current package is `src/wzkf/` | Staged tree contains `wz-knowledge-fabric/src/wzkf/...`; `pyproject.toml` maps package to `src/wzkf`. |
| 35 tests passed | 88 tests passed | Fresh acceptance log: `collected 88 items` and `88 passed, 1 warning in 1.78s`. |
| Docker cannot connect | Docker services are running | Fresh acceptance log: Postgres and Redis containers both `Up 4 hours`. |
| No live DB | Isolated live DB created and migrated | Fresh run created `wzkf_acceptance_1782845571`, migrated to `0002_live_mvp_schema`, and verified expected tables. |
| Retrieval is placeholder returning `[]` | Postgres FTS plus pgvector query returns ranked rows | Fresh CLI search returned three scored rows; code implements SQL in `postgres_hybrid_search_sql()`. |
| No Redis/RQ | RQ executed five embedding jobs on first run | Fresh acceptance log: `rq worked=true succeeded=5 failed=0 pending=0`. |
| DB rows are zero | DB rows are nonzero | Fresh summary: `documents=5`, `raw_artifacts=5`, `child_chunks=254`, `embeddings=254`, `claims=5`, `context_packs=1`. |
| Live MVP still blocked | Local live MVP acceptance is passing | Fresh summary status is `PASS`. |

The old report is useful only as a history of an earlier scaffold. It must not
be used as the current system status.

## Fresh Runtime Evidence

The acceptance script itself proves what it checks. It runs tests, validates
sources, starts infrastructure, creates a fresh isolated DB, migrates schema,
runs live-small twice, searches Postgres, generates a CLI context pack, verifies
idempotency, checks DB row counts, and writes a summary:

```text
<wzkf-root>/scripts/run_live_mvp_acceptance.sh:52
run "$UV_BIN" run pytest

<wzkf-root>/scripts/run_live_mvp_acceptance.sh:53
run "$UV_BIN" run wzkf sources validate

<wzkf-root>/scripts/run_live_mvp_acceptance.sh:55-56
run docker compose up -d
run docker compose ps

<wzkf-root>/scripts/run_live_mvp_acceptance.sh:98-100
DATABASE_URL="$DB_URL" "$UV_BIN" run alembic upgrade head

<wzkf-root>/scripts/run_live_mvp_acceptance.sh:127-141
run "$UV_BIN" run wzkf smoke live-small ... --use-rq ...
run "$UV_BIN" run wzkf smoke live-small ... --use-rq ...

<wzkf-root>/scripts/run_live_mvp_acceptance.sh:187-207
asserts rerun equality, RQ completion, non-abstaining context pack, and cited child chunks.
```

Fresh command output:

```text
collected 88 items
88 passed, 1 warning in 1.78s

sources.yaml valid: 17 sources

wz-knowledge-fabric-postgres-1   pgvector/pgvector:pg16   Up 4 hours   0.0.0.0:5432->5432/tcp
wz-knowledge-fabric-redis-1      redis:7-alpine           Up 4 hours   0.0.0.0:6379->6379/tcp

postgres_select_1=1
redis_ping=true

created_database=wzkf_acceptance_1782845571

Running upgrade  -> 0001_initial, initial schema
Running upgrade 0001_initial -> 0002_live_mvp_schema, live MVP schema compatibility

tables=alembic_version,child_chunks,claims,concept_aliases,concepts,context_packs,costs,document_concepts,documents,embeddings,jobs,parent_chunks,raw_artifacts,relations,sources
expected_missing=none
extensions=plpgsql,vector
alembic_version=0002_live_mvp_schema

live-small status=PASS
counts documents=5 raw_artifacts=5 child_chunks=254 embeddings=254 concepts=1 claims=5 context_packs=1
api_search_status=200 api_search_result_count=10 api_context_status=200
context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075 obsidian_notes=6 cost_operations=254
rq worked=true succeeded=5 failed=0 pending=0

second run:
live-small status=PASS
counts documents=5 raw_artifacts=5 child_chunks=254 embeddings=254 concepts=1 claims=5 context_packs=1
context_pack_hash=c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075 obsidian_notes=6 cost_operations=254
rq worked=false succeeded=5 failed=0 pending=0

acceptance_status=PASS
```

The second run's `rq worked=false` is not a failure. The script asserts the
queue still has `succeeded=5`, `failed=0`, `pending=0`, and that core counts and
hashes match the first run. That is evidence of idempotency: no new work was
needed on rerun.

## Acceptance Summary Evidence

Fresh summary file:

```text
<acceptance-run-root>/acceptance-summary.json
```

Key fields:

```json
{
  "status": "PASS",
  "database": "wzkf_acceptance_1782845571",
  "db_counts": {
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
  },
  "retrieval_methods": {
    "academic_metadata_api": 2,
    "arxiv_atom": 1,
    "github_clone": 1,
    "podcast_rss_transcript": 1
  },
  "rq": {
    "failed": 0,
    "pending": 0,
    "succeeded": 5,
    "used": true,
    "worked_first_run": true,
    "worked_second_run": false
  },
  "api": {
    "context_status": 200,
    "search_result_count": 10,
    "search_status": 200
  }
}
```

Source URLs proven in the fresh run:

```text
https://share.transistor.fm/s/6b6fe1af
http://arxiv.org/abs/1105.4789v1
https://openalex.org/W2088503847
https://doi.org/10.1017/cbo9781316683040.014
https://github.com/janestreet/ppx_expect
```

Document IDs produced:

```text
86fa09593a49e5795490f7a9
9ea62a8bc708cd67e194f300
01775005d41a5e031fbfbcf5
88d71d806cd25cad5adeb0a9
ab089dafa378f082caccadfa
```

Context pack hashes:

```text
API/live-small context hash:
c364146a0bf99cd57ceaa1080ac549f394486fe07a9d7ba59cdf46d278f7c075

CLI context pack hash:
ee9271964e95d01ecdf217541873e2aeefe08a378e57ef3189e8c91c8e920231
```

CLI search evidence:

```text
5.21  01775005d41a5e031fbfbcf5  e44946b8ce03e1b66cc11173  https://openalex.org/W2088503847
4.81  01775005d41a5e031fbfbcf5  1954f67b29ed1bbd168be898  https://openalex.org/W2088503847
4.81  86fa09593a49e5795490f7a9  7cd70d4ff5c5b63b9a618200  https://share.transistor.fm/s/6b6fe1af
```

CLI context-pack citation evidence:

```text
doc=01775005d41a5e031fbfbcf5
child=e44946b8ce03e1b66cc11173
source=https://openalex.org/W2088503847
hash=03313c917f6c3e947f7528477b0b630c924dfc8a81996b0cc120b105c36f24ea

doc=01775005d41a5e031fbfbcf5
child=1954f67b29ed1bbd168be898
source=https://openalex.org/W2088503847
hash=0b0f0784a88e465ba264d3bc7ed41b9588fc92683b94c106fb71b5ded095ed33

doc=86fa09593a49e5795490f7a9
child=7cd70d4ff5c5b63b9a618200
source=https://share.transistor.fm/s/6b6fe1af
hash=9247aac6b1fcfb12fa00475e3f9fe538aae1681497df494cb0e0f9f2d10710b5
```

Obsidian notes produced:

```text
Concept - Limit Order Book.md
Is the Electronic Open Limit Order Book Inevitable.md
Limit Order Book Data.md
Stochastic Price Dynamics Implied By the Limit Order Book.md
What comes after smartphones with Snap CEO Evan Spiegel.md
janestreetppx_expect fixture repository.md
```

## Codebase Proof Matrix

| Claim | Status | Code evidence | Runtime evidence |
| --- | --- | --- | --- |
| Python 3.12 app with required stack exists | `PROVEN` | `<wzkf-root>/pyproject.toml` declares `requires-python >=3.12`, Typer, FastAPI, SQLAlchemy, Alembic, psycopg, Redis, RQ. | Tests ran under Python 3.12.13. |
| CLI entrypoint exists | `PROVEN` | `pyproject.toml` maps `wzkf = "wzkf.cli:app"`. | Acceptance calls `uv run wzkf ...` successfully. |
| Source registry validates configured sources | `PROVEN` | `source_registry.py:32-39` loads sources/policies and validates references; `source_registry.py:89-99` rejects duplicate IDs and unknown policies. | `sources.yaml valid: 17 sources`. |
| Rights gate enforces private research and ABSTAIN boundaries | `PROVEN` | `license_gate.py:33-102` returns `ABSTAINED`, `METADATA_ONLY`, `ALLOWED`, or review decisions; YouTube without authorized transcript/audio abstains at `license_gate.py:36-43`. | `tests/test_rights_gate.py` passed in the 88-test suite. |
| Postgres schema models encode provenance tables | `PROVEN` | `models.py:37-219` defines sources, documents, raw artifacts, parent chunks, child chunks, embeddings, concepts, claims, jobs, costs, context packs. | Fresh DB had all expected tables and row counts. |
| pgvector is installed and vector column exists | `PROVEN` | `0002_live_mvp_schema.py:21-32` creates extension `vector` and adds `embeddings.embedding_vector vector`. | Fresh run printed `extensions=plpgsql,vector` and `alembic_version=0002_live_mvp_schema`. |
| Live-small refuses fake live mode without DB | `PROVEN` | `cli.py:457-460` exits with `ABSTAIN` when no DB URL is supplied. | Acceptance supplied a real isolated DB URL and passed. |
| Live-small ingests one RSS transcript source | `PROVEN` | `live_small.py:293-309` fetches RSS, requires selected artifact type `transcript`, fetches transcript text, and records it. `podcast_rss.py:31-47` prefers transcript metadata over audio. | Retrieval methods include `podcast_rss_transcript: 1`; source URL includes `https://share.transistor.fm/s/6b6fe1af`. |
| YouTube-only podcast scraping is blocked | `PROVEN` | `podcast_rss.py:34-35` raises when a YouTube source lacks authorized transcript metadata; `license_gate.py:36-43` also abstains. | Rights tests passed. |
| Live-small ingests arXiv and academic metadata | `PROVEN` | `live_small.py:311-332` fetches arXiv Atom, OpenAlex, and Crossref records through cached metadata clients. | Retrieval methods include `arxiv_atom: 1` and `academic_metadata_api: 2`. |
| Live-small clones and selects GitHub repo files | `PROVEN` | `live_small.py:334-346` clones the GitHub repo and records selected files. `github_repo.py:26-40` selects README/license/docs/examples/src/tests and skips filenames containing secret/token/password/credential. | Retrieval methods include `github_clone: 1`; source URL includes `https://github.com/janestreet/ppx_expect`. |
| Raw/canonical provenance is persisted | `PROVEN` | `models.py:51-83` stores document source hash, canonical hash, raw path, canonical path, artifact sha256, retrieval method. `repositories.py:362-413` writes those fields. | Fresh counts: `documents=5`, `raw_artifacts=5`, `canonical_file_count=5`. |
| Parent/child chunks are deterministic and hashable | `PROVEN` | `parent_child.py:36-100` creates a parent chunk and child chunks with stable IDs derived from chunk hashes. | Fresh counts: `parent_chunks=5`, `child_chunks=254`. |
| Embeddings are cached by operation key | `PROVEN` | `embedding_service.py:66-75` builds an operation key from operation name, model, input hash, prompt hash, and config hash; `embedding_service.py:76-99` returns cache hits or records cost. | Fresh counts: `embeddings=254`, `cost_operations=254`; second run kept the same count. |
| Redis/RQ worker path exists and runs | `PROVEN` | `rq_worker.py:27-73` enqueues RQ jobs; `rq_worker.py:76-99` runs local embedding jobs; `rq_worker.py:102-111` starts a `SimpleWorker`. | Fresh first run: `rq worked=true succeeded=5 failed=0 pending=0`. |
| OpenAI embedding path exists but is fail-closed | `PARTIAL` | `rq_worker.py:128-142` requires `WZKF_OPENAI_API_KEY` for OpenAI and raises if absent. | Tests cover adapter behavior, but acceptance used mock embeddings. Live OpenAI billing/API execution is `NOT_PROVEN`. |
| Evidence-bound claims are structurally enforced | `PROVEN` | `claims.py:15-19` rejects claim extraction with neither evidence IDs nor abstain reason. | Fresh counts: `claims=5`; claim tests passed. |
| Postgres hybrid retrieval is implemented | `PROVEN FOR MVP` | `repositories.py:445-497` uses `websearch_to_tsquery`, `to_tsvector`, and pgvector `<=>`; `repositories.py:133-167` maps rows into `SearchResult`. | CLI search returned scored rows; API search status was 200 with 10 results. |
| Retrieval is production-grade | `NOT_PROVEN` | Code has MVP scoring, not a reranker, not a scale benchmark, not relevance evaluation. | Acceptance proves only a small local live search. |
| Context packs include citations and abstain on no evidence | `PROVEN` | `context_pack.py:33-65` sorts results, includes child/parent/document/source/hash fields, and sets `abstain` when no chunks exist. | CLI context pack had `abstain=false`, 10 child chunks, and citations with hashes. |
| FastAPI search/context endpoints exist | `PROVEN` | `api/main.py:41-72` defines `/context-packs` and `/search`; `api/main.py:130-150` routes to live Postgres when a DB URL is configured. | Acceptance wrote API artifacts with `search_status=200`, `context_status=200`, `search_result_count=10`. |
| API server deployment is proven | `NOT_PROVEN` | Code defines FastAPI app; acceptance uses `TestClient`. | No long-running Uvicorn deployment, ingress, auth, TLS, or hosted health check was proven. |
| Obsidian insight export excludes raw transcripts | `PROVEN` | `obsidian.py:80-99` renders insight note frontmatter with `raw_transcript_exported: false`; `obsidian.py:109-127` does the same for concept notes. | Fresh run produced six notes. |
| Obsidian changed-only hash ledger exists | `PROVEN` | `obsidian.py:48-58` hashes note body, checks `.export-ledger.json`, and skips unchanged notes when `changed_only=True`. | Second live-small run preserved counts and hash. |
| End-to-end local MVP is passing | `PROVEN` | Acceptance script lines `52-286` encode the full check sequence and final summary. | Fresh exit code 0 with `acceptance_status=PASS`. |

## Exact Code Snippets And What They Prove

### 1. The live-small CLI cannot pretend to be live without a database

File:
`<wzkf-root>/src/wzkf/cli.py:457`

```python
resolved_database_url = _database_url(database_url)
if not resolved_database_url:
    typer.echo("ABSTAIN: live-small smoke requires --database-url or DATABASE_URL")
    raise typer.Exit(code=1)
```

Evidence meaning:

- The smoke path is fail-closed.
- Without `--database-url` or `DATABASE_URL`, it exits with `ABSTAIN`.
- The acceptance run therefore had to provide a real DB URL to pass.

### 2. The acceptance script creates a fresh isolated database and validates schema

File:
`<wzkf-root>/scripts/run_live_mvp_acceptance.sh:84`

```bash
conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db_name)))
conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
```

File:
`<wzkf-root>/scripts/run_live_mvp_acceptance.sh:107`

```python
expected = [
    "sources", "documents", "raw_artifacts", "parent_chunks", "child_chunks",
    "embeddings", "concepts", "concept_aliases", "claims", "jobs", "costs",
    "context_packs",
]
```

Evidence meaning:

- The run is isolated per timestamp.
- It does not merely reuse an old DB.
- It verifies expected tables after migration.

Fresh output:

```text
created_database=wzkf_acceptance_1782845571
expected_missing=none
extensions=plpgsql,vector
alembic_version=0002_live_mvp_schema
```

### 3. Live-small harvests live sources

File:
`<wzkf-root>/src/wzkf/smoke/live_small.py:293`

```python
rss_xml = fetch_text(config.podcast_rss_url, None, None)
episode = PodcastRssHarvester().harvest_first_episode(...)
if episode.selected_artifact_type != "transcript":
    raise LiveSmallSmokeError("podcast smoke requires an authorized transcript URL")
transcript_text = fetch_text(episode.selected_artifact_url, None, None)
```

File:
`<wzkf-root>/src/wzkf/smoke/live_small.py:311`

```python
arxiv_xml = fetch_text(config.arxiv_api_url, None, None)
arxiv_records = ArxivAtomHarvester(...).parse(arxiv_xml)
```

File:
`<wzkf-root>/src/wzkf/smoke/live_small.py:338`

```python
commit_hash = clone_repo(config.github_repo_url, repo_root)
harvested_repo = GitHubRepoHarvester().harvest_local_repo(...)
```

Evidence meaning:

- The smoke path is not only fixture ingestion.
- It fetches a real RSS document and transcript URL.
- It fetches a real arXiv Atom response.
- It uses OpenAlex/Crossref metadata requests.
- It clones a real GitHub repository.

Runtime proof:

```json
"retrieval_methods": {
  "academic_metadata_api": 2,
  "arxiv_atom": 1,
  "github_clone": 1,
  "podcast_rss_transcript": 1
}
```

### 4. RQ is a real Redis/RQ path

File:
`<wzkf-root>/src/wzkf/jobs/rq_worker.py:52`

```python
rq_job_id = f"wzkf-embed-{local_job.id}"
queue = Queue(queue_name, connection=Redis.from_url(redis_url))
rq_job = queue.fetch_job(rq_job_id)
```

File:
`<wzkf-root>/src/wzkf/jobs/rq_worker.py:57`

```python
rq_job = queue.enqueue(
    run_embedding_job,
    str(root),
    local_job.id,
    provider,
    model,
    job_id=rq_job_id,
    result_ttl=86400,
    failure_ttl=86400,
)
```

File:
`<wzkf-root>/src/wzkf/jobs/rq_worker.py:108`

```python
connection = Redis.from_url(redis_url)
queue = Queue(queue_name, connection=connection)
worker = SimpleWorker([queue], connection=connection)
return worker.work(burst=burst, max_jobs=max_jobs)
```

Evidence meaning:

- This is not just an in-process list.
- It uses `redis.Redis`, `rq.Queue`, and `rq.SimpleWorker`.

Runtime proof:

```text
Worker ... Listening on wzkf-acceptance-1782845571...
Successfully completed wzkf.jobs.rq_worker.run_embedding_job(...)
rq worked=true succeeded=5 failed=0 pending=0
```

### 5. Search is backed by Postgres FTS and pgvector

File:
`<wzkf-root>/src/wzkf/db/repositories.py:445`

```sql
WITH query_input AS (
    SELECT
        websearch_to_tsquery('english', :query) AS ts_query,
        CAST(:query_embedding AS vector) AS query_embedding
)
```

File:
`<wzkf-root>/src/wzkf/db/repositories.py:462`

```sql
ts_rank(
    to_tsvector('english', child_chunks.text),
    query_input.ts_query
) AS text_score
```

File:
`<wzkf-root>/src/wzkf/db/repositories.py:466`

```sql
CASE
    WHEN embeddings.embedding_vector IS NULL THEN 0.0
    ELSE 1.0 - (embeddings.embedding_vector <=> query_input.query_embedding)
END AS vector_score
```

Evidence meaning:

- Search is not a placeholder.
- It uses Postgres full-text ranking and pgvector distance.
- It returns child chunk, parent chunk, document, source URL, text score,
  vector score, final score, and chunk hash.

Runtime proof:

```text
5.21  01775005d41a5e031fbfbcf5  e44946b8ce03e1b66cc11173  https://openalex.org/W2088503847
4.81  01775005d41a5e031fbfbcf5  1954f67b29ed1bbd168be898  https://openalex.org/W2088503847
4.81  86fa09593a49e5795490f7a9  7cd70d4ff5c5b63b9a618200  https://share.transistor.fm/s/6b6fe1af
```

### 6. Claims cannot be accepted without evidence or abstention

File:
`<wzkf-root>/src/wzkf/extraction/claims.py:15`

```python
@model_validator(mode="after")
def require_evidence_or_abstain(self) -> "ClaimExtractionV1":
    if not self.evidence_child_chunk_ids and not self.abstain_reason:
        raise ValueError("extracted claims require evidence_child_chunk_ids or an abstain_reason")
    return self
```

Evidence meaning:

- The claim model structurally enforces the evidence/ABSTAIN invariant.
- It does not prove semantic truth of claims, but it prevents unsupported claim
  objects from being structurally valid.

Runtime proof:

```text
claims=5
```

### 7. Context packs carry citations and abstain when search has no chunks

File:
`<wzkf-root>/src/wzkf/retrieval/context_pack.py:33`

```python
ordered = sorted(results, key=lambda item: (-item.score, item.child_chunk_id))
chunks = [
    ContextChunk(
        child_chunk_id=item.child_chunk_id,
        parent_chunk_id=item.parent_chunk_id,
        document_id=item.document_id,
        source_title=item.source_title,
        source_url=item.source_url,
        text=item.parent_text or item.text,
        child_text=item.text,
        chunk_hash=item.chunk_hash,
    )
    for item in ordered
]
abstain = not chunks
```

Evidence meaning:

- Context packs are evidence carriers, not free-form summaries.
- The output includes child chunk IDs, parent chunk IDs, document IDs, source
  URLs, and chunk hashes.
- Empty evidence produces `abstain=true`.

Runtime proof:

```text
cli_context_abstain=false
cli_context_child_count=10
cli_context_citation_1=doc:01775005d41a5e031fbfbcf5 child:e44946b8ce03e1b66cc11173 source:https://openalex.org/W2088503847 hash:03313c917f6c3e947f7528477b0b630c924dfc8a81996b0cc120b105c36f24ea
```

### 8. Obsidian export intentionally excludes raw transcripts

File:
`<wzkf-root>/src/wzkf/export/obsidian.py:80`

```python
return (
    "---\n"
    f"type: {insight.note_type}\n"
    ...
    "raw_transcript_exported: false\n"
```

File:
`<wzkf-root>/src/wzkf/export/obsidian.py:109`

```python
return (
    "---\n"
    "type: concept\n"
    ...
    "raw_transcript_exported: false\n"
```

Evidence meaning:

- Obsidian is an insight export layer.
- Raw transcripts are not exported by default.

Runtime proof:

```text
obsidian_notes=6
```

## What Is Proven By Tests

The fresh acceptance run executed every test in
`<wzkf-root>/tests`.

```text
tests/test_academic_metadata.py ...
tests/test_academic_metadata_clients.py ...
tests/test_alembic_config.py ..
tests/test_api.py .....
tests/test_claims.py ..
tests/test_cli_help.py ..............
tests/test_concept_alias_resolution.py ..
tests/test_context_pack.py ...
tests/test_cost_cache.py .
tests/test_db_repository.py ....
tests/test_db_schema.py ...
tests/test_fixture_ingestion.py .
tests/test_fixture_paper_repo_ingestion.py .......
tests/test_harvesters.py ....
tests/test_hashing_storage.py ...
tests/test_jobs_and_services.py ....
tests/test_live_small_smoke.py ..
tests/test_local_pipeline.py ..
tests/test_obsidian_export.py ..
tests/test_ontology_store.py ..
tests/test_openai_embedding_provider.py ...
tests/test_parent_child_chunking.py ..
tests/test_postgres_retrieval_sql.py .
tests/test_rights_gate.py ...
tests/test_rq_worker.py ....
tests/test_search_pipeline.py ..
tests/test_source_registry.py ..
tests/test_structured_extraction.py ..

88 passed, 1 warning in 1.78s
```

This proves the unit and local integration behavior represented by those tests.
It does not prove untested production behavior.

## What Is Still Fixture Or Mock Backed

These are honest boundaries. They are not failures of the local MVP, but they
must not be overstated.

| Layer | Current status | Boundary |
| --- | --- | --- |
| Embeddings | Mock provider used in acceptance | Live paid OpenAI embedding execution is `NOT_PROVEN`. |
| LLM extraction | Deterministic/evidence-bound MVP extraction | Production LLM extraction quality is `NOT_PROVEN`. |
| API | FastAPI app exercised through `TestClient` | Long-running hosted API server is `NOT_PROVEN`. |
| Retrieval relevance | Postgres FTS + pgvector returns cited results | Production-grade ranking, reranking, benchmark relevance, and scale are `NOT_PROVEN`. |
| Corpus breadth | Five live-small documents | Large-scale ingestion across all listed podcasts, repos, papers, and datasets is `NOT_PROVEN`. |
| Reuters/LSEG | Rights policy gates exist | Licensed current Reuters/LSEG full-text ingestion is `NOT_PROVEN` and should remain blocked unless a license is configured. |
| Docker deployment | Local Docker Compose works | Production deployment, health checks, resource limits, persistence policy, auth, TLS, and monitoring are `NOT_PROVEN`. |
| Security | Repo harvester skips secret-like filenames | Full secret scanning of cloned repos is `NOT_PROVEN`. |

## Precise Answer To "What Exactly Did We Build?"

We built and verified a new `wz-knowledge-fabric` Python package with 120 staged
files and 12,854 staged insertions at the time this proof was prepared. The
active package is `wzkf`, not the older `wzk` path referenced in the attachment.

The built system has these executable surfaces:

```text
wzkf sources validate
wzkf ingest ...
wzkf process ...
wzkf search ...
wzkf context-pack ...
wzkf export obsidian ...
wzkf jobs ...
wzkf costs ...
wzkf ontology ...
wzkf smoke live-small
```

The strongest proven command is:

```bash
cd <wzkf-root>
scripts/run_live_mvp_acceptance.sh
```

The strongest proven artifact is:

```text
<acceptance-run-root>/acceptance-summary.json
```

The strongest repo-contained proof script is:

```text
<wzkf-root>/scripts/run_live_mvp_acceptance.sh
```

The strongest source-code proof points are:

```text
<wzkf-root>/src/wzkf/smoke/live_small.py
<wzkf-root>/src/wzkf/db/repositories.py
<wzkf-root>/src/wzkf/jobs/rq_worker.py
<wzkf-root>/src/wzkf/api/main.py
<wzkf-root>/src/wzkf/export/obsidian.py
<wzkf-root>/src/wzkf/extraction/claims.py
```

## Final Claim Boundaries

### Safe To Claim

```text
The current checkout contains a working WZ Knowledge Fabric local live MVP.
It passes the repository acceptance script against Docker Postgres/pgvector and
Redis/RQ. It ingests a five-document live-small corpus, persists provenance,
chunks, embeddings, claims, costs, and context packs, exposes search/context
through CLI and FastAPI paths, exports six Obsidian insight/concept notes, and
proves idempotency across two consecutive live-small runs.
```

### Not Safe To Claim

```text
The system is production-grade.
The system is ready for hosted users.
The system has proven paid OpenAI embedding execution.
The system has proven large-corpus ingestion.
The search quality is production-grade.
The API is deployed.
The pipeline has production observability, auth, TLS, resource limits, or HA.
The system can ingest licensed Reuters/LSEG full text without a configured license.
The extracted claims are semantically true beyond the evidence-bound structural checks.
```

## Bottom Line

The accurate current status is:

```text
WZKF-LIVE-LOCAL-MVP: PROVEN
PRODUCTION-GRADE-WZKF: NOT_PROVEN
LIVE-OPENAI-COSTED-EMBEDDINGS: NOT_PROVEN
BROAD-SCALE-CORPUS-INGESTION: NOT_PROVEN
```
