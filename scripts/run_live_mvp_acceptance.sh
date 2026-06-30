#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="${WZKF_ACCEPTANCE_STAMP:-$(date +%s)}"
RUN_ROOT="${WZKF_ACCEPTANCE_ROOT:-/tmp/wzkf-live-mvp-acceptance-${STAMP}}"
DB_NAME="${WZKF_ACCEPTANCE_DB:-wzkf_acceptance_${STAMP}}"
DB_URL="postgresql+psycopg://wzkf:wzkf@localhost:5432/${DB_NAME}"
DB_PLAIN_URL="postgresql://wzkf:wzkf@localhost:5432/${DB_NAME}"
ADMIN_DB_URL="${WZKF_ACCEPTANCE_ADMIN_DB_URL:-postgresql://wzkf:wzkf@localhost:5432/postgres}"
REDIS_URL="${WZKF_ACCEPTANCE_REDIS_URL:-redis://localhost:6379/0}"
QUEUE_NAME="${WZKF_ACCEPTANCE_QUEUE:-wzkf-acceptance-${STAMP}}"
UV_BIN="${WZKF_UV_BIN:-}"

if [[ -z "$UV_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/uv" ]]; then
    UV_BIN="$ROOT/.venv/bin/uv"
  else
    UV_BIN="uv"
  fi
fi

LOG_PATH="${RUN_ROOT}/acceptance.log"
SUMMARY_PATH="${RUN_ROOT}/acceptance-summary.json"
STORAGE_ROOT="${RUN_ROOT}/live-small-storage"
FIRST_EVIDENCE="${RUN_ROOT}/first-live-small-smoke.json"
SECOND_EVIDENCE="${RUN_ROOT}/second-live-small-smoke.json"
CLI_CONTEXT_PACK="${RUN_ROOT}/cli-context-pack.json"

mkdir -p "$RUN_ROOT"
: > "$LOG_PATH"

log() {
  printf '%s\n' "$*" | tee -a "$LOG_PATH"
}

run() {
  log ""
  log "COMMAND: $*"
  "$@" 2>&1 | tee -a "$LOG_PATH"
}

log "WZKF live MVP acceptance run"
log "run_root=${RUN_ROOT}"
log "database=${DB_NAME}"
log "storage_root=${STORAGE_ROOT}"
log "redis_url=${REDIS_URL}"
log "queue_name=${QUEUE_NAME}"

run "$UV_BIN" run pytest
run "$UV_BIN" run wzkf sources validate

run docker compose up -d
run docker compose ps

log ""
log "COMMAND: ${UV_BIN} run python - <<'PY'  # wait for Postgres/Redis"
"$UV_BIN" run python - <<PY 2>&1 | tee -a "$LOG_PATH"
from time import sleep, monotonic
import psycopg
import redis

admin_url = "${ADMIN_DB_URL}"
redis_url = "${REDIS_URL}"
deadline = monotonic() + 60
last_error = None
while monotonic() < deadline:
    try:
        with psycopg.connect(admin_url) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                print("postgres_select_1=" + str(cur.fetchone()[0]))
        print("redis_ping=" + str(redis.Redis.from_url(redis_url).ping()).lower())
        break
    except Exception as exc:
        last_error = exc
        sleep(2)
else:
    raise SystemExit(f"services not ready: {last_error}")
PY

log ""
log "COMMAND: ${UV_BIN} run python - <<'PY'  # create isolated database"
"$UV_BIN" run python - <<PY 2>&1 | tee -a "$LOG_PATH"
import psycopg
from psycopg import sql

admin_url = "${ADMIN_DB_URL}"
db_name = "${DB_NAME}"
with psycopg.connect(admin_url, autocommit=True) as conn:
    conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db_name)))
    conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
print("created_database=" + db_name)
PY

log ""
log "COMMAND: DATABASE_URL=${DB_URL} ${UV_BIN} run alembic upgrade head"
DATABASE_URL="$DB_URL" "$UV_BIN" run alembic upgrade head 2>&1 | tee -a "$LOG_PATH"

log ""
log "COMMAND: ${UV_BIN} run python - <<'PY'  # verify migrated schema"
"$UV_BIN" run python - <<PY 2>&1 | tee -a "$LOG_PATH"
import psycopg

expected = [
    "sources", "documents", "raw_artifacts", "parent_chunks", "child_chunks",
    "embeddings", "concepts", "concept_aliases", "claims", "jobs", "costs",
    "context_packs",
]
with psycopg.connect("${DB_PLAIN_URL}") as conn:
    with conn.cursor() as cur:
        cur.execute("select tablename from pg_tables where schemaname='public' order by tablename")
        tables = [row[0] for row in cur.fetchall()]
        missing = [name for name in expected if name not in tables]
        print("tables=" + ",".join(tables))
        print("expected_missing=" + (",".join(missing) if missing else "none"))
        cur.execute("select extname from pg_extension order by extname")
        print("extensions=" + ",".join(row[0] for row in cur.fetchall()))
        cur.execute("select version_num from alembic_version")
        print("alembic_version=" + cur.fetchone()[0])
        if missing:
            raise SystemExit("schema missing expected tables")
PY

run "$UV_BIN" run wzkf smoke live-small \
  --database-url "$DB_URL" \
  --storage-root "$STORAGE_ROOT" \
  --use-rq \
  --redis-url "$REDIS_URL" \
  --queue-name "$QUEUE_NAME"
cp "${STORAGE_ROOT}/evidence/live-small-smoke.json" "$FIRST_EVIDENCE"

run "$UV_BIN" run wzkf smoke live-small \
  --database-url "$DB_URL" \
  --storage-root "$STORAGE_ROOT" \
  --use-rq \
  --redis-url "$REDIS_URL" \
  --queue-name "$QUEUE_NAME"
cp "${STORAGE_ROOT}/evidence/live-small-smoke.json" "$SECOND_EVIDENCE"

run "$UV_BIN" run wzkf search "limit order book market depth" \
  --database-url "$DB_URL" \
  --embedding-model mock-hash-embedding-v1 \
  --limit 3

log ""
log "COMMAND: ${UV_BIN} run wzkf context-pack ... > ${CLI_CONTEXT_PACK}"
"$UV_BIN" run wzkf context-pack "limit order book market depth" \
  --database-url "$DB_URL" \
  --embedding-model mock-hash-embedding-v1 \
  --limit 10 > "$CLI_CONTEXT_PACK"

log ""
log "COMMAND: ${UV_BIN} run python - <<'PY'  # summarize CLI context pack"
"$UV_BIN" run python - <<PY 2>&1 | tee -a "$LOG_PATH"
import json
from pathlib import Path

context_pack = json.loads(Path("${CLI_CONTEXT_PACK}").read_text())
print("cli_context_abstain=" + str(context_pack.get("abstain")).lower())
print("cli_context_pack_hash=" + str(context_pack.get("pack_hash")))
print("cli_context_child_count=" + str(len(context_pack.get("included_child_chunk_ids", []))))
for index, citation in enumerate(context_pack.get("included_chunks", [])[:3], start=1):
    print(
        f"cli_context_citation_{index}=doc:{citation.get('document_id')} "
        f"child:{citation.get('child_chunk_id')} "
        f"source:{citation.get('source_url')} "
        f"hash:{citation.get('chunk_hash')}"
    )
PY

log ""
log "COMMAND: ${UV_BIN} run python - <<'PY'  # final acceptance assertions"
"$UV_BIN" run python - <<PY 2>&1 | tee -a "$LOG_PATH"
import json
from pathlib import Path
import psycopg

run_root = Path("${RUN_ROOT}")
storage = Path("${STORAGE_ROOT}")
first = json.loads(Path("${FIRST_EVIDENCE}").read_text())
second = json.loads(Path("${SECOND_EVIDENCE}").read_text())
context_pack = json.loads(Path("${CLI_CONTEXT_PACK}").read_text())

required_equal = [
    "document_count",
    "raw_artifact_count",
    "child_chunk_count",
    "embedding_count",
    "cost_operations",
    "context_pack_hash",
]
for key in required_equal:
    if first[key] != second[key]:
        raise SystemExit(f"idempotency mismatch for {key}: {first[key]} != {second[key]}")
if not second.get("rq_used"):
    raise SystemExit("live-small smoke did not use RQ")
if second.get("rq_failed") != 0 or second.get("rq_pending") != 0:
    raise SystemExit("RQ jobs did not finish cleanly")
if second.get("rq_succeeded", 0) < 5:
    raise SystemExit("expected at least 5 succeeded RQ jobs")
if context_pack.get("abstain"):
    raise SystemExit("CLI context pack abstained")
if not context_pack.get("included_child_chunk_ids"):
    raise SystemExit("CLI context pack has no cited child chunks")

obsidian_notes = sorted(path.name for path in (storage / "obsidian_export").glob("*.md"))
if len(obsidian_notes) < 5:
    raise SystemExit("expected at least 5 Obsidian insight/concept notes")

counts = {}
retrieval_methods = {}
with psycopg.connect("${DB_PLAIN_URL}") as conn:
    with conn.cursor() as cur:
        for table in [
            "documents", "raw_artifacts", "parent_chunks", "child_chunks",
            "embeddings", "concepts", "concept_aliases", "claims", "jobs",
            "costs", "context_packs",
        ]:
            cur.execute(f"select count(*) from {table}")
            counts[table] = int(cur.fetchone()[0])
        cur.execute("select retrieval_method, count(*) from raw_artifacts group by retrieval_method order by retrieval_method")
        retrieval_methods = {method: int(count) for method, count in cur.fetchall()}

expected_methods = {
    "academic_metadata_api": 2,
    "arxiv_atom": 1,
    "github_clone": 1,
    "podcast_rss_transcript": 1,
}
if retrieval_methods != expected_methods:
    raise SystemExit(f"unexpected retrieval methods: {retrieval_methods}")

summary = {
    "status": "PASS",
    "run_root": str(run_root),
    "database": "${DB_NAME}",
    "database_url": "${DB_URL}",
    "storage_root": str(storage),
    "log_path": "${LOG_PATH}",
    "first_evidence_path": "${FIRST_EVIDENCE}",
    "second_evidence_path": "${SECOND_EVIDENCE}",
    "context_pack_path": "${CLI_CONTEXT_PACK}",
    "db_counts": counts,
    "retrieval_methods": retrieval_methods,
    "source_urls": second["source_urls"],
    "document_ids": second["document_ids"],
    "context_pack_hash": second["context_pack_hash"],
    "cost_operations": second["cost_operations"],
    "rq": {
        "used": second["rq_used"],
        "worked_first_run": first["rq_worked"],
        "worked_second_run": second["rq_worked"],
        "succeeded": second["rq_succeeded"],
        "failed": second["rq_failed"],
        "pending": second["rq_pending"],
    },
    "api": {
        "search_status": second["api_search_status"],
        "search_result_count": second["api_search_result_count"],
        "context_status": second["api_context_status"],
        "context_pack_hash": second["api_context_pack_hash"],
    },
    "obsidian_notes": obsidian_notes,
}
Path("${SUMMARY_PATH}").write_text(json.dumps(summary, sort_keys=True, indent=2), encoding="utf-8")
print("acceptance_status=PASS")
print("summary_path=${SUMMARY_PATH}")
print("log_path=${LOG_PATH}")
print("db_counts=" + json.dumps(counts, sort_keys=True))
print("retrieval_methods=" + json.dumps(retrieval_methods, sort_keys=True))
print("source_urls=" + " | ".join(second["source_urls"]))
print("context_pack_hash=" + second["context_pack_hash"])
print("cost_operations=" + str(second["cost_operations"]))
print("rq_used=" + str(second["rq_used"]).lower())
print("rq_succeeded=" + str(second["rq_succeeded"]))
print("rq_failed=" + str(second["rq_failed"]))
print("rq_pending=" + str(second["rq_pending"]))
print("obsidian_notes=" + str(len(obsidian_notes)))
PY

log ""
log "ACCEPTANCE SUMMARY"
cat "$SUMMARY_PATH" | tee -a "$LOG_PATH"
