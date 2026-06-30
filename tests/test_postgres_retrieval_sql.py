from wzkf.db import repositories


def test_postgres_hybrid_search_sql_uses_fts_and_pgvector():
    assert hasattr(repositories, "postgres_hybrid_search_sql")

    sql = str(repositories.postgres_hybrid_search_sql())

    assert "websearch_to_tsquery" in sql
    assert "to_tsvector" in sql
    assert "ts_rank(" in sql
    assert "<=>" in sql
    assert "embedding_vector" in sql
    assert "child_chunk_id" in sql
    assert "parent_chunk_id" in sql
    assert "document_id" in sql
    assert "source_url" in sql
    assert "chunk_hash" in sql
    assert "score" in sql
