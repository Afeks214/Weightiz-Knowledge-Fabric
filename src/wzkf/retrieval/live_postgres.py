from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from wzkf.db.repositories import KnowledgeRepository
from wzkf.retrieval.embeddings import MockEmbeddingProvider
from wzkf.retrieval.hybrid_search import SearchResult


def resolve_query_embedding(query: str, query_embedding: str | Sequence[float] | None) -> list[float]:
    if query_embedding is None:
        return MockEmbeddingProvider().embed(query)
    if isinstance(query_embedding, str):
        stripped = query_embedding.strip().removeprefix("[").removesuffix("]")
        if not stripped:
            raise ValueError("query_embedding must contain at least one number")
        return [float(part.strip()) for part in stripped.split(",") if part.strip()]
    return [float(value) for value in query_embedding]


def live_postgres_search(
    query: str,
    database_url: str,
    embedding_model: str,
    query_embedding: list[float],
    limit: int = 10,
) -> list[SearchResult]:
    engine = create_engine(database_url)
    maker = sessionmaker(bind=engine)
    with maker() as session:
        return KnowledgeRepository(session).postgres_hybrid_search_child_chunks(
            query=query,
            query_embedding=query_embedding,
            embedding_model=embedding_model,
            limit=limit,
        )
