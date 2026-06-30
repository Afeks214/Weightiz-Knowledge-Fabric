# WZKF Live MVP Phase 2/3 Evidence

Date: 2026-06-30
Workspace: `<weightiz-workspace>`
Project: `<wzkf-root>`

## Status

**PARTIAL**

Phase 2 is now materially upgraded: live Postgres migration applies the
canonical `jobs` and `costs` tables, installs pgvector, and exposes
`embeddings.embedding_vector`.

Phase 3 is further upgraded: Postgres full-text plus pgvector retrieval is wired
through repository, CLI, and FastAPI search/context-pack paths when a database
URL is configured. The local manifest path remains the default fallback, so this
is still not a full live MVP.

## Evidence

### Tests

Command:

```bash
.venv/bin/uv run pytest
```

Output:

```text
collected 77 items
...
======================== 77 passed, 1 warning in 31.19s ========================
```

### Source Registry

Command:

```bash
.venv/bin/uv run wzkf sources validate
```

Output:

```text
sources.yaml valid: 16 sources
```

### Docker And Connectivity

During the live CLI/API proof, Docker Desktop entered a bad state: Docker server
API calls and Postgres client connections timed out. The runtime was force
restarted and recovered.

Recovery command output:

```text
docker_wait_1=rc1 stderr=failed to connect to the docker API at unix://<docker-socket>; check if the path is correct and if the daemon is running: dial unix <user-home>/.docker/run/docker.sock: connect: no such file or directory
docker_ready_after=4s server_version=29.4.3
```

Compose and migration recovery output:

```text
Container wz-knowledge-fabric-postgres-1 Started
Container wz-knowledge-fabric-redis-1 Started
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
alembic_version=0002_live_mvp_schema
extensions=plpgsql,vector
redis_ping=true
```

Command:

```bash
DOCKER_API_VERSION=1.43 docker compose ps
```

Output:

```text
NAME                             IMAGE                    COMMAND                  SERVICE    CREATED          STATUS          PORTS
wz-knowledge-fabric-postgres-1   pgvector/pgvector:pg16   "docker-entrypoint.s..."   postgres   16 minutes ago   Up 16 minutes   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
wz-knowledge-fabric-redis-1      redis:7-alpine           "docker-entrypoint.s..."   redis      16 minutes ago   Up 16 minutes   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
```

Command:

```bash
.venv/bin/python - <<'PY'
import psycopg, redis
with psycopg.connect('postgresql://wzkf:wzkf@localhost:5432/wzkf') as conn:
    with conn.cursor() as cur:
        cur.execute('select 1')
        print('postgres_select_1=' + str(cur.fetchone()[0]))
print('redis_ping=' + str(redis.Redis(host='localhost', port=6379).ping()).lower())
PY
```

Output:

```text
postgres_select_1=1
redis_ping=true
```

### Live Alembic Migration

Command:

```bash
DATABASE_URL=postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf .venv/bin/uv run alembic upgrade head
```

Output:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 0001_initial -> 0002_live_mvp_schema, live MVP schema compatibility
```

### Live Schema Verification

Command:

```bash
.venv/bin/python - <<'PY'
import psycopg
expected = [
    'sources', 'documents', 'raw_artifacts', 'parent_chunks', 'child_chunks',
    'embeddings', 'concepts', 'concept_aliases', 'claims', 'jobs', 'costs',
    'context_packs',
]
with psycopg.connect('postgresql://wzkf:wzkf@localhost:5432/wzkf') as conn:
    with conn.cursor() as cur:
        cur.execute("select tablename from pg_tables where schemaname='public' order by tablename")
        tables = [row[0] for row in cur.fetchall()]
        print('tables=' + ','.join(tables))
        print('expected_missing=' + (','.join(name for name in expected if name not in tables) or 'none'))
        cur.execute("select extname from pg_extension order by extname")
        print('extensions=' + ','.join(row[0] for row in cur.fetchall()))
        cur.execute("""
            select column_name, udt_name
            from information_schema.columns
            where table_schema='public' and table_name='embeddings'
            order by ordinal_position
        """)
        print('embedding_columns=' + ','.join(f'{name}:{udt}' for name, udt in cur.fetchall()))
        cur.execute('select version_num from alembic_version')
        print('alembic_version=' + cur.fetchone()[0])
PY
```

Output:

```text
tables=alembic_version,child_chunks,claims,concept_aliases,concepts,context_packs,costs,document_concepts,documents,embeddings,jobs,parent_chunks,raw_artifacts,relations,sources
expected_missing=none
extensions=plpgsql,vector
embedding_columns=id:text,child_chunk_id:text,embedding_model:text,embedding:json,created_at:timestamptz,embedding_vector:vector
alembic_version=0002_live_mvp_schema
```

### Live Postgres FTS + pgvector Retrieval

Command:

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from wzkf.db.repositories import KnowledgeRepository
engine = create_engine('postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf')
Session = sessionmaker(bind=engine)
with Session() as session:
    repo = KnowledgeRepository(session)
    results = repo.postgres_hybrid_search_child_chunks(
        query='limit order book market depth',
        query_embedding=[0.0, 1.0],
        embedding_model='test-vector',
        limit=3,
    )
    print('postgres_pgvector_fts_search_results=' + str(len(results)))
    for index, result in enumerate(results, start=1):
        print(
            f"result_{index}=child_chunk_id:{result.child_chunk_id}|"
            f"parent_chunk_id:{result.parent_chunk_id}|document_id:{result.document_id}|"
            f"source_url:{result.source_url}|chunk_hash:{result.chunk_hash}|"
            f"score:{result.score:.6f}|text_score:{result.text_score:.6f}|"
            f"vector_score:{result.vector_score:.6f}"
        )
PY
```

Output:

```text
postgres_pgvector_fts_search_results=2
result_1=child_chunk_id:61ea9369714aa0662a900599|parent_chunk_id:0cb74bb5e05cdb787800b0f7|document_id:7ff362fb5efc108aa2a87fc0|source_url:http://arxiv.org/abs/2606.30001v1|chunk_hash:46aee92ef6b1e33eaadf31ba8388cc74ee0d34844aa5bf379e196f7db30235d0|score:5.608598|text_score:0.608598|vector_score:1.000000
result_2=child_chunk_id:aaf97c84b2db2c582c74a90b|parent_chunk_id:24eae62e96f4c9b9a00d0094|document_id:4081bbfe7795003f7b88d595|source_url:https://signalsandthreads.com/example-expect-tests|chunk_hash:d47ee8b13e081e088b9e2baa14af4493714b788812a6496d5aa1550798d914d5|score:0.000000|text_score:0.000000|vector_score:0.000000
```

### Live CLI Search And Context Pack

Command:

```bash
.venv/bin/uv run wzkf search "limit order book market depth" \
  --database-url postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf \
  --embedding-model test-vector \
  --query-embedding 0,1 \
  --limit 3
```

Output:

```text
5.61    7ff362fb5efc108aa2a87fc0    61ea9369714aa0662a900599    http://arxiv.org/abs/2606.30001v1
0.00    4081bbfe7795003f7b88d595    aaf97c84b2db2c582c74a90b    https://signalsandthreads.com/example-expect-tests
```

Command:

```bash
.venv/bin/uv run wzkf context-pack "limit order book market depth" \
  --database-url postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf \
  --embedding-model test-vector \
  --query-embedding 0,1 \
  --limit 3
```

Key output:

```text
"pack_hash":"01cec606385424f06b9e783edbc8ef359cba89f2e08a57a63cf9ee2ad5ac9a6b"
"included_child_chunk_ids":["61ea9369714aa0662a900599","aaf97c84b2db2c582c74a90b"]
"source_url":"http://arxiv.org/abs/2606.30001v1"
"chunk_hash":"46aee92ef6b1e33eaadf31ba8388cc74ee0d34844aa5bf379e196f7db30235d0"
```

### Live FastAPI Search And Context Pack

Command:

```bash
.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from wzkf.api.main import create_app
client = TestClient(create_app(database_url='postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf'))
search = client.get('/search', params={
    'query': 'limit order book market depth',
    'embedding_model': 'test-vector',
    'query_embedding': '0,1',
    'limit': '3',
})
print('api_search_status=' + str(search.status_code))
body = search.json()
print('api_search_abstain=' + str(body['abstain']).lower())
print('api_search_result_count=' + str(len(body['results'])))
for index, result in enumerate(body['results'], start=1):
    print(
        f"api_result_{index}=child_chunk_id:{result['child_chunk_id']}|"
        f"parent_chunk_id:{result['parent_chunk_id']}|document_id:{result['document_id']}|"
        f"source_url:{result['source_url']}|chunk_hash:{result['chunk_hash']}|"
        f"score:{result['score']:.6f}|text_score:{result['text_score']:.6f}|"
        f"vector_score:{result['vector_score']:.6f}"
    )
pack = client.post('/context-packs', json={
    'query': 'limit order book market depth',
    'created_for': 'api-live-proof',
    'embedding_model': 'test-vector',
    'query_embedding': '0,1',
    'limit': 3,
})
print('api_context_pack_status=' + str(pack.status_code))
pack_body = pack.json()
print('api_context_pack_abstain=' + str(pack_body['abstain']).lower())
print('api_context_pack_child_ids=' + ','.join(pack_body['included_child_chunk_ids']))
print('api_context_pack_hash=' + pack_body['pack_hash'])
PY
```

Output:

```text
api_search_status=200
api_search_abstain=false
api_search_result_count=2
api_result_1=child_chunk_id:61ea9369714aa0662a900599|parent_chunk_id:0cb74bb5e05cdb787800b0f7|document_id:7ff362fb5efc108aa2a87fc0|source_url:http://arxiv.org/abs/2606.30001v1|chunk_hash:46aee92ef6b1e33eaadf31ba8388cc74ee0d34844aa5bf379e196f7db30235d0|score:5.608598|text_score:0.608598|vector_score:1.000000
api_result_2=child_chunk_id:aaf97c84b2db2c582c74a90b|parent_chunk_id:24eae62e96f4c9b9a00d0094|document_id:4081bbfe7795003f7b88d595|source_url:https://signalsandthreads.com/example-expect-tests|chunk_hash:d47ee8b13e081e088b9e2baa14af4493714b788812a6496d5aa1550798d914d5|score:0.000000|text_score:0.000000|vector_score:0.000000
api_context_pack_status=200
api_context_pack_abstain=false
api_context_pack_child_ids=61ea9369714aa0662a900599,aaf97c84b2db2c582c74a90b
api_context_pack_hash=d968ee847adb5da37e15a25face097ff2be4be154e6fa289e74419dc34c5e9c2
```

### Small Benchmark

Command:

```bash
.venv/bin/python - <<'PY'
from statistics import mean
from time import perf_counter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from wzkf.db.repositories import KnowledgeRepository
engine = create_engine('postgresql+psycopg://wzkf:wzkf@localhost:5432/wzkf')
Session = sessionmaker(bind=engine)
durations=[]
last_count=0
with Session() as session:
    repo = KnowledgeRepository(session)
    for _ in range(20):
        start=perf_counter()
        results = repo.postgres_hybrid_search_child_chunks(
            query='limit order book market depth',
            query_embedding=[0.0, 1.0],
            embedding_model='test-vector',
            limit=3,
        )
        durations.append((perf_counter()-start)*1000)
        last_count=len(results)
print('benchmark_query=limit order book market depth')
print('benchmark_iterations=20')
print('benchmark_result_count=' + str(last_count))
print('benchmark_avg_ms=' + f'{mean(durations):.3f}')
print('benchmark_min_ms=' + f'{min(durations):.3f}')
print('benchmark_max_ms=' + f'{max(durations):.3f}')
PY
```

Output:

```text
benchmark_query=limit order book market depth
benchmark_iterations=20
benchmark_result_count=2
benchmark_avg_ms=32.947
benchmark_min_ms=3.780
benchmark_max_ms=491.878
```

## Files Changed

- `<wzkf-root>/src/wzkf/db/models.py`
- `<wzkf-root>/src/wzkf/db/repositories.py`
- `<wzkf-root>/src/wzkf/api/main.py`
- `<wzkf-root>/src/wzkf/cli.py`
- `<wzkf-root>/src/wzkf/db/migrations/versions/0001_initial.py`
- `<wzkf-root>/src/wzkf/db/migrations/versions/0002_live_mvp_schema.py`
- `<wzkf-root>/src/wzkf/retrieval/live_postgres.py`
- `<wzkf-root>/tests/test_db_schema.py`
- `<wzkf-root>/tests/test_postgres_retrieval_sql.py`
- `<wzkf-root>/tests/test_api.py`
- `<wzkf-root>/tests/test_cli_help.py`
- `<wzkf-root>/README.md`
- `<wzkf-root>/docs/EVIDENCE/2026-06-30-live-mvp-phase2-3.md`

## What Is Proven

- The WZKF project is tracked in the staged review diff.
- Docker Postgres and Redis can run locally.
- The app can connect to live Postgres and Redis.
- Alembic can migrate live Postgres to revision `0002_live_mvp_schema`.
- All Phase 2 expected tables exist in live Postgres.
- pgvector is installed as a Postgres extension.
- `embeddings.embedding_vector` is a live `vector` column.
- Repository-level Postgres retrieval uses FTS and pgvector and returns
  `child_chunk_id`, `parent_chunk_id`, `document_id`, `source_url`,
  `chunk_hash`, `score`, `text_score`, and `vector_score`.
- CLI and FastAPI search/context-pack paths can use live Postgres FTS +
  pgvector when a database URL is configured.
- Tests and source validation pass after the patch.

## What Is Not Proven

- Redis/RQ workers are not implemented or proven.
- Re-run proof for Redis worker idempotency and no duplicate paid cost is not
  complete.
- Live ingestion of 1 podcast RSS/transcript, 3 academic records, and 1 GitHub
  repo fixed commit is not complete.
- Context packs can be generated from live Postgres search, but they are not yet
  persisted back into the live `context_packs` table by the CLI/API path.
- Ontology, persisted context packs, and Obsidian export have not yet been
  regenerated from a fully live Postgres-backed ingestion path.

## Blockers

- None for Phase 2.
- Phase 4 needs real Redis/RQ worker implementation.
- Phase 5 needs approved live source smoke inputs and a single documented
  acceptance command sequence.

## Next Patch

Run the Phase 5 live small ingestion smoke and produce the single documented
acceptance command sequence. Redis/RQ worker evidence is now captured in
`docs/EVIDENCE/2026-06-30-live-mvp-phase4-rq.md`.
