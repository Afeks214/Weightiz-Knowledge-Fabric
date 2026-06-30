from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from wzkf.db.models import (
    child_chunks,
    context_packs,
    cost_ledger,
    documents,
    embeddings,
    metadata,
    parent_chunks,
    processing_jobs,
    raw_artifacts,
    sources,
)
from wzkf.db.repositories import KnowledgeRepository
from wzkf.extraction.claims import ClaimExtractionV1
from wzkf.ingest.fixture_ingestor import FixtureIngestor
from wzkf.retrieval.context_pack import ContextPackBuilder


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    with maker() as db:
        yield db


def count_rows(session, table) -> int:
    return session.scalar(select(func.count()).select_from(table))


def test_repository_persists_fixture_document_idempotently(session, tmp_path: Path):
    fixture = FixtureIngestor(tmp_path).ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    repo = KnowledgeRepository(session)

    first = repo.upsert_fixture_document(fixture)
    second = repo.upsert_fixture_document(fixture)

    assert first.document_id == second.document_id == fixture.document_id
    assert count_rows(session, sources) == 1
    assert count_rows(session, documents) == 1
    assert count_rows(session, raw_artifacts) == 1
    assert count_rows(session, parent_chunks) == len(fixture.parent_chunks)
    assert count_rows(session, child_chunks) == len(fixture.child_chunks)


def test_repository_search_returns_child_citations_with_parent_context(session, tmp_path: Path):
    fixture = FixtureIngestor(tmp_path).ingest_github_repo_fixture(
        Path("tests/fixtures/repos/janestreet_ppx_expect"),
        source_key="janestreet_ppx_expect",
        commit_hash="fixture-commit",
    )
    repo = KnowledgeRepository(session)
    repo.upsert_fixture_document(fixture)

    results = repo.search_child_chunks("expect tests reviewable output", limit=3)

    assert results
    child_by_id = {chunk.id: chunk for chunk in fixture.child_chunks}
    parent_by_id = {chunk.id: chunk for chunk in fixture.parent_chunks}
    returned_child = child_by_id[results[0].child_chunk_id]
    returned_parent = parent_by_id[returned_child.parent_chunk_id]

    assert results[0].document_id == fixture.document_id
    assert results[0].child_chunk_id in child_by_id
    assert results[0].parent_chunk_id == returned_parent.id
    assert results[0].source_url == fixture.source_url
    assert results[0].chunk_hash == returned_child.chunk_hash
    assert results[0].parent_text == returned_parent.text


def test_repository_idempotently_records_embeddings_claims_jobs_costs_and_context_pack(
    session,
    tmp_path: Path,
):
    fixture = FixtureIngestor(tmp_path).ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    repo = KnowledgeRepository(session)
    repo.upsert_fixture_document(fixture)
    child_id = fixture.child_chunks[0].id

    repo.upsert_embedding(child_id, "mock-hash-embedding-v1", [0.1, 0.2])
    repo.upsert_embedding(child_id, "mock-hash-embedding-v1", [0.1, 0.2])
    assert count_rows(session, embeddings) == 1

    claim = ClaimExtractionV1(
        document_id=fixture.document_id,
        claim_text="Official transcript text is preferred over audio transcription.",
        claim_type="method",
        confidence=0.9,
        extraction_model="fixture-extractor",
        evidence_child_chunk_ids=[child_id],
    )
    repo.upsert_claim(claim, parent_chunk_id=fixture.parent_chunks[0].id)
    repo.upsert_claim(claim, parent_chunk_id=fixture.parent_chunks[0].id)
    assert repo.count_claims() == 1

    job = repo.upsert_processing_job(
        job_type="embed_document",
        document_id=fixture.document_id,
        input_hash=fixture.canonical_hash,
        status="SUCCEEDED",
    )
    repeat = repo.upsert_processing_job(
        job_type="embed_document",
        document_id=fixture.document_id,
        input_hash=fixture.canonical_hash,
        status="SUCCEEDED",
    )
    assert job == repeat
    assert count_rows(session, processing_jobs) == 1

    repo.record_cost(job, provider="mock", model="mock-hash-embedding-v1", estimated_cost_usd=0.0)
    repo.record_cost(job, provider="mock", model="mock-hash-embedding-v1", estimated_cost_usd=0.0)
    assert count_rows(session, cost_ledger) == 1

    pack = ContextPackBuilder().build(
        "official transcript",
        repo.search_child_chunks("official transcript", limit=2),
        created_for="codex",
    )
    repo.upsert_context_pack(pack)
    repo.upsert_context_pack(pack)
    assert count_rows(session, context_packs) == 1


def test_repository_hybrid_search_combines_text_and_vector_scores(session, tmp_path: Path):
    repo = KnowledgeRepository(session)
    first = FixtureIngestor(tmp_path / "a").ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    second = FixtureIngestor(tmp_path / "b").ingest_arxiv_fixture(
        Path("tests/fixtures/papers/arxiv_qfin.xml")
    )
    repo.upsert_fixture_document(first)
    repo.upsert_fixture_document(second)
    repo.upsert_embedding(first.child_chunks[0].id, "test-vector", [1.0, 0.0])
    repo.upsert_embedding(second.child_chunks[0].id, "test-vector", [0.0, 1.0])

    results = repo.hybrid_search_child_chunks(
        query="reviewable output",
        query_embedding=[0.0, 1.0],
        embedding_model="test-vector",
        limit=2,
    )

    assert [result.document_id for result in results] == [
        second.document_id,
        first.document_id,
    ]
    assert results[0].vector_score > results[1].vector_score
    assert results[1].text_score > results[0].text_score
