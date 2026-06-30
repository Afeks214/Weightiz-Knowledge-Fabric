from dataclasses import asdict
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel

from wzkf.retrieval.context_pack import ContextPackBuilder
from wzkf.jobs.cost_ledger import FileCostLedger
from wzkf.jobs.queue import JobRecord, JobStatus, LocalJobQueue
from wzkf.jobs.runner import JobRunResult, KnowledgeJobRunner
from wzkf.pipeline.local import LocalKnowledgeFabric
from wzkf.retrieval.embedding_service import CachedEmbeddingService, FileOperationCache
from wzkf.retrieval.embeddings import MockEmbeddingProvider
from wzkf.retrieval.live_postgres import live_postgres_search, resolve_query_embedding


class ContextPackRequest(BaseModel):
    query: str
    created_for: str = "api"
    embedding_model: str | None = None
    query_embedding: str | None = None
    limit: int = 10


class EmbedDocumentJobRequest(BaseModel):
    document_id: str


def create_app(storage_root: Path | None = None, database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="WZ Knowledge Fabric", version="0.1.0")
    root = storage_root or Path("data")
    fabric = LocalKnowledgeFabric(root)
    resolved_database_url = database_url or os.environ.get("DATABASE_URL")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/context-packs")
    def context_pack(request: ContextPackRequest):
        results = _search_results(
            fabric=fabric,
            database_url=resolved_database_url,
            query=request.query,
            embedding_model=request.embedding_model,
            query_embedding=request.query_embedding,
            limit=request.limit,
        )
        return ContextPackBuilder().build(request.query, results, request.created_for)

    @app.get("/search")
    def search(
        query: str,
        embedding_model: str | None = None,
        query_embedding: str | None = None,
        limit: int = 10,
    ) -> dict[str, object]:
        results = _search_results(
            fabric=fabric,
            database_url=resolved_database_url,
            query=query,
            embedding_model=embedding_model,
            query_embedding=query_embedding,
            limit=limit,
        )
        return {
            "query": query,
            "results": [result.model_dump(mode="json") for result in results],
            "abstain": not results,
        }

    @app.get("/documents/{document_id}")
    def document(document_id: str) -> dict[str, object]:
        found = fabric.get_document(document_id)
        if found is None:
            raise HTTPException(status_code=404, detail="document not found")
        return found

    @app.get("/concepts")
    def concepts() -> dict[str, object]:
        return {
            "concepts": [asdict(concept) for concept in fabric.concepts()],
            "review_items": [asdict(item) for item in fabric.concept_review_items()],
        }

    @app.get("/concepts/{concept_id}")
    def concept(concept_id: str) -> dict[str, object]:
        found = fabric.get_concept(concept_id)
        if found is None:
            raise HTTPException(status_code=404, detail="concept not found")
        return asdict(found)

    @app.post("/jobs/embed-document")
    def enqueue_embed_document(request: EmbedDocumentJobRequest) -> dict[str, object]:
        document = fabric.get_document(request.document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document not found")
        queue = LocalJobQueue(_jobs_path(root))
        return _job_json(
            queue.enqueue(
                job_type="embed_document",
                document_id=request.document_id,
                input_hash=document["canonical_hash"],
                payload={"embedding_model": MockEmbeddingProvider.model_name},
            )
        )

    @app.get("/jobs/status")
    def jobs_status() -> dict[str, int]:
        queue = LocalJobQueue(_jobs_path(root))
        status = {"total": queue.count()}
        for item in JobStatus:
            status[item.value.lower()] = queue.count(status=item)
        return status

    @app.post("/jobs/run-pending")
    def run_pending_jobs() -> dict[str, int]:
        result = _run_pending_embedding_jobs(fabric, LocalJobQueue(_jobs_path(root)), root)
        return asdict(result)

    @app.get("/costs")
    def costs() -> dict[str, float | int]:
        return asdict(FileCostLedger(_costs_path(root)).summary())

    return app


def _search_results(
    fabric: LocalKnowledgeFabric,
    database_url: str | None,
    query: str,
    embedding_model: str | None,
    query_embedding: str | None,
    limit: int,
):
    if not database_url:
        return fabric.search(query, limit=limit)
    try:
        resolved_embedding = resolve_query_embedding(query, query_embedding)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return live_postgres_search(
        query=query,
        database_url=database_url,
        embedding_model=embedding_model or MockEmbeddingProvider.model_name,
        query_embedding=resolved_embedding,
        limit=limit,
    )


def _run_pending_embedding_jobs(
    fabric: LocalKnowledgeFabric,
    queue: LocalJobQueue,
    storage_root: Path,
) -> JobRunResult:
    service = CachedEmbeddingService(
        provider=MockEmbeddingProvider(),
        cache=FileOperationCache(_operation_cache_path(storage_root)),
        config={"dimension": 8},
        cost_ledger=FileCostLedger(_costs_path(storage_root)),
        provider_name="mock",
    )
    return KnowledgeJobRunner(
        fabric=fabric,
        queue=queue,
        embedding_service=service,
    ).run_pending()


def _job_json(job: JobRecord) -> dict[str, object]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "document_id": job.document_id,
        "input_hash": job.input_hash,
        "payload": job.payload,
        "status": job.status.value,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "error_message": job.error_message,
    }


def _jobs_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "jobs.json"


def _operation_cache_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "operation-cache.json"


def _costs_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "cost-ledger.json"


app = create_app()
