from pathlib import Path

from fastapi.testclient import TestClient

import wzkf.api.main as api_main
from wzkf.api.main import create_app
from wzkf.pipeline.local import LocalKnowledgeFabric
from wzkf.retrieval.hybrid_search import SearchResult


def test_api_health_and_context_pack_abstain(tmp_path: Path):
    client = TestClient(create_app(storage_root=tmp_path))

    assert client.get("/health").json() == {"status": "ok"}

    response = client.post(
        "/context-packs",
        json={"query": "missing evidence", "created_for": "codex"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["abstain"] is True
    assert body["pack_hash"]


def test_api_search_context_pack_and_document_routes_use_local_corpus(tmp_path: Path):
    document = LocalKnowledgeFabric(tmp_path).ingest_github_repo_fixture(
        Path("tests/fixtures/repos/janestreet_ppx_expect"),
        source_key="janestreet_ppx_expect",
        commit_hash="fixture-commit",
    )
    client = TestClient(create_app(storage_root=tmp_path))

    search = client.get("/search", params={"query": "expect tests reviewable output"})
    assert search.status_code == 200
    search_body = search.json()
    assert search_body["abstain"] is False
    assert search_body["results"][0]["document_id"] == document.document_id
    assert search_body["results"][0]["child_chunk_id"]

    pack = client.post(
        "/context-packs",
        json={"query": "expect tests reviewable output", "created_for": "claude"},
    )
    pack_body = pack.json()
    assert pack.status_code == 200
    assert pack_body["abstain"] is False
    assert pack_body["included_child_chunk_ids"]

    doc = client.get(f"/documents/{document.document_id}")
    assert doc.status_code == 200
    assert doc.json()["document_id"] == document.document_id

    concepts = client.get("/concepts")
    assert concepts.status_code == 200
    concept_body = concepts.json()
    assert concept_body["review_items"] == []
    assert concept_body["concepts"][0]["canonical_name"] == "Expect Tests"
    assert concept_body["concepts"][0]["evidence_child_chunk_ids"]

    concept_id = concept_body["concepts"][0]["concept_id"]
    concept = client.get(f"/concepts/{concept_id}")
    assert concept.status_code == 200
    assert concept.json()["canonical_name"] == "Expect Tests"


def test_api_search_uses_live_postgres_when_database_url_is_configured(
    tmp_path: Path,
    monkeypatch,
):
    captured = {}

    def fake_live_postgres_search(
        query,
        database_url,
        embedding_model,
        query_embedding,
        limit,
    ):
        captured.update(
            {
                "query": query,
                "database_url": database_url,
                "embedding_model": embedding_model,
                "query_embedding": query_embedding,
                "limit": limit,
            }
        )
        return [
            SearchResult(
                child_chunk_id="child-live",
                parent_chunk_id="parent-live",
                document_id="doc-live",
                source_title="Live Source",
                source_url="https://example.com/live",
                text="child text",
                parent_text="parent text",
                chunk_hash="hash-live",
                score=5.5,
                text_score=0.5,
                vector_score=1.0,
            )
        ]

    monkeypatch.setattr(api_main, "live_postgres_search", fake_live_postgres_search)
    client = TestClient(create_app(storage_root=tmp_path, database_url="postgresql://live"))

    response = client.get(
        "/search",
        params={
            "query": "limit order book",
            "embedding_model": "test-vector",
            "query_embedding": "0,1",
            "limit": "3",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["abstain"] is False
    assert body["results"][0]["child_chunk_id"] == "child-live"
    assert body["results"][0]["parent_chunk_id"] == "parent-live"
    assert body["results"][0]["document_id"] == "doc-live"
    assert body["results"][0]["source_url"] == "https://example.com/live"
    assert body["results"][0]["chunk_hash"] == "hash-live"
    assert body["results"][0]["score"] == 5.5
    assert captured == {
        "query": "limit order book",
        "database_url": "postgresql://live",
        "embedding_model": "test-vector",
        "query_embedding": [0.0, 1.0],
        "limit": 3,
    }


def test_api_context_pack_uses_live_postgres_when_database_url_is_configured(
    tmp_path: Path,
    monkeypatch,
):
    def fake_live_postgres_search(
        query,
        database_url,
        embedding_model,
        query_embedding,
        limit,
    ):
        return [
            SearchResult(
                child_chunk_id="child-live",
                parent_chunk_id="parent-live",
                document_id="doc-live",
                source_title="Live Source",
                source_url="https://example.com/live",
                text="child text",
                parent_text="parent cited text",
                chunk_hash="hash-live",
                score=5.5,
                text_score=0.5,
                vector_score=1.0,
            )
        ]

    monkeypatch.setattr(api_main, "live_postgres_search", fake_live_postgres_search)
    client = TestClient(create_app(storage_root=tmp_path, database_url="postgresql://live"))

    response = client.post(
        "/context-packs",
        json={
            "query": "limit order book",
            "created_for": "api-test",
            "embedding_model": "test-vector",
            "query_embedding": "0,1",
            "limit": 3,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["abstain"] is False
    assert body["included_child_chunk_ids"] == ["child-live"]
    assert body["included_chunks"][0]["parent_chunk_id"] == "parent-live"
    assert body["included_chunks"][0]["source_url"] == "https://example.com/live"
    assert body["included_chunks"][0]["chunk_hash"] == "hash-live"


def test_api_job_and_cost_routes_process_document_once(tmp_path: Path):
    document = LocalKnowledgeFabric(tmp_path).ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    child_count = len(document.child_chunks)
    client = TestClient(create_app(storage_root=tmp_path))

    created = client.post("/jobs/embed-document", json={"document_id": document.document_id})
    repeat = client.post("/jobs/embed-document", json={"document_id": document.document_id})

    assert created.status_code == 200
    assert repeat.status_code == 200
    assert created.json()["id"] == repeat.json()["id"]
    assert created.json()["status"] == "PENDING"

    status = client.get("/jobs/status")
    assert status.status_code == 200
    assert status.json()["total"] == 1
    assert status.json()["pending"] == 1

    run = client.post("/jobs/run-pending")
    assert run.status_code == 200
    assert run.json() == {"failed": 0, "skipped": 0, "succeeded": 1}

    finished = client.get("/jobs/status")
    assert finished.status_code == 200
    assert finished.json()["pending"] == 0
    assert finished.json()["succeeded"] == 1

    costs = client.get("/costs")
    assert costs.status_code == 200
    assert costs.json()["operations"] == child_count
    assert costs.json()["estimated_cost_usd"] == 0.0

    second_run = client.post("/jobs/run-pending")
    assert second_run.status_code == 200
    assert second_run.json() == {"failed": 0, "skipped": 0, "succeeded": 0}
