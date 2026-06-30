from pathlib import Path
import shutil

from sqlalchemy import create_engine, func, select

from wzkf.db.models import (
    child_chunks,
    claims,
    concepts,
    context_packs,
    cost_ledger,
    documents,
    embeddings,
    metadata,
    raw_artifacts,
)
from wzkf.jobs.cost_ledger import FileCostLedger
from wzkf.jobs.queue import JobStatus, LocalJobQueue
from wzkf.pipeline.local import LocalKnowledgeFabric
from wzkf.retrieval.embedding_service import CachedEmbeddingService, FileOperationCache
from wzkf.retrieval.embeddings import MockEmbeddingProvider
from wzkf.smoke.live_small import LiveSmallSmokeConfig, run_live_small_smoke


def _count(engine, table) -> int:
    with engine.connect() as conn:
        return conn.scalar(select(func.count()).select_from(table))


def test_live_small_smoke_persists_live_source_artifacts_and_is_idempotent(
    tmp_path: Path,
):
    repo_root = tmp_path / "cloned-repo"
    (repo_root / "src").mkdir(parents=True)
    (repo_root / "tests").mkdir()
    (repo_root / "README.mdx").write_text("# ppx_expect live README\n", encoding="utf-8")
    (repo_root / "LICENSE.md").write_text("MIT\n", encoding="utf-8")
    (repo_root / "src" / "ppx_expect.ml").write_text("let live = true\n", encoding="utf-8")
    (repo_root / "tests" / "test_expect.ml").write_text("let%expect_test _ = ()\n", encoding="utf-8")
    (repo_root / "secret-token.txt").write_text("must not ingest\n", encoding="utf-8")

    podcast_feed_url = "https://example.test/feed.xml"
    transcript_url = "https://example.test/transcript.txt"
    arxiv_url = "https://example.test/arxiv.xml"
    responses = {
        podcast_feed_url: f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Live Podcast Fixture</title>
    <item>
      <title>Live Transcript Episode</title>
      <link>https://example.test/episode</link>
      <enclosure url="https://example.test/audio.mp3" type="audio/mpeg"/>
      <podcast:transcript url="{transcript_url}" type="text/plain"/>
    </item>
  </channel>
</rss>
""",
        transcript_url: (
            "[00:00:00] Host: We discuss limit order book evidence.\n"
            "[00:00:05] Guest: Market depth and order book aliases need provenance.\n"
        ),
        arxiv_url: Path("tests/fixtures/papers/arxiv_qfin.xml").read_text(encoding="utf-8"),
        "https://api.openalex.org/works": Path(
            "tests/fixtures/academic_metadata/openalex_work.json"
        ).read_text(encoding="utf-8"),
        "https://api.crossref.org/works": Path(
            "tests/fixtures/academic_metadata/crossref_work.json"
        ).read_text(encoding="utf-8"),
    }

    def fetch_text(url: str, params: dict[str, str] | None = None, headers=None) -> str:
        assert headers is None or isinstance(headers, dict)
        return responses[url]

    def clone_repo(repo_url: str, destination: Path) -> str:
        assert repo_url == "https://github.com/janestreet/ppx_expect.git"
        shutil.copytree(repo_root, destination, dirs_exist_ok=True)
        return "d36acdd3fb1409cd6422fe3064741251fe585061"

    database_path = tmp_path / "smoke.sqlite"
    database_url = f"sqlite+pysqlite:///{database_path}"
    engine = create_engine(database_url)
    metadata.create_all(engine)

    config = LiveSmallSmokeConfig(
        storage_root=tmp_path / "storage",
        database_url=database_url,
        podcast_source_key="cheeky_pint",
        podcast_rss_url=podcast_feed_url,
        arxiv_query_id="qfin_market_microstructure",
        arxiv_api_url=arxiv_url,
        academic_query_id="qfin_market_microstructure",
        academic_search_query="limit order book",
        github_source_key="janestreet_ppx_expect",
        github_repo_url="https://github.com/janestreet/ppx_expect.git",
        context_query="limit order book market depth",
        query_embedding=[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    )

    first = run_live_small_smoke(config, fetch_text=fetch_text, clone_repo=clone_repo)
    second = run_live_small_smoke(config, fetch_text=fetch_text, clone_repo=clone_repo)

    assert first.document_count == 5
    assert first.raw_artifact_count == 5
    assert first.canonical_file_count == 5
    assert first.embedding_count == first.child_chunk_count
    assert first.context_pack_hash
    assert first.obsidian_note_count >= 5
    assert first.api_search_status == 200
    assert first.api_search_result_count >= 1
    assert first.evidence_path.exists()
    assert first.api_search_path.exists()
    assert first.api_context_pack_path.exists()

    assert second.document_count == first.document_count
    assert second.cost_operations == first.cost_operations
    assert second.db_counts["documents"] == 5
    assert second.db_counts["context_packs"] == 1

    assert _count(engine, documents) == 5
    assert _count(engine, raw_artifacts) == 5
    assert _count(engine, child_chunks) == first.child_chunk_count
    assert _count(engine, embeddings) == first.child_chunk_count
    assert _count(engine, concepts) >= 1
    assert _count(engine, claims) >= 1
    assert _count(engine, context_packs) == 1
    assert _count(engine, cost_ledger) == 5
    with engine.connect() as conn:
        retrieval_methods = set(
            conn.scalars(select(raw_artifacts.c.retrieval_method)).all()
        )
    assert retrieval_methods == {
        "academic_metadata_api",
        "arxiv_atom",
        "github_clone",
        "podcast_rss_transcript",
    }


def test_live_small_smoke_can_route_embeddings_through_rq_path(
    tmp_path: Path,
    monkeypatch,
):
    repo_root = tmp_path / "cloned-repo"
    (repo_root / "src").mkdir(parents=True)
    (repo_root / "README.mdx").write_text("# ppx_expect live README\n", encoding="utf-8")
    (repo_root / "LICENSE.md").write_text("MIT\n", encoding="utf-8")
    (repo_root / "src" / "ppx_expect.ml").write_text("let live = true\n", encoding="utf-8")

    podcast_feed_url = "https://example.test/feed.xml"
    transcript_url = "https://example.test/transcript.txt"
    arxiv_url = "https://example.test/arxiv.xml"
    responses = {
        podcast_feed_url: f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <item>
      <title>Live RQ Episode</title>
      <link>https://example.test/episode</link>
      <enclosure url="https://example.test/audio.mp3" type="audio/mpeg"/>
      <podcast:transcript url="{transcript_url}" type="text/plain"/>
    </item>
  </channel>
</rss>
""",
        transcript_url: "Limit order book evidence with market depth aliases.\n",
        arxiv_url: Path("tests/fixtures/papers/arxiv_qfin.xml").read_text(encoding="utf-8"),
        "https://api.openalex.org/works": Path(
            "tests/fixtures/academic_metadata/openalex_work.json"
        ).read_text(encoding="utf-8"),
        "https://api.crossref.org/works": Path(
            "tests/fixtures/academic_metadata/crossref_work.json"
        ).read_text(encoding="utf-8"),
    }

    def fetch_text(url: str, params: dict[str, str] | None = None, headers=None) -> str:
        return responses[url]

    def clone_repo(repo_url: str, destination: Path) -> str:
        shutil.copytree(repo_root, destination, dirs_exist_ok=True)
        return "d36acdd3fb1409cd6422fe3064741251fe585061"

    def fake_enqueue_embedding_job(
        redis_url: str,
        storage_root: Path,
        document_id: str,
        embedding_provider: str = "mock",
        embedding_model: str | None = None,
        queue_name: str = "unused",
    ) -> dict[str, object]:
        root = Path(storage_root)
        document = LocalKnowledgeFabric(root).get_document(document_id)
        assert document is not None
        provider = MockEmbeddingProvider()
        queue = LocalJobQueue(root / "manifests" / "jobs.json")
        job = queue.enqueue(
            job_type="embed_document",
            document_id=document_id,
            input_hash=document["canonical_hash"],
            payload={
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model or provider.model_name,
            },
        )
        if job.status == JobStatus.PENDING:
            service = CachedEmbeddingService(
                provider=provider,
                cache=FileOperationCache(root / "manifests" / "operation-cache.json"),
                config={"dimension": 8},
                cost_ledger=FileCostLedger(root / "manifests" / "cost-ledger.json"),
                provider_name="mock",
            )
            fabric = LocalKnowledgeFabric(root)
            for chunk in document["child_chunks"]:
                result = service.embed_text(chunk["text"])
                fabric.upsert_embedding(chunk["id"], provider.model_name, result.embedding)
            queue.mark(job.id, JobStatus.SUCCEEDED)
        return {
            "created_rq_job": True,
            "local_job_id": job.id,
            "rq_job_id": f"fake-{job.id}",
        }

    monkeypatch.setattr(
        "wzkf.smoke.live_small.enqueue_embedding_job",
        fake_enqueue_embedding_job,
    )
    monkeypatch.setattr("wzkf.smoke.live_small.work_rq_jobs", lambda **kwargs: True)

    database_url = f"sqlite+pysqlite:///{tmp_path / 'smoke-rq.sqlite'}"
    engine = create_engine(database_url)
    metadata.create_all(engine)
    config = LiveSmallSmokeConfig(
        storage_root=tmp_path / "storage",
        database_url=database_url,
        podcast_rss_url=podcast_feed_url,
        arxiv_api_url=arxiv_url,
        github_repo_url="https://github.com/janestreet/ppx_expect.git",
        use_rq=True,
        redis_url="redis://example.invalid:6379/0",
        queue_name="test-rq",
    )

    result = run_live_small_smoke(config, fetch_text=fetch_text, clone_repo=clone_repo)

    assert result.rq_used is True
    assert result.rq_worked is True
    assert result.rq_succeeded == 5
    assert result.rq_failed == 0
    assert result.rq_pending == 0
    assert result.embedding_count == result.child_chunk_count
    assert _count(engine, embeddings) == result.child_chunk_count
