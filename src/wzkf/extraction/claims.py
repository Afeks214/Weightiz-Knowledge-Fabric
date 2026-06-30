from pydantic import BaseModel, Field, model_validator


class ClaimExtractionV1(BaseModel):
    document_id: str
    claim_text: str
    claim_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_model: str
    evidence_child_chunk_ids: list[str] = Field(default_factory=list)
    speaker: str | None = None
    speaker_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    abstain_reason: str | None = None

    @model_validator(mode="after")
    def require_evidence_or_abstain(self) -> "ClaimExtractionV1":
        if not self.evidence_child_chunk_ids and not self.abstain_reason:
            raise ValueError("extracted claims require evidence_child_chunk_ids or an abstain_reason")
        return self
