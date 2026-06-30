from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from wzkf.chunking.parent_child import ChildChunk
from wzkf.extraction.claims import ClaimExtractionV1
from wzkf.ontology.alias_resolver import AliasResolver


class EvidenceBoundText(BaseModel):
    text: str
    evidence_child_chunk_ids: list[str]

    @model_validator(mode="after")
    def require_evidence(self) -> "EvidenceBoundText":
        if not self.evidence_child_chunk_ids:
            raise ValueError("evidence_child_chunk_ids are required")
        return self


class ExtractedConcept(BaseModel):
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_child_chunk_ids: list[str]


class WeightizIdeaHook(BaseModel):
    idea: str
    why_it_matters: str
    related_concepts: list[str]
    allowed_use: str = "research_only"
    evidence_child_chunk_ids: list[str]
    risk_of_misinterpretation: str

    @model_validator(mode="after")
    def require_evidence(self) -> "WeightizIdeaHook":
        if not self.evidence_child_chunk_ids:
            raise ValueError("Weightiz hooks require evidence_child_chunk_ids")
        return self


class StructuredExtraction(BaseModel):
    document_id: str
    abstain: bool
    abstain_reason: str | None = None
    summary: EvidenceBoundText | None = None
    technical_summary: EvidenceBoundText | None = None
    concepts: list[ExtractedConcept] = Field(default_factory=list)
    claims: list[ClaimExtractionV1] = Field(default_factory=list)
    methods: list[EvidenceBoundText] = Field(default_factory=list)
    caveats: list[EvidenceBoundText] = Field(default_factory=list)
    formulas: list[EvidenceBoundText] = Field(default_factory=list)
    implementation_patterns: list[EvidenceBoundText] = Field(default_factory=list)
    weightiz_hooks: list[WeightizIdeaHook] = Field(default_factory=list)


class EvidenceBoundExtractor:
    def __init__(self, alias_resolver: AliasResolver | None = None):
        self.alias_resolver = alias_resolver or AliasResolver.with_default_seed()

    def extract(self, document_id: str, child_chunks: list[ChildChunk]) -> StructuredExtraction:
        if not child_chunks:
            return StructuredExtraction(
                document_id=document_id,
                abstain=True,
                abstain_reason="No evidence chunks were provided.",
            )

        first = child_chunks[0]
        evidence_ids = [first.id]
        summary_text = _salient_sentence(first.text)
        concepts = self._extract_concepts(first)
        claims = [
            ClaimExtractionV1(
                document_id=document_id,
                claim_text=summary_text,
                claim_type="method" if "test" in first.text.casefold() else "claim",
                confidence=0.7,
                extraction_model="deterministic-fixture-extractor-v1",
                evidence_child_chunk_ids=evidence_ids,
            )
        ]
        return StructuredExtraction(
            document_id=document_id,
            abstain=False,
            summary=EvidenceBoundText(text=summary_text, evidence_child_chunk_ids=evidence_ids),
            technical_summary=EvidenceBoundText(text=first.text, evidence_child_chunk_ids=evidence_ids),
            concepts=concepts,
            claims=claims,
            methods=_methods_from(first),
            caveats=_caveats_from(first),
            formulas=_formulas_from(first),
            implementation_patterns=_patterns_from(first),
            weightiz_hooks=_weightiz_hooks_from(first, concepts),
        )

    def _extract_concepts(self, chunk: ChildChunk) -> list[ExtractedConcept]:
        candidates: list[str] = []
        text = chunk.text.casefold()
        if "expect" in text:
            candidates.append("Expect Tests")
        if "order book" in text or "market depth" in text or "lob" in text:
            candidates.append("Limit Order Book")
        concepts: list[ExtractedConcept] = []
        for candidate in candidates:
            resolution = self.alias_resolver.resolve(candidate)
            concepts.append(
                ExtractedConcept(
                    canonical_name=resolution.canonical_name,
                    aliases=[] if resolution.matched_alias is None else [resolution.matched_alias],
                    confidence=resolution.confidence,
                    evidence_child_chunk_ids=[chunk.id],
                )
            )
        return concepts


def _first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if "." not in cleaned:
        return cleaned
    return cleaned.split(".", 1)[0] + "."


def _salient_sentence(text: str) -> str:
    candidates: list[str] = []
    for line in text.splitlines():
        for sentence in line.split("."):
            cleaned = " ".join(sentence.split()).strip()
            if cleaned:
                candidates.append(cleaned + ".")
    for keyword in ["expect tests", "limit order book", "market depth", "weightiz"]:
        for sentence in candidates:
            if keyword in sentence.casefold():
                return sentence
    return _first_sentence(text)


def _methods_from(chunk: ChildChunk) -> list[EvidenceBoundText]:
    if "test" not in chunk.text.casefold() and "method" not in chunk.text.casefold():
        return []
    return [EvidenceBoundText(text=_salient_sentence(chunk.text), evidence_child_chunk_ids=[chunk.id])]


def _caveats_from(chunk: ChildChunk) -> list[EvidenceBoundText]:
    if "caveat" not in chunk.text.casefold() and "risk" not in chunk.text.casefold():
        return []
    return [EvidenceBoundText(text=_first_sentence(chunk.text), evidence_child_chunk_ids=[chunk.id])]


def _formulas_from(chunk: ChildChunk) -> list[EvidenceBoundText]:
    if "$$" not in chunk.text and "=" not in chunk.text:
        return []
    return [EvidenceBoundText(text=chunk.text, evidence_child_chunk_ids=[chunk.id])]


def _patterns_from(chunk: ChildChunk) -> list[EvidenceBoundText]:
    if "artifact" not in chunk.text.casefold() and "implementation" not in chunk.text.casefold():
        return []
    return [EvidenceBoundText(text=_salient_sentence(chunk.text), evidence_child_chunk_ids=[chunk.id])]


def _weightiz_hooks_from(
    chunk: ChildChunk,
    concepts: list[ExtractedConcept],
) -> list[WeightizIdeaHook]:
    if "weightiz" not in chunk.text.casefold():
        return []
    return [
        WeightizIdeaHook(
            idea=_salient_sentence(chunk.text),
            why_it_matters="Connects a source-backed research idea to Weightiz artifact validation.",
            related_concepts=[concept.canonical_name for concept in concepts],
            evidence_child_chunk_ids=[chunk.id],
            risk_of_misinterpretation="Research-only hook; not a trading recommendation or live decision.",
        )
    ]
