from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from wzkf.ontology.alias_resolver import AliasResolver, ConceptReviewStatus
from wzkf.storage.hashing import canonical_json_hash


@dataclass(frozen=True)
class ConceptRecord:
    concept_id: str
    canonical_name: str
    concept_type: str
    aliases: list[str]
    confidence: float
    document_ids: list[str]
    evidence_child_chunk_ids: list[str]


@dataclass(frozen=True)
class ConceptReviewItem:
    review_id: str
    candidate_name: str
    document_id: str
    evidence_child_chunk_ids: list[str]
    confidence: float
    status: str = ConceptReviewStatus.REVIEW_REQUIRED.value


class OntologyStore:
    def __init__(
        self,
        alias_resolver: AliasResolver,
        concepts: dict[str, ConceptRecord] | None = None,
        review_items: dict[str, ConceptReviewItem] | None = None,
    ):
        self.alias_resolver = alias_resolver
        self._concepts = concepts or {}
        self._review_items = review_items or {}

    @classmethod
    def with_default_resolver(cls) -> "OntologyStore":
        return cls(AliasResolver.with_default_seed())

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> "OntologyStore":
        ontology = manifest.get("ontology", {})
        concepts = {
            key: ConceptRecord(**value)
            for key, value in ontology.get("concepts", {}).items()
        }
        review_items = {
            key: ConceptReviewItem(**value)
            for key, value in ontology.get("review_items", {}).items()
        }
        return cls(
            alias_resolver=AliasResolver.with_default_seed(),
            concepts=concepts,
            review_items=review_items,
        )

    def record_candidate(
        self,
        candidate_name: str,
        document_id: str,
        evidence_child_chunk_ids: list[str],
        concept_type: str,
    ) -> ConceptRecord | ConceptReviewItem:
        resolution = self.alias_resolver.resolve(candidate_name)
        if resolution.status == ConceptReviewStatus.REVIEW_REQUIRED:
            review_id = canonical_json_hash(
                {
                    "candidate_name": candidate_name,
                    "document_id": document_id,
                    "evidence_child_chunk_ids": evidence_child_chunk_ids,
                }
            )[:24]
            item = ConceptReviewItem(
                review_id=review_id,
                candidate_name=candidate_name,
                document_id=document_id,
                evidence_child_chunk_ids=_unique(evidence_child_chunk_ids),
                confidence=resolution.confidence,
            )
            self._review_items.setdefault(review_id, item)
            return self._review_items[review_id]

        concept_id = canonical_json_hash({"canonical_name": resolution.canonical_name})[:24]
        existing = self._concepts.get(concept_id)
        if existing is None:
            record = ConceptRecord(
                concept_id=concept_id,
                canonical_name=resolution.canonical_name,
                concept_type=concept_type,
                aliases=[candidate_name],
                confidence=resolution.confidence,
                document_ids=[document_id],
                evidence_child_chunk_ids=_unique(evidence_child_chunk_ids),
            )
        else:
            record = ConceptRecord(
                concept_id=concept_id,
                canonical_name=existing.canonical_name,
                concept_type=existing.concept_type,
                aliases=_unique([*existing.aliases, candidate_name]),
                confidence=max(existing.confidence, resolution.confidence),
                document_ids=_unique([*existing.document_ids, document_id]),
                evidence_child_chunk_ids=_unique(
                    [*existing.evidence_child_chunk_ids, *evidence_child_chunk_ids]
                ),
            )
        self._concepts[concept_id] = record
        return record

    def concepts(self) -> list[ConceptRecord]:
        return sorted(self._concepts.values(), key=lambda item: item.canonical_name)

    def review_items(self) -> list[ConceptReviewItem]:
        return sorted(self._review_items.values(), key=lambda item: item.candidate_name)

    def get_concept(self, concept_id: str) -> ConceptRecord | None:
        return self._concepts.get(concept_id)

    def to_manifest(self) -> dict[str, Any]:
        return {
            "concepts": {
                concept_id: asdict(record)
                for concept_id, record in sorted(self._concepts.items())
            },
            "review_items": {
                review_id: asdict(item)
                for review_id, item in sorted(self._review_items.items())
            },
        }


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value not in seen:
            unique_values.append(value)
            seen.add(value)
    return unique_values
