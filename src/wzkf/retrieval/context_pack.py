from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from wzkf.retrieval.hybrid_search import SearchResult
from wzkf.storage.hashing import canonical_json_hash


class ContextChunk(BaseModel):
    child_chunk_id: str
    parent_chunk_id: str
    document_id: str
    source_title: str
    source_url: str
    text: str
    child_text: str
    chunk_hash: str


class ContextPack(BaseModel):
    query: str
    pack_hash: str
    included_chunks: list[ContextChunk] = Field(default_factory=list)
    included_child_chunk_ids: list[str] = Field(default_factory=list)
    created_for: str
    created_at: datetime
    abstain: bool = False
    abstain_reason: str | None = None


class ContextPackBuilder:
    def build(self, query: str, results: list[SearchResult], created_for: str) -> ContextPack:
        ordered = sorted(results, key=lambda item: (-item.score, item.child_chunk_id))
        chunks = [
            ContextChunk(
                child_chunk_id=item.child_chunk_id,
                parent_chunk_id=item.parent_chunk_id,
                document_id=item.document_id,
                source_title=item.source_title,
                source_url=item.source_url,
                text=item.parent_text or item.text,
                child_text=item.text,
                chunk_hash=item.chunk_hash,
            )
            for item in ordered
        ]
        abstain = not chunks
        payload = {
            "query": query,
            "created_for": created_for,
            "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
            "abstain": abstain,
        }
        return ContextPack(
            query=query,
            pack_hash=canonical_json_hash(payload),
            included_chunks=chunks,
            included_child_chunk_ids=[chunk.child_chunk_id for chunk in chunks],
            created_for=created_for,
            created_at=datetime.now(UTC),
            abstain=abstain,
            abstain_reason="No cited evidence chunks matched the query." if abstain else None,
        )
