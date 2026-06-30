from __future__ import annotations

from dataclasses import dataclass

from wzkf.jobs.queue import JobRecord, JobStatus, LocalJobQueue
from wzkf.pipeline.local import LocalKnowledgeFabric
from wzkf.retrieval.embedding_service import CachedEmbeddingService


@dataclass(frozen=True)
class JobRunResult:
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


class KnowledgeJobRunner:
    def __init__(
        self,
        fabric: LocalKnowledgeFabric,
        queue: LocalJobQueue,
        embedding_service: CachedEmbeddingService,
    ):
        self.fabric = fabric
        self.queue = queue
        self.embedding_service = embedding_service

    def run_pending(self) -> JobRunResult:
        succeeded = 0
        failed = 0
        skipped = 0
        for job in self.queue.pending():
            result = self.run_job(job.id)
            succeeded += result.succeeded
            failed += result.failed
            skipped += result.skipped
        return JobRunResult(succeeded=succeeded, failed=failed, skipped=skipped)

    def run_job(self, job_id: str) -> JobRunResult:
        job = self.queue.get(job_id)
        if job is None:
            return JobRunResult(failed=1)
        if job.status != JobStatus.PENDING:
            return JobRunResult(skipped=1)
        self.queue.mark(job.id, JobStatus.RUNNING)
        try:
            if job.job_type == "embed_document":
                self._run_embed_document(job)
                self.queue.mark(job.id, JobStatus.SUCCEEDED)
                return JobRunResult(succeeded=1)
            self.queue.mark(job.id, JobStatus.SKIPPED, "unsupported job type")
            return JobRunResult(skipped=1)
        except Exception as exc:  # pragma: no cover - defensive state capture
            self.queue.mark(job.id, JobStatus.FAILED, str(exc))
            return JobRunResult(failed=1)

    def _run_embed_document(self, job: JobRecord) -> None:
        requested_provider = job.payload.get("embedding_provider")
        if requested_provider and requested_provider != self.embedding_service.provider_name:
            raise ValueError(
                "embedding provider mismatch: "
                f"job requires {requested_provider}, "
                f"runner has {self.embedding_service.provider_name}"
            )
        requested_model = job.payload.get("embedding_model")
        if requested_model and requested_model != self.embedding_service.model_name:
            raise ValueError(
                "embedding model mismatch: "
                f"job requires {requested_model}, "
                f"runner has {self.embedding_service.model_name}"
            )
        document_id = job.document_id
        document = self.fabric.get_document(document_id)
        if document is None:
            raise ValueError(f"document not found: {document_id}")
        for chunk in document.get("child_chunks", []):
            result = self.embedding_service.embed_text(chunk["text"])
            self.fabric.upsert_embedding(
                chunk["id"],
                self.embedding_service.model_name,
                result.embedding,
            )
