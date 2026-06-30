# WZKF Live MVP Phase 4 Redis/RQ Evidence

Date: 2026-06-30
Workspace: `<weightiz-workspace>`
Project: `<wzkf-root>`

## Status

**PARTIAL**

Phase 4 is now implemented and locally proven for mock embedding jobs:

- enqueue into Redis/RQ
- execute with an RQ burst worker
- update local job state
- write embeddings
- write cost ledger once
- rerun without duplicate cost
- fail closed into local `FAILED` state when a requested provider cannot start

This does **not** prove live paid OpenAI embedding execution. The OpenAI path was
proven only as fail-closed when `WZKF_OPENAI_API_KEY` is missing.

## Files Changed

- `<wzkf-root>/src/wzkf/jobs/rq_worker.py`
- `<wzkf-root>/src/wzkf/jobs/queue.py`
- `<wzkf-root>/src/wzkf/jobs/runner.py`
- `<wzkf-root>/src/wzkf/cli.py`
- `<wzkf-root>/tests/test_rq_worker.py`
- `<wzkf-root>/tests/test_cli_help.py`
- `<wzkf-root>/README.md`

## Test Evidence

Command:

```bash
.venv/bin/uv run pytest tests/test_rq_worker.py tests/test_cli_help.py::test_cli_jobs_enqueue_rq_reports_local_and_rq_ids tests/test_cli_help.py::test_cli_jobs_work_rq_reports_worker_result
```

Output:

```text
collected 6 items
tests/test_rq_worker.py ....                                             [ 66%]
tests/test_cli_help.py ..                                                [100%]
============================== 6 passed in 1.28s ===============================
```

Command:

```bash
.venv/bin/uv run pytest
```

Output:

```text
collected 83 items
...
======================== 83 passed, 1 warning in 2.75s =========================
```

Command:

```bash
.venv/bin/uv run wzkf sources validate
```

Output:

```text
sources.yaml valid: 16 sources
```

## Live Redis/RQ Command Sequence

Command summary:

```bash
queue="wzkf-embeddings-live-1782830090"
storage="<rq-success-run-root>"
failure_storage="<rq-failure-run-root>"
docker compose up -d
.venv/bin/uv run wzkf ingest podcast --source signals_threads --fixture tests/fixtures/signals_threads/episode.html --storage-root "$storage"
.venv/bin/uv run wzkf jobs enqueue-rq --document-id "$doc_id" --redis-url redis://localhost:6379/0 --queue-name "$queue" --storage-root "$storage"
.venv/bin/uv run wzkf jobs work-rq --redis-url redis://localhost:6379/0 --queue-name "$queue" --burst --max-jobs 1
.venv/bin/uv run wzkf jobs status --storage-root "$storage"
.venv/bin/uv run wzkf costs report --storage-root "$storage"
```

Runtime setup output:

```text
rq_queue=wzkf-embeddings-live-1782830090
success_storage=<rq-success-run-root>
failure_storage=<rq-failure-run-root>
Container wz-knowledge-fabric-postgres-1 Running
Container wz-knowledge-fabric-redis-1 Running
redis_ping=true
```

Successful enqueue output:

```text
ingested signals_threads:Expect Tests for Trading Infrastructure
success_document_id=4081bbfe7795003f7b88d595
rq enqueued local_job_id=f8e8d0789d4167ba1a4fe40ada2e61e2 rq_job_id=wzkf-embed-f8e8d0789d4167ba1a4fe40ada2e61e2 created=true
```

Successful worker output:

```text
wzkf-embeddings-live-1782830090: wzkf.jobs.rq_worker.run_embedding_job('<rq-success-run-root>', 'f8e8d0789d4167ba1a4fe40ada2e61e2', 'mock', 'mock-hash-embedding-v1') (wzkf-embed-f8e8d0789d4167ba1a4fe40ada2e61e2)
Successfully completed wzkf.jobs.rq_worker.run_embedding_job('<rq-success-run-root>', 'f8e8d0789d4167ba1a4fe40ada2e61e2', 'mock', 'mock-hash-embedding-v1') job in 0:00:00.002905s
rq worker queue=wzkf-embeddings-live-1782830090 burst=true worked=true
jobs total=1 pending=0 running=0 succeeded=1 failed=0 skipped=0 abstained=0
costs operations=1 estimated_cost_usd=0.000000
success_embedding_count=1
success_cost_operations=1
```

Rerun idempotency output:

```text
rq enqueued local_job_id=f8e8d0789d4167ba1a4fe40ada2e61e2 rq_job_id=wzkf-embed-f8e8d0789d4167ba1a4fe40ada2e61e2 created=false
rq worker queue=wzkf-embeddings-live-1782830090 burst=true worked=false
jobs total=1 pending=0 running=0 succeeded=1 failed=0 skipped=0 abstained=0
costs operations=1 estimated_cost_usd=0.000000
rerun_embedding_count=1
rerun_cost_operations=1
```

Fail-closed provider output:

```text
failure_document_id=4081bbfe7795003f7b88d595
rq enqueued local_job_id=9da22a8245b162f6ddae82ce3b241707 rq_job_id=wzkf-embed-9da22a8245b162f6ddae82ce3b241707 created=true
wzkf-embeddings-live-1782830090-failure: wzkf.jobs.rq_worker.run_embedding_job('<rq-failure-run-root>', '9da22a8245b162f6ddae82ce3b241707', 'openai', 'text-embedding-3-small') (wzkf-embed-9da22a8245b162f6ddae82ce3b241707)
rq worker queue=wzkf-embeddings-live-1782830090-failure burst=true worked=true
jobs total=1 pending=0 running=0 succeeded=0 failed=1 skipped=0 abstained=0
failure_job_id=9da22a8245b162f6ddae82ce3b241707
failure_status=FAILED
failure_error=openai embedding provider requires api_key
```

## What Is Proven

- Redis was reachable: `redis_ping=true`.
- RQ accepted a deterministic job ID: `wzkf-embed-f8e8d0789d4167ba1a4fe40ada2e61e2`.
- RQ burst worker executed the embedding task.
- The local job state moved from pending to succeeded.
- One embedding was written for the one child chunk in the fixture document.
- One cost operation was written.
- Re-enqueue returned `created=false`.
- Re-running the worker did not create a new cost operation.
- The OpenAI worker path fails closed without a runtime API key and marks the
  local job `FAILED`.

## What Is Not Proven

- Live OpenAI embedding execution with a real runtime key.
- Redis/RQ retry scheduling with multiple retry attempts.
- Live Postgres-backed ingestion jobs.
- Phase 5 real source smoke.

## Blockers

No blocker for the mock Redis/RQ worker path. Remaining work is Phase 5 and the
single acceptance command sequence.

## Next Patch

Run the Phase 5 small live ingestion smoke with legal sources only: one podcast
RSS/transcript, three academic metadata records, and one GitHub repository at a
fixed commit.
