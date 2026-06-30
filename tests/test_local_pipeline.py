import json
from pathlib import Path

from wzkf.pipeline.local import LocalKnowledgeFabric


def test_local_pipeline_ingests_searches_context_packs_and_exports(tmp_path: Path):
    fabric = LocalKnowledgeFabric(storage_root=tmp_path)

    podcast = fabric.ingest_signals_threads_fixture(
        Path("tests/fixtures/signals_threads/episode.html")
    )
    paper = fabric.ingest_arxiv_fixture(Path("tests/fixtures/papers/arxiv_qfin.xml"))
    repo = fabric.ingest_github_repo_fixture(
        Path("tests/fixtures/repos/janestreet_ppx_expect"),
        source_key="janestreet_ppx_expect",
        commit_hash="fixture-commit",
    )
    reuters_records = fabric.ingest_reuters_metadata_fixture(
        Path("tests/fixtures/reuters/reuters_21578_metadata.json")
    )
    academic_records = fabric.ingest_academic_metadata_fixture(
        provider="openalex",
        fixture_path=Path("tests/fixtures/academic_metadata/openalex_work.json"),
        query_id="qfin_market_microstructure",
    )

    assert {podcast.document_type, paper.document_type, repo.document_type} == {
        "podcast_episode",
        "paper",
        "github_repo",
    }
    assert [record.document_type for record in reuters_records] == ["news_dataset_record"]
    assert [record.source_key for record in academic_records] == [
        "openalex:qfin_market_microstructure"
    ]
    assert reuters_records[0].metadata["metadata_only"] is True
    assert (tmp_path / "manifests" / "corpus.json").exists()

    results = fabric.search("expect tests reviewable output", limit=5)
    assert results
    assert results[0].source_url.startswith("https://")
    assert results[0].chunk_hash

    pack = fabric.context_pack("expect tests reviewable output", created_for="codex")
    assert pack.abstain is False
    assert pack.included_child_chunk_ids

    concepts = fabric.rebuild_ontology()
    concept_names = {concept.canonical_name for concept in concepts}
    assert {"Expect Tests", "Limit Order Book"}.issubset(concept_names)
    expect_tests = next(
        concept for concept in concepts if concept.canonical_name == "Expect Tests"
    )
    assert expect_tests.evidence_child_chunk_ids
    assert expect_tests.document_ids
    assert fabric.concept_review_items() == []

    fabric.upsert_embedding(podcast.child_chunks[0].id, "test-vector", [1.0, 0.0])
    fabric.upsert_embedding(paper.child_chunks[0].id, "test-vector", [0.0, 1.0])
    hybrid_results = fabric.hybrid_search(
        "expect tests reviewable output",
        query_embedding=[0.0, 1.0],
        embedding_model="test-vector",
    )
    assert hybrid_results[0].document_id == paper.document_id
    assert hybrid_results[0].parent_text
    assert hybrid_results[0].vector_score > hybrid_results[1].vector_score

    exported = fabric.export_obsidian(changed_only=True)
    bodies = [path.read_text(encoding="utf-8") for path in exported]
    assert exported
    assert all("raw_transcript_exported: false" in body for body in bodies)
    assert any("| Claim | Evidence |" in body for body in bodies)
    assert any("Expect tests make generated output reviewable." in body for body in bodies)
    assert any("type: concept" in body for body in bodies)
    assert any("# Expect Tests" in body for body in bodies)
    assert any("aliases:" in body for body in bodies)
    assert all("This insight is backed by cited fixture evidence." not in body for body in bodies)


def test_local_pipeline_deduplicates_academic_metadata_by_doi(tmp_path: Path):
    fabric = LocalKnowledgeFabric(storage_root=tmp_path)

    openalex_docs = fabric.ingest_academic_metadata_fixture(
        provider="openalex",
        fixture_path=Path("tests/fixtures/academic_metadata/openalex_work.json"),
        query_id="qfin_market_microstructure",
    )
    unpaywall_docs = fabric.ingest_academic_metadata_fixture(
        provider="unpaywall",
        fixture_path=Path("tests/fixtures/academic_metadata/unpaywall_same_doi_as_openalex.json"),
        query_id="qfin_market_microstructure",
    )

    assert openalex_docs[0].document_id == unpaywall_docs[0].document_id

    manifest = json.loads((tmp_path / "manifests" / "corpus.json").read_text(encoding="utf-8"))
    matching_documents = [
        document
        for document in manifest["documents"].values()
        if document["metadata"].get("doi") == "10.1234/openalex-lob"
    ]

    assert len(matching_documents) == 1
    metadata = matching_documents[0]["metadata"]
    assert metadata["providers"] == ["openalex", "unpaywall"]
    assert metadata["source_urls"] == [
        "https://doi.org/10.1234/openalex-lob",
        "https://openalex.org/W123456789",
    ]
    assert metadata["pdf_urls"] == [
        "https://example.org/openalex-lob.pdf",
        "https://repository.example.org/openalex-lob.pdf",
    ]
    assert metadata["provider_sources"] == [
        {
            "external_id": "https://openalex.org/W123456789",
            "license_status": "open_access_pdf_allowed",
            "pdf_url": "https://example.org/openalex-lob.pdf",
            "provider": "openalex",
            "source_url": "https://openalex.org/W123456789",
        },
        {
            "external_id": "10.1234/openalex-lob",
            "license_status": "open_access_pdf_allowed",
            "pdf_url": "https://repository.example.org/openalex-lob.pdf",
            "provider": "unpaywall",
            "source_url": "https://doi.org/10.1234/openalex-lob",
        },
    ]
