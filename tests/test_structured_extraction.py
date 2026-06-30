from wzkf.chunking.parent_child import ChildChunk
from wzkf.extraction.structured import EvidenceBoundExtractor


def test_structured_extractor_returns_evidence_bound_items():
    chunk = ChildChunk(
        id="child-expect",
        parent_chunk_id="parent-expect",
        document_id="doc-expect",
        child_index=0,
        text=(
            "Expect tests make generated output reviewable. "
            "For Weightiz, artifact hashes and citations should be preserved."
        ),
        token_count=14,
        chunk_hash="sha256:child",
    )

    extraction = EvidenceBoundExtractor().extract("doc-expect", [chunk])

    assert extraction.abstain is False
    assert extraction.summary.evidence_child_chunk_ids == ["child-expect"]
    assert extraction.claims[0].evidence_child_chunk_ids == ["child-expect"]
    assert extraction.concepts[0].canonical_name == "Expect Tests"
    assert extraction.weightiz_hooks[0].allowed_use == "research_only"
    assert extraction.weightiz_hooks[0].evidence_child_chunk_ids == ["child-expect"]


def test_structured_extractor_abstains_without_chunks():
    extraction = EvidenceBoundExtractor().extract("doc-empty", [])

    assert extraction.abstain is True
    assert extraction.abstain_reason == "No evidence chunks were provided."
    assert extraction.claims == []
    assert extraction.weightiz_hooks == []
