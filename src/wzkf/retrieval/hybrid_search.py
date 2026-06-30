from pydantic import BaseModel

from wzkf.chunking.parent_child import ChildChunk


class SearchResult(BaseModel):
    child_chunk_id: str
    parent_chunk_id: str
    document_id: str
    source_title: str
    source_url: str
    text: str
    parent_text: str | None = None
    chunk_hash: str
    score: float
    text_score: float = 0.0
    vector_score: float = 0.0


class HybridSearch:
    def __init__(self, results: list[SearchResult]):
        self.results = results

    @classmethod
    def from_child_chunks(
        cls,
        chunks: list[ChildChunk],
        source_title: str,
        source_url: str,
    ) -> "HybridSearch":
        results = [
            SearchResult(
                child_chunk_id=chunk.id,
                parent_chunk_id=chunk.parent_chunk_id,
                document_id=chunk.document_id,
                source_title=source_title,
                source_url=source_url,
                text=chunk.text,
                parent_text=None,
                chunk_hash=chunk.chunk_hash,
                score=0.0,
            )
            for chunk in chunks
        ]
        return cls(results)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        terms = {term.casefold() for term in query.split()}
        scored: list[SearchResult] = []
        for result in self.results:
            text_terms = {term.casefold().strip(".,:;()[]") for term in result.text.split()}
            overlap = len(terms & text_terms)
            if overlap:
                scored.append(result.model_copy(update={"score": result.score + overlap}))
        return sorted(scored, key=lambda item: (-item.score, item.child_chunk_id))[:limit]
