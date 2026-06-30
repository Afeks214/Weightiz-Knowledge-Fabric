from typer.testing import CliRunner

import wzkf.cli as cli
from wzkf.harvesters.academic_metadata import (
    AcademicFetchResult,
    AcademicMetadataHarvester,
)
from wzkf.cli import app
from wzkf.retrieval.hybrid_search import SearchResult


def test_cli_help_lists_core_commands():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "sources" in result.output
    assert "ingest" in result.output
    assert "process" in result.output
    assert "search" in result.output
    assert "context-pack" in result.output
    assert "export" in result.output
    assert "smoke" in result.output


def test_sources_validate_uses_registry_files(tmp_path):
    sources = tmp_path / "sources.yaml"
    rights = tmp_path / "rights.yaml"
    sources.write_text(
        """
podcasts:
  - id: bad_source
    title: Bad Source
    strategy: official_transcript_first
    rights_policy: missing_policy
""",
        encoding="utf-8",
    )
    rights.write_text("policies: {}\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "sources",
            "validate",
            "--sources",
            str(sources),
            "--rights-policies",
            str(rights),
        ],
    )

    assert result.exit_code == 1
    assert "missing_policy" in result.output


def test_cli_ingest_podcast_can_use_rss_feed_fixture(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "podcast",
            "--source",
            "signals_threads",
            "--rss-feed",
            "tests/fixtures/podcast_rss/signals_threads_feed.xml",
            "--transcript-fixture",
            "tests/fixtures/signals_threads/episode.html",
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "selected transcript" in result.output
    assert (tmp_path / "manifests" / "corpus.json").exists()


def test_cli_ingest_papers_can_use_arxiv_atom_fixture(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "papers",
            "--query",
            "qfin_market_microstructure",
            "--atom",
            "tests/fixtures/papers/arxiv_qfin.xml",
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "harvested arxiv:qfin_market_microstructure" in result.output


def test_cli_ingest_news_can_use_reuters_metadata_fixture(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "news",
            "--source",
            "reuters_21578",
            "--fixture",
            "tests/fixtures/reuters/reuters_21578_metadata.json",
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "metadata-only reuters_21578 records ingested: 1" in result.output


def test_cli_ingest_academic_can_use_cached_live_query_client(tmp_path, monkeypatch):
    class FakeAcademicClient:
        def __init__(self, provider, query_id, cache, config):
            assert provider == "openalex"
            assert query_id == "qfin_market_microstructure"
            assert "api_key" in config
            self.cache = cache

        def fetch_query(self, query, limit):
            assert query == "limit order book"
            assert limit == 1
            fixture = "tests/fixtures/academic_metadata/openalex_work.json"
            records = AcademicMetadataHarvester(
                provider="openalex",
                query_id="qfin_market_microstructure",
            ).parse(open(fixture, encoding="utf-8").read())
            return AcademicFetchResult(
                records=records,
                operation_key="fixture-operation-key",
                cache_hit=False,
            )

    monkeypatch.setattr(cli, "CachedAcademicMetadataClient", FakeAcademicClient)

    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "academic",
            "--provider",
            "openalex",
            "--query",
            "qfin_market_microstructure",
            "--search-query",
            "limit order book",
            "--limit",
            "1",
            "--api-key",
            "test-openalex-key",
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "harvested academic:openalex:qfin_market_microstructure: 1 records" in result.output
    assert "cache_hit=false" in result.output
    assert "operation_key=fixture-operation-key" in result.output
    assert (tmp_path / "manifests" / "corpus.json").exists()


def test_cli_process_document_updates_jobs_and_cost_report(tmp_path):
    ingest = CliRunner().invoke(
        app,
        [
            "ingest",
            "podcast",
            "--source",
            "signals_threads",
            "--fixture",
            "tests/fixtures/signals_threads/episode.html",
            "--storage-root",
            str(tmp_path),
        ],
    )
    assert ingest.exit_code == 0

    import json

    corpus = json.loads((tmp_path / "manifests" / "corpus.json").read_text(encoding="utf-8"))
    document_id = next(iter(corpus["documents"]))
    child_count = len(corpus["documents"][document_id]["child_chunks"])

    process = CliRunner().invoke(
        app,
        [
            "process",
            "document",
            "--document-id",
            document_id,
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert process.exit_code == 0
    assert "processed jobs succeeded=1 failed=0 skipped=0" in process.output

    repeat = CliRunner().invoke(
        app,
        [
            "process",
            "document",
            "--document-id",
            document_id,
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert repeat.exit_code == 0
    assert "processed jobs succeeded=0 failed=0 skipped=0" in repeat.output

    status = CliRunner().invoke(
        app,
        ["jobs", "status", "--storage-root", str(tmp_path)],
    )

    assert status.exit_code == 0
    assert "total=1" in status.output
    assert "pending=0" in status.output
    assert "succeeded=1" in status.output

    costs = CliRunner().invoke(
        app,
        ["costs", "report", "--storage-root", str(tmp_path)],
    )

    assert costs.exit_code == 0
    assert f"operations={child_count}" in costs.output
    assert "estimated_cost_usd=0.000000" in costs.output


def test_cli_search_can_use_live_postgres_database_url(monkeypatch):
    captured = {}

    def fake_live_postgres_search(
        query,
        database_url,
        embedding_model,
        query_embedding,
        limit,
    ):
        captured.update(
            {
                "query": query,
                "database_url": database_url,
                "embedding_model": embedding_model,
                "query_embedding": query_embedding,
                "limit": limit,
            }
        )
        return [
            SearchResult(
                child_chunk_id="child-live",
                parent_chunk_id="parent-live",
                document_id="doc-live",
                source_title="Live Source",
                source_url="https://example.com/live",
                text="child text",
                parent_text="parent text",
                chunk_hash="hash-live",
                score=5.5,
                text_score=0.5,
                vector_score=1.0,
            )
        ]

    monkeypatch.setattr(cli, "live_postgres_search", fake_live_postgres_search)

    result = CliRunner().invoke(
        app,
        [
            "search",
            "limit order book",
            "--database-url",
            "postgresql://live",
            "--embedding-model",
            "test-vector",
            "--query-embedding",
            "0,1",
            "--limit",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert "5.50\tdoc-live\tchild-live\thttps://example.com/live" in result.output
    assert captured == {
        "query": "limit order book",
        "database_url": "postgresql://live",
        "embedding_model": "test-vector",
        "query_embedding": [0.0, 1.0],
        "limit": 3,
    }


def test_cli_context_pack_can_use_live_postgres_database_url(monkeypatch):
    def fake_live_postgres_search(
        query,
        database_url,
        embedding_model,
        query_embedding,
        limit,
    ):
        return [
            SearchResult(
                child_chunk_id="child-live",
                parent_chunk_id="parent-live",
                document_id="doc-live",
                source_title="Live Source",
                source_url="https://example.com/live",
                text="child text",
                parent_text="parent cited text",
                chunk_hash="hash-live",
                score=5.5,
                text_score=0.5,
                vector_score=1.0,
            )
        ]

    monkeypatch.setattr(cli, "live_postgres_search", fake_live_postgres_search)

    result = CliRunner().invoke(
        app,
        [
            "context-pack",
            "limit order book",
            "--database-url",
            "postgresql://live",
            "--embedding-model",
            "test-vector",
            "--query-embedding",
            "0,1",
            "--limit",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert '"abstain":false' in result.output
    assert '"included_child_chunk_ids":["child-live"]' in result.output
    assert '"source_url":"https://example.com/live"' in result.output
    assert '"chunk_hash":"hash-live"' in result.output


def test_cli_process_document_openai_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("WZKF_OPENAI_API_KEY", raising=False)
    ingest = CliRunner().invoke(
        app,
        [
            "ingest",
            "podcast",
            "--source",
            "signals_threads",
            "--fixture",
            "tests/fixtures/signals_threads/episode.html",
            "--storage-root",
            str(tmp_path),
        ],
    )
    assert ingest.exit_code == 0

    import json

    corpus = json.loads((tmp_path / "manifests" / "corpus.json").read_text(encoding="utf-8"))
    document_id = next(iter(corpus["documents"]))

    process = CliRunner().invoke(
        app,
        [
            "process",
            "document",
            "--document-id",
            document_id,
            "--embedding-provider",
            "openai",
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert process.exit_code == 1
    assert "ABSTAIN:" in process.output
    assert "api_key" in process.output
    assert not (tmp_path / "manifests" / "jobs.json").exists()


def test_cli_process_document_can_select_openai_provider_without_storing_key(
    tmp_path,
    monkeypatch,
):
    class FakeOpenAIEmbeddingProvider:
        def __init__(self, api_key, model_name="text-embedding-3-small"):
            assert api_key == "test-openai-key"
            self.model_name = model_name

        def embed(self, text):
            return [float(len(text)), 42.0]

    monkeypatch.setattr(cli, "OpenAIEmbeddingProvider", FakeOpenAIEmbeddingProvider)

    ingest = CliRunner().invoke(
        app,
        [
            "ingest",
            "podcast",
            "--source",
            "signals_threads",
            "--fixture",
            "tests/fixtures/signals_threads/episode.html",
            "--storage-root",
            str(tmp_path),
        ],
    )
    assert ingest.exit_code == 0

    import json

    corpus = json.loads((tmp_path / "manifests" / "corpus.json").read_text(encoding="utf-8"))
    document_id = next(iter(corpus["documents"]))
    child_count = len(corpus["documents"][document_id]["child_chunks"])

    process = CliRunner().invoke(
        app,
        [
            "process",
            "document",
            "--document-id",
            document_id,
            "--embedding-provider",
            "openai",
            "--embedding-model",
            "text-embedding-3-small",
            "--api-key",
            "test-openai-key",
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert process.exit_code == 0
    assert "processed jobs succeeded=1 failed=0 skipped=0" in process.output

    costs = json.loads((tmp_path / "manifests" / "cost-ledger.json").read_text())
    assert len(costs["operations"]) == child_count
    assert {operation["provider"] for operation in costs["operations"].values()} == {"openai"}
    assert "test-openai-key" not in (tmp_path / "manifests" / "jobs.json").read_text()
    assert "test-openai-key" not in (tmp_path / "manifests" / "operation-cache.json").read_text()
    assert "test-openai-key" not in (tmp_path / "manifests" / "cost-ledger.json").read_text()


def test_cli_ontology_review_reports_resolved_concepts(tmp_path):
    ingest = CliRunner().invoke(
        app,
        [
            "ingest",
            "podcast",
            "--source",
            "signals_threads",
            "--fixture",
            "tests/fixtures/signals_threads/episode.html",
            "--storage-root",
            str(tmp_path),
        ],
    )
    assert ingest.exit_code == 0

    review = CliRunner().invoke(
        app,
        ["ontology", "review", "--storage-root", str(tmp_path)],
    )

    assert review.exit_code == 0
    assert "concepts=1" in review.output
    assert "review_items=0" in review.output
    assert "Expect Tests" in review.output


def test_cli_jobs_enqueue_rq_reports_local_and_rq_ids(tmp_path, monkeypatch):
    ingest = CliRunner().invoke(
        app,
        [
            "ingest",
            "podcast",
            "--source",
            "signals_threads",
            "--fixture",
            "tests/fixtures/signals_threads/episode.html",
            "--storage-root",
            str(tmp_path),
        ],
    )
    assert ingest.exit_code == 0

    import json

    document_id = next(
        iter(json.loads((tmp_path / "manifests" / "corpus.json").read_text())["documents"])
    )

    def fake_enqueue_embedding_job(**kwargs):
        assert kwargs["redis_url"] == "redis://unit-test"
        assert kwargs["document_id"] == document_id
        return {
            "created_rq_job": True,
            "local_job_id": "local-job-id",
            "rq_job_id": "rq-job-id",
        }

    monkeypatch.setattr(cli, "enqueue_embedding_job", fake_enqueue_embedding_job, raising=False)

    result = CliRunner().invoke(
        app,
        [
            "jobs",
            "enqueue-rq",
            "--document-id",
            document_id,
            "--redis-url",
            "redis://unit-test",
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "rq enqueued local_job_id=local-job-id rq_job_id=rq-job-id created=true" in result.output


def test_cli_jobs_work_rq_reports_worker_result(monkeypatch):
    def fake_work_rq_jobs(**kwargs):
        assert kwargs["redis_url"] == "redis://unit-test"
        assert kwargs["queue_name"] == "wzkf-embeddings"
        assert kwargs["burst"] is True
        assert kwargs["max_jobs"] == 1
        return True

    monkeypatch.setattr(cli, "work_rq_jobs", fake_work_rq_jobs, raising=False)

    result = CliRunner().invoke(
        app,
        [
            "jobs",
            "work-rq",
            "--redis-url",
            "redis://unit-test",
            "--queue-name",
            "wzkf-embeddings",
            "--burst",
            "--max-jobs",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "rq worker queue=wzkf-embeddings burst=true worked=true" in result.output
