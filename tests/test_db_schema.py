from wzkf.db.models import metadata


def test_core_tables_exist_in_metadata():
    expected = {
        "sources",
        "documents",
        "raw_artifacts",
        "parent_chunks",
        "child_chunks",
        "embeddings",
        "concepts",
        "concept_aliases",
        "claims",
        "jobs",
        "costs",
        "context_packs",
    }

    assert expected.issubset(set(metadata.tables))


def test_claims_table_requires_evidence_column():
    claims = metadata.tables["claims"]

    assert "evidence_child_chunk_ids" in claims.c


def test_embeddings_table_has_pgvector_column_for_live_search():
    embeddings = metadata.tables["embeddings"]

    assert "embedding_vector" in embeddings.c
