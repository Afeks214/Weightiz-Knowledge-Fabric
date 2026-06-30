from wzkf.ontology.store import OntologyStore


def test_ontology_store_merges_aliases_into_one_canonical_concept():
    store = OntologyStore.with_default_resolver()

    first = store.record_candidate(
        candidate_name="LOB",
        document_id="doc-1",
        evidence_child_chunk_ids=["child-1"],
        concept_type="market_microstructure",
    )
    second = store.record_candidate(
        candidate_name="Market Depth",
        document_id="doc-1",
        evidence_child_chunk_ids=["child-2"],
        concept_type="market_microstructure",
    )

    concepts = store.concepts()

    assert first.concept_id == second.concept_id
    assert len(concepts) == 1
    assert concepts[0].canonical_name == "Limit Order Book"
    assert concepts[0].aliases == ["LOB", "Market Depth"]
    assert concepts[0].document_ids == ["doc-1"]
    assert concepts[0].evidence_child_chunk_ids == ["child-1", "child-2"]
    assert concepts[0].confidence == 1.0


def test_ontology_store_routes_unknown_candidates_to_review_queue():
    store = OntologyStore.with_default_resolver()

    review = store.record_candidate(
        candidate_name="queue-reactive fill model",
        document_id="doc-2",
        evidence_child_chunk_ids=["child-9"],
        concept_type="research_method",
    )

    assert review.status == "REVIEW_REQUIRED"
    assert review.candidate_name == "queue-reactive fill model"
    assert review.document_id == "doc-2"
    assert review.evidence_child_chunk_ids == ["child-9"]
    assert review.confidence == 0.5
    assert store.concepts() == []
    assert store.review_items() == [review]
