from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, insert, select, text, update
from sqlalchemy.orm import Session

from wzkf.db.models import (
    child_chunks,
    claims,
    concept_aliases,
    concepts,
    context_packs,
    cost_ledger,
    documents,
    document_concepts,
    embeddings,
    parent_chunks,
    processing_jobs,
    raw_artifacts,
    sources,
)
from wzkf.extraction.claims import ClaimExtractionV1
from wzkf.ingest.fixture_ingestor import FixtureDocument
from wzkf.ontology.store import ConceptRecord
from wzkf.retrieval.context_pack import ContextPack
from wzkf.retrieval.hybrid_search import SearchResult
from wzkf.storage.hashing import canonical_json_hash, sha256_text


class KnowledgeRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_fixture_document(self, document: FixtureDocument) -> FixtureDocument:
        source_id = self._upsert_source(document)
        self._upsert_document(document, source_id)
        self._upsert_raw_artifact(document)
        for parent in document.parent_chunks:
            self._insert_if_missing(
                parent_chunks,
                parent.id,
                {
                    "id": parent.id,
                    "document_id": parent.document_id,
                    "chunk_index": parent.chunk_index,
                    "section_title": parent.section_title,
                    "speaker": None,
                    "start_time_sec": None,
                    "end_time_sec": None,
                    "page_start": None,
                    "page_end": None,
                    "text": parent.text,
                    "token_count": parent.token_count,
                    "chunk_hash": parent.chunk_hash,
                },
            )
        for child in document.child_chunks:
            self._insert_if_missing(
                child_chunks,
                child.id,
                {
                    "id": child.id,
                    "parent_chunk_id": child.parent_chunk_id,
                    "document_id": child.document_id,
                    "child_index": child.child_index,
                    "text": child.text,
                    "token_count": child.token_count,
                    "chunk_hash": child.chunk_hash,
                },
            )
        self.session.flush()
        return document

    def search_child_chunks(self, query: str, limit: int = 10) -> list[SearchResult]:
        terms = [term.casefold() for term in query.split() if term.strip()]
        rows = self._child_rows()
        results: list[SearchResult] = []
        for row in rows:
            text = row["text"]
            score = _term_score(text, terms)
            if score <= 0:
                continue
            results.append(_search_result_from_row(row, text_score=float(score), vector_score=0.0))
        return sorted(results, key=lambda item: (-item.score, item.child_chunk_id))[:limit]

    def hybrid_search_child_chunks(
        self,
        query: str,
        query_embedding: list[float],
        embedding_model: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        terms = [term.casefold() for term in query.split() if term.strip()]
        rows = self.session.execute(
            select(
                child_chunks.c.id.label("child_id"),
                child_chunks.c.parent_chunk_id,
                child_chunks.c.document_id,
                child_chunks.c.text,
                child_chunks.c.chunk_hash,
                parent_chunks.c.text.label("parent_text"),
                documents.c.title,
                documents.c.canonical_url,
                embeddings.c.embedding,
            )
            .join(documents, documents.c.id == child_chunks.c.document_id)
            .join(parent_chunks, parent_chunks.c.id == child_chunks.c.parent_chunk_id)
            .outerjoin(
                embeddings,
                and_(
                    embeddings.c.child_chunk_id == child_chunks.c.id,
                    embeddings.c.embedding_model == embedding_model,
                ),
            )
        ).mappings()
        results: list[SearchResult] = []
        for row in rows:
            text_score = float(_term_score(row["text"], terms))
            vector_score = _cosine(query_embedding, row["embedding"] or [])
            if text_score <= 0 and vector_score <= 0:
                continue
            results.append(
                _search_result_from_row(
                    row,
                    text_score=text_score,
                    vector_score=vector_score,
                )
            )
        return sorted(results, key=lambda item: (-item.score, item.child_chunk_id))[:limit]

    def postgres_hybrid_search_child_chunks(
        self,
        query: str,
        query_embedding: list[float],
        embedding_model: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        bind = self.session.get_bind()
        if bind.dialect.name != "postgresql":
            raise RuntimeError("postgres_hybrid_search_child_chunks requires PostgreSQL")
        rows = self.session.execute(
            postgres_hybrid_search_sql(),
            {
                "query": query,
                "query_embedding": _vector_literal(query_embedding),
                "embedding_model": embedding_model,
                "limit": limit,
            },
        ).mappings()
        return [
            SearchResult(
                child_chunk_id=row["child_chunk_id"],
                parent_chunk_id=row["parent_chunk_id"],
                document_id=row["document_id"],
                source_title=row["source_title"],
                source_url=row["source_url"] or "",
                text=row["text"],
                parent_text=row["parent_text"],
                chunk_hash=row["chunk_hash"],
                score=float(row["score"] or 0.0),
                text_score=float(row["text_score"] or 0.0),
                vector_score=float(row["vector_score"] or 0.0),
            )
            for row in rows
        ]

    def upsert_embedding(self, child_chunk_id: str, model: str, embedding: list[float]) -> str:
        embedding_id = sha256_text(f"{child_chunk_id}:{model}")[:32]
        self._insert_if_missing(
            embeddings,
            embedding_id,
            {
                "id": embedding_id,
                "child_chunk_id": child_chunk_id,
                "embedding_model": model,
                "embedding": embedding,
                "embedding_vector": embedding,
                "created_at": _now(),
            },
        )
        self.session.flush()
        return embedding_id

    def upsert_claim(self, claim: ClaimExtractionV1, parent_chunk_id: str) -> str:
        claim_id = canonical_json_hash(
            {
                "document_id": claim.document_id,
                "parent_chunk_id": parent_chunk_id,
                "claim_text": claim.claim_text,
                "evidence_child_chunk_ids": claim.evidence_child_chunk_ids,
            }
        )[:32]
        self._insert_if_missing(
            claims,
            claim_id,
            {
                "id": claim_id,
                "document_id": claim.document_id,
                "parent_chunk_id": parent_chunk_id,
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_type,
                "confidence": claim.confidence,
                "extraction_model": claim.extraction_model,
                "evidence_child_chunk_ids": claim.evidence_child_chunk_ids,
                "created_at": _now(),
            },
        )
        self.session.flush()
        return claim_id

    def count_claims(self) -> int:
        return len(list(self.session.execute(select(claims.c.id))))

    def upsert_processing_job(
        self,
        job_type: str,
        document_id: str,
        input_hash: str,
        status: str,
    ) -> str:
        job_id = canonical_json_hash(
            {"job_type": job_type, "document_id": document_id, "input_hash": input_hash}
        )[:32]
        existing = self.session.scalar(select(processing_jobs.c.id).where(processing_jobs.c.id == job_id))
        values = {
            "id": job_id,
            "job_type": job_type,
            "document_id": document_id,
            "input_hash": input_hash,
            "status": status,
            "started_at": _now(),
            "finished_at": _now() if status in {"SUCCEEDED", "FAILED", "SKIPPED", "ABSTAINED"} else None,
            "error_message": None,
            "retry_count": 0,
        }
        if existing is None:
            self.session.execute(insert(processing_jobs).values(**values))
        else:
            self.session.execute(
                update(processing_jobs).where(processing_jobs.c.id == job_id).values(status=status)
            )
        self.session.flush()
        return job_id

    def record_cost(
        self,
        job_id: str,
        provider: str,
        model: str,
        estimated_cost_usd: float,
    ) -> str:
        cost_id = canonical_json_hash(
            {"job_id": job_id, "provider": provider, "model": model, "unit_type": "operation"}
        )[:32]
        self._insert_if_missing(
            cost_ledger,
            cost_id,
            {
                "id": cost_id,
                "job_id": job_id,
                "provider": provider,
                "model": model,
                "unit_type": "operation",
                "input_units": 1.0,
                "output_units": 0.0,
                "estimated_cost_usd": estimated_cost_usd,
                "created_at": _now(),
            },
        )
        self.session.flush()
        return cost_id

    def upsert_context_pack(self, pack: ContextPack) -> str:
        pack_id = pack.pack_hash[:32]
        self._insert_if_missing(
            context_packs,
            pack_id,
            {
                "id": pack_id,
                "query": pack.query,
                "pack_hash": pack.pack_hash,
                "included_child_chunk_ids": pack.included_child_chunk_ids,
                "created_for": pack.created_for,
                "created_at": pack.created_at,
            },
        )
        self.session.flush()
        return pack_id

    def upsert_concept_record(self, concept: ConceptRecord) -> str:
        concept_id = concept.concept_id
        self._insert_if_missing(
            concepts,
            concept_id,
            {
                "id": concept_id,
                "canonical_name": concept.canonical_name,
                "concept_type": concept.concept_type,
                "description": None,
                "created_at": _now(),
            },
        )
        for alias in concept.aliases:
            alias_id = canonical_json_hash({"concept_id": concept_id, "alias": alias})[:32]
            self._insert_if_missing(
                concept_aliases,
                alias_id,
                {
                    "id": alias_id,
                    "concept_id": concept_id,
                    "alias": alias,
                    "alias_source": "live_small_smoke",
                    "confidence": concept.confidence,
                },
            )
        for document_id in concept.document_ids:
            existing = self.session.scalar(
                select(document_concepts.c.document_id).where(
                    and_(
                        document_concepts.c.document_id == document_id,
                        document_concepts.c.concept_id == concept_id,
                    )
                )
            )
            if existing is None:
                self.session.execute(
                    insert(document_concepts).values(
                        document_id=document_id,
                        concept_id=concept_id,
                        confidence=concept.confidence,
                        evidence_child_chunk_ids=concept.evidence_child_chunk_ids,
                    )
                )
        self.session.flush()
        return concept_id

    def _upsert_source(self, document: FixtureDocument) -> str:
        source_id = sha256_text(document.source_key)[:24]
        self._insert_if_missing(
            sources,
            source_id,
            {
                "id": source_id,
                "source_key": document.source_key,
                "source_type": _source_type_for(document.document_type),
                "title": document.source_key,
                "publisher": None,
                "homepage_url": document.source_url,
                "rss_url": None,
                "rights_policy": str(
                    document.metadata.get("license_status")
                    or document.metadata.get("rights_policy")
                    or "private_research_only"
                ),
                "created_at": _now(),
            },
        )
        return source_id

    def _upsert_document(self, document: FixtureDocument, source_id: str) -> None:
        existing = self.session.scalar(select(documents.c.id).where(documents.c.id == document.document_id))
        values: dict[str, Any] = {
            "id": document.document_id,
            "source_id": source_id,
            "document_type": document.document_type,
            "title": document.title,
            "canonical_url": document.source_url,
            "published_at": None,
            "authors_json": document.metadata.get("authors", []),
            "guests_json": document.metadata.get("guests", []),
            "abstract": document.metadata.get("abstract"),
            "license_status": str(document.metadata.get("license_status", "private_research_only")),
            "ingestion_status": "SUCCEEDED",
            "source_hash": document.raw_artifact.sha256,
            "canonical_hash": document.canonical_hash,
            "raw_path": document.raw_artifact.storage_path,
            "canonical_text_path": str(document.canonical_text_path),
            "created_at": _now(),
            "updated_at": _now(),
        }
        if existing is None:
            self.session.execute(insert(documents).values(**values))
        else:
            self.session.execute(
                update(documents)
                .where(documents.c.id == document.document_id)
                .values(updated_at=values["updated_at"], canonical_hash=document.canonical_hash)
            )

    def _upsert_raw_artifact(self, document: FixtureDocument) -> None:
        artifact = document.raw_artifact
        artifact_id = canonical_json_hash(
            {
                "document_id": document.document_id,
                "artifact_type": artifact.artifact_type,
                "sha256": artifact.sha256,
            }
        )[:32]
        self._insert_if_missing(
            raw_artifacts,
            artifact_id,
            {
                "id": artifact_id,
                "document_id": document.document_id,
                "artifact_type": artifact.artifact_type,
                "storage_path": artifact.storage_path,
                "sha256": artifact.sha256,
                "retrieved_at": _now(),
                "retrieval_method": artifact.retrieval_method,
            },
        )

    def _insert_if_missing(self, table, row_id: str, values: dict[str, Any]) -> None:
        exists = self.session.scalar(select(table.c.id).where(table.c.id == row_id))
        if exists is None:
            self.session.execute(insert(table).values(**values))

    def _child_rows(self):
        return self.session.execute(
            select(
                child_chunks.c.id.label("child_id"),
                child_chunks.c.parent_chunk_id,
                child_chunks.c.document_id,
                child_chunks.c.text,
                child_chunks.c.chunk_hash,
                parent_chunks.c.text.label("parent_text"),
                documents.c.title,
                documents.c.canonical_url,
            )
            .join(documents, documents.c.id == child_chunks.c.document_id)
            .join(parent_chunks, parent_chunks.c.id == child_chunks.c.parent_chunk_id)
        ).mappings()


def _source_type_for(document_type: str) -> str:
    if document_type == "podcast_episode":
        return "podcast"
    if document_type == "github_repo":
        return "repo"
    return document_type


def postgres_hybrid_search_sql():
    return text(
        """
        WITH query_input AS (
            SELECT
                websearch_to_tsquery('english', :query) AS ts_query,
                CAST(:query_embedding AS vector) AS query_embedding
        )
        SELECT
            child_chunks.id AS child_chunk_id,
            child_chunks.parent_chunk_id AS parent_chunk_id,
            child_chunks.document_id AS document_id,
            documents.title AS source_title,
            COALESCE(documents.canonical_url, '') AS source_url,
            child_chunks.text AS text,
            parent_chunks.text AS parent_text,
            child_chunks.chunk_hash AS chunk_hash,
            ts_rank(
                to_tsvector('english', child_chunks.text),
                query_input.ts_query
            ) AS text_score,
            CASE
                WHEN embeddings.embedding_vector IS NULL THEN 0.0
                ELSE 1.0 - (embeddings.embedding_vector <=> query_input.query_embedding)
            END AS vector_score,
            (
                ts_rank(
                    to_tsvector('english', child_chunks.text),
                    query_input.ts_query
                )
                + (
                    5.0 * CASE
                        WHEN embeddings.embedding_vector IS NULL THEN 0.0
                        ELSE 1.0 - (
                            embeddings.embedding_vector <=> query_input.query_embedding
                        )
                    END
                )
            ) AS score
        FROM child_chunks
        JOIN documents ON documents.id = child_chunks.document_id
        JOIN parent_chunks ON parent_chunks.id = child_chunks.parent_chunk_id
        LEFT JOIN embeddings
            ON embeddings.child_chunk_id = child_chunks.id
            AND embeddings.embedding_model = :embedding_model
        CROSS JOIN query_input
        WHERE
            to_tsvector('english', child_chunks.text) @@ query_input.ts_query
            OR embeddings.embedding_vector IS NOT NULL
        ORDER BY score DESC, child_chunks.id ASC
        LIMIT :limit
        """
    )


def _term_score(text: str, terms: list[str]) -> int:
    folded = text.casefold()
    return sum(1 for term in terms if term in folded)


def _search_result_from_row(row, text_score: float, vector_score: float) -> SearchResult:
    return SearchResult(
        child_chunk_id=row["child_id"],
        parent_chunk_id=row["parent_chunk_id"],
        document_id=row["document_id"],
        source_title=row["title"],
        source_url=row["canonical_url"] or "",
        text=row["text"],
        parent_text=row["parent_text"],
        chunk_hash=row["chunk_hash"],
        score=text_score + (5.0 * vector_score),
        text_score=text_score,
        vector_score=vector_score,
    )


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _vector_literal(value: list[float]) -> str:
    return "[" + ",".join(f"{float(item):.12g}" for item in value) + "]"


def _now() -> datetime:
    return datetime.now(UTC)
