from pathlib import Path

from wzkf.ingest.fixture_ingestor import FixtureIngestor
from wzkf.jobs.queue import JobStatus, LocalJobQueue
from wzkf.jobs.runner import KnowledgeJobRunner
from wzkf.pipeline.local import LocalKnowledgeFabric
from wzkf.retrieval.embedding_service import CachedEmbeddingService, FileOperationCache
from wzkf.storage.hashing import canonical_json_hash, sha256_text


class CountingEmbeddingProvider:
    model_name = "counting-embedding-v1"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return [float(len(text)), 1.0]


def test_cached_embedding_service_prevents_duplicate_provider_calls(tmp_path: Path):
    provider = CountingEmbeddingProvider()
    service = CachedEmbeddingService(
        provider=provider,
        cache=FileOperationCache(tmp_path / "operation-cache.json"),
        config={"dimension": 2},
    )

    first = service.embed_text("Expect tests make output reviewable.")
    second = service.embed_text("Expect tests make output reviewable.")

    assert first.embedding == second.embedding
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert provider.calls == 1
    assert first.operation_key == second.operation_key


def test_cached_embedding_operation_key_includes_prompt_hash(tmp_path: Path):
    provider = CountingEmbeddingProvider()
    service = CachedEmbeddingService(
        provider=provider,
        cache=FileOperationCache(tmp_path / "operation-cache.json"),
        config={"dimension": 2},
        prompt_hash="sha256:prompt-contract",
    )

    result = service.embed_text("Expect tests make output reviewable.")

    assert result.operation_key == canonical_json_hash(
        {
            "operation_name": "embed_text",
            "model_name": provider.model_name,
            "input_hash": sha256_text("Expect tests make output reviewable."),
            "prompt_hash": "sha256:prompt-contract",
            "config_hash": canonical_json_hash({"dimension": 2}),
        }
    )


def test_local_job_queue_runs_pending_embedding_job_once(tmp_path: Path):
    fabric = LocalKnowledgeFabric(tmp_path / "fabric")
    document = fabric.ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    queue = LocalJobQueue(tmp_path / "jobs.json")

    first_job = queue.enqueue(
        job_type="embed_document",
        document_id=document.document_id,
        input_hash=document.canonical_hash,
        payload={"embedding_model": "counting-embedding-v1"},
    )
    repeat_job = queue.enqueue(
        job_type="embed_document",
        document_id=document.document_id,
        input_hash=document.canonical_hash,
        payload={"embedding_model": "counting-embedding-v1"},
    )

    assert first_job.id == repeat_job.id
    assert queue.count(status=JobStatus.PENDING) == 1

    provider = CountingEmbeddingProvider()
    runner = KnowledgeJobRunner(
        fabric=fabric,
        queue=queue,
        embedding_service=CachedEmbeddingService(
            provider=provider,
            cache=FileOperationCache(tmp_path / "operation-cache.json"),
            config={"dimension": 2},
        ),
    )
    result = runner.run_pending()

    assert result.succeeded == 1
    assert queue.count(status=JobStatus.SUCCEEDED) == 1
    assert queue.count(status=JobStatus.PENDING) == 0
    assert provider.calls == len(document.child_chunks)
    assert fabric.embedding_count() == len(document.child_chunks)

    second_result = runner.run_pending()
    assert second_result.succeeded == 0
    assert provider.calls == len(document.child_chunks)


def test_job_runner_fails_closed_on_embedding_model_mismatch(tmp_path: Path):
    fabric = LocalKnowledgeFabric(tmp_path / "fabric")
    document = fabric.ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    queue = LocalJobQueue(tmp_path / "jobs.json")
    queue.enqueue(
        job_type="embed_document",
        document_id=document.document_id,
        input_hash=document.canonical_hash,
        payload={
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
        },
    )

    provider = CountingEmbeddingProvider()
    runner = KnowledgeJobRunner(
        fabric=fabric,
        queue=queue,
        embedding_service=CachedEmbeddingService(
            provider=provider,
            cache=FileOperationCache(tmp_path / "operation-cache.json"),
            config={"dimension": 2},
            provider_name="mock",
        ),
    )
    result = runner.run_pending()

    assert result.failed == 1
    assert provider.calls == 0
    assert fabric.embedding_count() == 0
    assert queue.count(status=JobStatus.FAILED) == 1
