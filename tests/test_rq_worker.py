import importlib
import importlib.util
from pathlib import Path

from wzkf.ingest.fixture_ingestor import FixtureIngestor
from wzkf.jobs.cost_ledger import FileCostLedger
from wzkf.jobs.queue import JobStatus, LocalJobQueue
from wzkf.pipeline.local import LocalKnowledgeFabric


def _rq_worker_module():
    assert importlib.util.find_spec("wzkf.jobs.rq_worker") is not None
    return importlib.import_module("wzkf.jobs.rq_worker")


def test_rq_enqueue_creates_one_rq_job_for_one_local_job(tmp_path: Path, monkeypatch):
    rq_worker = _rq_worker_module()
    fabric = LocalKnowledgeFabric(tmp_path / "fabric")
    document = fabric.ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    fake_connection = object()

    class FakeRedis:
        @classmethod
        def from_url(cls, redis_url):
            assert redis_url == "redis://unit-test"
            return fake_connection

    class FakeJob:
        def __init__(self, job_id):
            self.id = job_id

    class FakeQueue:
        jobs = {}
        enqueue_calls = []

        def __init__(self, name, connection):
            assert name == "wzkf-embeddings"
            assert connection is fake_connection

        def fetch_job(self, job_id):
            return self.jobs.get(job_id)

        def enqueue(self, func, *args, **kwargs):
            job = FakeJob(kwargs["job_id"])
            self.jobs[job.id] = job
            self.enqueue_calls.append((func, args, kwargs))
            return job

    monkeypatch.setattr(rq_worker, "Redis", FakeRedis)
    monkeypatch.setattr(rq_worker, "Queue", FakeQueue)

    first = rq_worker.enqueue_embedding_job(
        redis_url="redis://unit-test",
        storage_root=tmp_path / "fabric",
        document_id=document.document_id,
    )
    second = rq_worker.enqueue_embedding_job(
        redis_url="redis://unit-test",
        storage_root=tmp_path / "fabric",
        document_id=document.document_id,
    )

    assert first["local_job_id"] == second["local_job_id"]
    assert first["rq_job_id"] == second["rq_job_id"]
    assert first["rq_job_id"].startswith("wzkf-embed-")
    assert ":" not in first["rq_job_id"]
    assert first["created_rq_job"] is True
    assert second["created_rq_job"] is False
    assert len(FakeQueue.enqueue_calls) == 1
    assert LocalJobQueue(tmp_path / "fabric" / "manifests" / "jobs.json").count(
        status=JobStatus.PENDING
    ) == 1


def test_rq_embedding_task_runs_local_job_once_without_duplicate_cost(tmp_path: Path):
    rq_worker = _rq_worker_module()
    fabric = LocalKnowledgeFabric(tmp_path / "fabric")
    document = fabric.ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    queue = LocalJobQueue(tmp_path / "fabric" / "manifests" / "jobs.json")
    job = queue.enqueue(
        job_type="embed_document",
        document_id=document.document_id,
        input_hash=document.canonical_hash,
        payload={
            "embedding_provider": "mock",
            "embedding_model": "mock-hash-embedding-v1",
        },
    )

    first = rq_worker.run_embedding_job(
        storage_root=str(tmp_path / "fabric"),
        local_job_id=job.id,
        embedding_provider="mock",
        embedding_model="mock-hash-embedding-v1",
    )
    second = rq_worker.run_embedding_job(
        storage_root=str(tmp_path / "fabric"),
        local_job_id=job.id,
        embedding_provider="mock",
        embedding_model="mock-hash-embedding-v1",
    )

    assert first == {"failed": 0, "skipped": 0, "succeeded": 1}
    assert second == {"failed": 0, "skipped": 1, "succeeded": 0}
    assert queue.count(status=JobStatus.SUCCEEDED) == 1
    assert fabric.embedding_count() == len(document.child_chunks)
    assert FileCostLedger(tmp_path / "fabric" / "manifests" / "cost-ledger.json").summary().operations == len(
        document.child_chunks
    )


def test_rq_embedding_task_marks_failed_on_provider_mismatch(tmp_path: Path):
    rq_worker = _rq_worker_module()
    fabric = LocalKnowledgeFabric(tmp_path / "fabric")
    document = fabric.ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    queue = LocalJobQueue(tmp_path / "fabric" / "manifests" / "jobs.json")
    job = queue.enqueue(
        job_type="embed_document",
        document_id=document.document_id,
        input_hash=document.canonical_hash,
        payload={
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
        },
    )

    result = rq_worker.run_embedding_job(
        storage_root=str(tmp_path / "fabric"),
        local_job_id=job.id,
        embedding_provider="mock",
        embedding_model="mock-hash-embedding-v1",
    )

    assert result == {"failed": 1, "skipped": 0, "succeeded": 0}
    assert queue.count(status=JobStatus.FAILED) == 1
    assert fabric.embedding_count() == 0


def test_rq_embedding_task_marks_failed_when_provider_cannot_start(
    tmp_path: Path,
    monkeypatch,
):
    rq_worker = _rq_worker_module()
    monkeypatch.delenv("WZKF_OPENAI_API_KEY", raising=False)
    fabric = LocalKnowledgeFabric(tmp_path / "fabric")
    document = fabric.ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    queue = LocalJobQueue(tmp_path / "fabric" / "manifests" / "jobs.json")
    job = queue.enqueue(
        job_type="embed_document",
        document_id=document.document_id,
        input_hash=document.canonical_hash,
        payload={
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
        },
    )

    result = rq_worker.run_embedding_job(
        storage_root=str(tmp_path / "fabric"),
        local_job_id=job.id,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
    )

    assert result == {"failed": 1, "skipped": 0, "succeeded": 0}
    assert queue.count(status=JobStatus.FAILED) == 1
    assert "api_key" in queue.get(job.id).error_message
