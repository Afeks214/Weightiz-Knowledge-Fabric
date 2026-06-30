import pytest
from pydantic import ValidationError

from wzkf.extraction.claims import ClaimExtractionV1


def test_claim_without_evidence_is_rejected_unless_abstained():
    with pytest.raises(ValidationError):
        ClaimExtractionV1(
            document_id="doc-1",
            claim_text="Expect tests make generated artifacts reviewable.",
            claim_type="method",
            confidence=0.8,
            extraction_model="mock-llm",
            evidence_child_chunk_ids=[],
        )


def test_abstain_claim_can_have_no_evidence_when_reason_is_present():
    claim = ClaimExtractionV1(
        document_id="doc-1",
        claim_text="ABSTAIN",
        claim_type="abstain",
        confidence=0.0,
        extraction_model="mock-llm",
        evidence_child_chunk_ids=[],
        abstain_reason="No evidence chunks matched the requested claim.",
    )

    assert claim.abstain_reason is not None
