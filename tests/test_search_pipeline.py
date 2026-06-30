from pathlib import Path

from wzkf.ingest.fixture_ingestor import FixtureIngestor
from wzkf.retrieval.embeddings import MockEmbeddingProvider
from wzkf.retrieval.hybrid_search import HybridSearch


def test_mock_embeddings_are_deterministic():
    provider = MockEmbeddingProvider()

    assert provider.embed("expect tests") == provider.embed("expect tests")
    assert provider.embed("expect tests") != provider.embed("market depth")


def test_hybrid_search_from_ingested_chunks_returns_citations(tmp_path: Path):
    document = FixtureIngestor(storage_root=tmp_path).ingest_github_repo_fixture(
        repo_root=Path("tests/fixtures/repos/janestreet_ppx_expect"),
        source_key="janestreet_ppx_expect",
        commit_hash="fixture-commit",
    )
    search = HybridSearch.from_child_chunks(
        document.child_chunks,
        source_title=document.title,
        source_url=document.source_url,
    )

    results = search.search("expect tests reviewable output", limit=3)

    assert results
    assert results[0].document_id == document.document_id
    assert results[0].child_chunk_id
    assert results[0].parent_chunk_id
    assert results[0].source_url == document.source_url
    assert results[0].chunk_hash
