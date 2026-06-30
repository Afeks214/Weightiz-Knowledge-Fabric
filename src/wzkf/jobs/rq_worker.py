from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from redis import Redis
from rq import Queue, SimpleWorker

from wzkf.jobs.cost_ledger import FileCostLedger
from wzkf.jobs.queue import JobStatus, LocalJobQueue
from wzkf.jobs.runner import KnowledgeJobRunner
from wzkf.pipeline.local import LocalKnowledgeFabric
from wzkf.retrieval.embedding_service import CachedEmbeddingService, FileOperationCache
from wzkf.retrieval.embeddings import (
    EmbeddingProviderError,
    MockEmbeddingProvider,
    OPENAI_EMBEDDINGS_ENDPOINT,
    OpenAIEmbeddingProvider,
)


DEFAULT_RQ_QUEUE = "wzkf-embeddings"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def enqueue_embedding_job(
    redis_url: str,
    storage_root: Path,
    document_id: str,
    embedding_provider: str = "mock",
    embedding_model: str | None = None,
    queue_name: str = DEFAULT_RQ_QUEUE,
) -> dict[str, object]:
    root = Path(storage_root)
    document = LocalKnowledgeFabric(root).get_document(document_id)
    if document is None:
        raise ValueError(f"document not found: {document_id}")

    provider = embedding_provider.lower().strip()
    model = _embedding_model(provider, embedding_model)
    local_job = LocalJobQueue(_jobs_path(root)).enqueue(
        job_type="embed_document",
        document_id=document_id,
        input_hash=document["canonical_hash"],
        payload={
            "embedding_provider": provider,
            "embedding_model": model,
        },
    )

    rq_job_id = f"wzkf-embed-{local_job.id}"
    queue = Queue(queue_name, connection=Redis.from_url(redis_url))
    rq_job = queue.fetch_job(rq_job_id)
    created = False
    if rq_job is None:
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
        created = True

    return {
        "created_rq_job": created,
        "local_job_id": local_job.id,
        "rq_job_id": rq_job.id,
    }


def run_embedding_job(
    storage_root: str,
    local_job_id: str,
    embedding_provider: str = "mock",
    embedding_model: str | None = None,
) -> dict[str, int]:
    root = Path(storage_root)
    queue = LocalJobQueue(_jobs_path(root))
    try:
        service = build_embedding_service(
            storage_root=root,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
    except Exception as exc:
        if queue.get(local_job_id) is not None:
            queue.mark(local_job_id, JobStatus.FAILED, str(exc))
        return {"failed": 1, "skipped": 0, "succeeded": 0}
    result = KnowledgeJobRunner(
        fabric=LocalKnowledgeFabric(root),
        queue=queue,
        embedding_service=service,
    ).run_job(local_job_id)
    return asdict(result)


def work_rq_jobs(
    redis_url: str = DEFAULT_REDIS_URL,
    queue_name: str = DEFAULT_RQ_QUEUE,
    burst: bool = True,
    max_jobs: int | None = None,
) -> bool:
    connection = Redis.from_url(redis_url)
    queue = Queue(queue_name, connection=connection)
    worker = SimpleWorker([queue], connection=connection)
    return worker.work(burst=burst, max_jobs=max_jobs)


def build_embedding_service(
    storage_root: Path,
    embedding_provider: str,
    embedding_model: str | None,
) -> CachedEmbeddingService:
    provider = embedding_provider.lower().strip()
    if provider == "mock":
        return CachedEmbeddingService(
            provider=MockEmbeddingProvider(),
            cache=FileOperationCache(_operation_cache_path(storage_root)),
            config={"dimension": 8},
            cost_ledger=FileCostLedger(_costs_path(storage_root)),
            provider_name="mock",
        )
    if provider == "openai":
        api_key = os.environ.get("WZKF_OPENAI_API_KEY", "").strip()
        if not api_key:
            raise EmbeddingProviderError("openai embedding provider requires api_key")
        model = embedding_model or "text-embedding-3-small"
        return CachedEmbeddingService(
            provider=OpenAIEmbeddingProvider(api_key=api_key, model_name=model),
            cache=FileOperationCache(_operation_cache_path(storage_root)),
            config={
                "endpoint": OPENAI_EMBEDDINGS_ENDPOINT,
                "provider": "openai",
            },
            cost_ledger=FileCostLedger(_costs_path(storage_root)),
            provider_name="openai",
        )
    raise EmbeddingProviderError(f"unsupported embedding provider: {embedding_provider}")


def _embedding_model(embedding_provider: str, embedding_model: str | None) -> str:
    if embedding_model:
        return embedding_model
    if embedding_provider == "mock":
        return MockEmbeddingProvider.model_name
    if embedding_provider == "openai":
        return "text-embedding-3-small"
    raise EmbeddingProviderError(f"unsupported embedding provider: {embedding_provider}")


def _jobs_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "jobs.json"


def _operation_cache_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "operation-cache.json"


def _costs_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "cost-ledger.json"
