from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from wzkf.chunking.parent_child import ChildChunk
from wzkf.export.obsidian import ObsidianConcept, ObsidianExporter, ObsidianInsight
from wzkf.extraction.structured import EvidenceBoundExtractor
from wzkf.harvesters.academic_metadata import AcademicMetadataHarvester
from wzkf.harvesters.reuters_dataset import ReutersMetadataHarvester
from wzkf.ingest.fixture_ingestor import FixtureDocument, FixtureIngestor
from wzkf.ontology.store import ConceptRecord, ConceptReviewItem, OntologyStore
from wzkf.retrieval.context_pack import ContextPack, ContextPackBuilder
from wzkf.retrieval.hybrid_search import HybridSearch, SearchResult


class LocalKnowledgeFabric:
    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        self.manifest_path = self.storage_root / "manifests" / "corpus.json"
        self.ingestor = FixtureIngestor(self.storage_root)

    def ingest_signals_threads_fixture(self, fixture_path: Path) -> FixtureDocument:
        return self._record(self.ingestor.ingest_signals_threads_fixture(fixture_path))

    def ingest_arxiv_fixture(self, fixture_path: Path) -> FixtureDocument:
        return self._record(self.ingestor.ingest_arxiv_fixture(fixture_path))

    def ingest_github_repo_fixture(
        self,
        repo_root: Path,
        source_key: str,
        commit_hash: str,
    ) -> FixtureDocument:
        return self._record(
            self.ingestor.ingest_github_repo_fixture(repo_root, source_key, commit_hash)
        )

    def ingest_reuters_metadata_fixture(self, fixture_path: Path) -> list[FixtureDocument]:
        records = ReutersMetadataHarvester().parse(Path(fixture_path).read_text(encoding="utf-8"))
        return [
            self._record(self.ingestor.ingest_reuters_metadata_record(record))
            for record in records
        ]

    def ingest_academic_metadata_fixture(
        self,
        provider: str,
        fixture_path: Path,
        query_id: str,
    ) -> list[FixtureDocument]:
        records = AcademicMetadataHarvester(provider=provider, query_id=query_id).parse(
            Path(fixture_path).read_text(encoding="utf-8")
        )
        return [
            self._record(self.ingestor.ingest_academic_metadata_record(record))
            for record in records
        ]

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        return self._search_index().search(query, limit=limit)

    def upsert_embedding(
        self,
        child_chunk_id: str,
        embedding_model: str,
        embedding: list[float],
    ) -> None:
        manifest = self._load()
        manifest.setdefault("embeddings", {})
        manifest["embeddings"][f"{embedding_model}:{child_chunk_id}"] = {
            "child_chunk_id": child_chunk_id,
            "embedding_model": embedding_model,
            "embedding": embedding,
        }
        self._write_manifest(manifest)

    def embedding_count(self) -> int:
        return len(self._load().get("embeddings", {}))

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        embedding_model: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        terms = [term.casefold() for term in query.split() if term.strip()]
        manifest = self._load()
        embeddings = manifest.get("embeddings", {})
        results: list[SearchResult] = []
        for result in self._all_results():
            key = f"{embedding_model}:{result.child_chunk_id}"
            vector_score = _cosine(query_embedding, embeddings.get(key, {}).get("embedding", []))
            text_score = float(_term_score(result.text, terms))
            if text_score <= 0 and vector_score <= 0:
                continue
            results.append(
                result.model_copy(
                    update={
                        "text_score": text_score,
                        "vector_score": vector_score,
                        "score": text_score + (5.0 * vector_score),
                    }
                )
            )
        return sorted(results, key=lambda item: (-item.score, item.child_chunk_id))[:limit]

    def context_pack(self, query: str, created_for: str) -> ContextPack:
        return ContextPackBuilder().build(query, self.search(query), created_for=created_for)

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        return self._load()["documents"].get(document_id)

    def rebuild_ontology(self) -> list[ConceptRecord]:
        manifest = self._load()
        store = OntologyStore.with_default_resolver()
        extractor = EvidenceBoundExtractor()
        for document in manifest["documents"].values():
            chunks = [_child_chunk_from_json(chunk) for chunk in document.get("child_chunks", [])]
            extraction = extractor.extract(document["document_id"], chunks)
            for concept in extraction.concepts:
                candidate = concept.aliases[0] if concept.aliases else concept.canonical_name
                store.record_candidate(
                    candidate_name=candidate,
                    document_id=document["document_id"],
                    evidence_child_chunk_ids=concept.evidence_child_chunk_ids,
                    concept_type="extracted_concept",
                )
        manifest["ontology"] = store.to_manifest()
        self._write_manifest(manifest)
        return store.concepts()

    def concepts(self) -> list[ConceptRecord]:
        store = self._ontology_store()
        if not store.concepts() and self._load()["documents"]:
            return self.rebuild_ontology()
        return store.concepts()

    def concept_review_items(self) -> list[ConceptReviewItem]:
        store = self._ontology_store()
        if not store.concepts() and not store.review_items() and self._load()["documents"]:
            self.rebuild_ontology()
            store = self._ontology_store()
        return store.review_items()

    def get_concept(self, concept_id: str) -> ConceptRecord | None:
        store = self._ontology_store()
        concept = store.get_concept(concept_id)
        if concept is None and self._load()["documents"]:
            self.rebuild_ontology()
            concept = self._ontology_store().get_concept(concept_id)
        return concept

    def export_obsidian(self, changed_only: bool = True) -> list[Path]:
        exporter = ObsidianExporter(self.storage_root / "obsidian_export")
        paths: list[Path] = []
        concepts = self.rebuild_ontology()
        for document in self._load()["documents"].values():
            chunks = [_child_chunk_from_json(chunk) for chunk in document.get("child_chunks", [])]
            extraction = EvidenceBoundExtractor().extract(document["document_id"], chunks)
            claims = [
                (claim.claim_text, claim.evidence_child_chunk_ids) for claim in extraction.claims
            ]
            summary = (
                extraction.summary.text
                if extraction.summary is not None
                else "ABSTAIN: no evidence chunks were available for this document."
            )
            insight = ObsidianInsight(
                note_type=f"{document['document_type']}_insight",
                title=document["title"],
                source_title=document["source_key"],
                document_id=document["document_id"],
                canonical_hash=document["canonical_hash"],
                license_status=str(
                    document.get("metadata", {}).get(
                        "license_status",
                        "private_research_only",
                    )
                ),
                concepts=[concept.canonical_name for concept in extraction.concepts],
                summary=summary,
                claims=claims,
            )
            path = exporter.export_insight(insight, changed_only=changed_only)
            if path is not None:
                paths.append(path)
        for concept in concepts:
            path = exporter.export_concept(
                ObsidianConcept(
                    canonical_name=concept.canonical_name,
                    concept_id=concept.concept_id,
                    concept_type=concept.concept_type,
                    aliases=concept.aliases,
                    confidence=concept.confidence,
                    document_ids=concept.document_ids,
                    evidence_child_chunk_ids=concept.evidence_child_chunk_ids,
                ),
                changed_only=changed_only,
            )
            if path is not None:
                paths.append(path)
        return paths

    def _record(self, document: FixtureDocument) -> FixtureDocument:
        manifest = self._load()
        incoming = _jsonable(asdict(document))
        existing = manifest["documents"].get(document.document_id)
        if existing is not None and _is_academic_metadata_document(existing, incoming):
            incoming = _merge_document(existing, incoming)
        manifest["documents"][document.document_id] = incoming
        self._write_manifest(manifest)
        return document

    def _load(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"version": 1, "documents": {}, "embeddings": {}}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _search_index(self) -> HybridSearch:
        return HybridSearch(self._all_results())

    def _ontology_store(self) -> OntologyStore:
        return OntologyStore.from_manifest(self._load())

    def _all_results(self) -> list[SearchResult]:
        results: list[SearchResult] = []
        for document in self._load()["documents"].values():
            parent_text_by_id = {
                parent["id"]: parent["text"] for parent in document.get("parent_chunks", [])
            }
            for chunk in document.get("child_chunks", []):
                results.append(
                    SearchResult(
                        child_chunk_id=chunk["id"],
                        parent_chunk_id=chunk["parent_chunk_id"],
                        document_id=chunk["document_id"],
                        source_title=document["title"],
                        source_url=document["source_url"],
                        text=chunk["text"],
                        parent_text=parent_text_by_id.get(chunk["parent_chunk_id"]),
                        chunk_hash=chunk["chunk_hash"],
                        score=0.0,
                    )
                )
        return results

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, indent=2),
            encoding="utf-8",
        )


def _child_chunk_from_json(chunk: dict[str, Any]) -> ChildChunk:
    return ChildChunk(
        id=chunk["id"],
        parent_chunk_id=chunk["parent_chunk_id"],
        document_id=chunk["document_id"],
        child_index=chunk["child_index"],
        text=chunk["text"],
        token_count=chunk["token_count"],
        chunk_hash=chunk["chunk_hash"],
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _merge_document(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged["metadata"] = _merge_metadata(
        existing.get("metadata", {}),
        incoming.get("metadata", {}),
    )
    return merged


def _is_academic_metadata_document(
    existing: dict[str, Any],
    incoming: dict[str, Any],
) -> bool:
    if incoming.get("document_type") != "paper":
        return False
    metadata_keys = {*existing.get("metadata", {}), *incoming.get("metadata", {})}
    return bool({"dedupe_key", "provider_sources"} & metadata_keys)


def _merge_metadata(
    existing: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value

    merged["providers"] = _unique_sorted(
        [*list(existing.get("providers", [])), *list(incoming.get("providers", []))]
    )
    merged["source_urls"] = _unique_sorted(
        [*list(existing.get("source_urls", [])), *list(incoming.get("source_urls", []))]
    )
    merged["pdf_urls"] = _unique_sorted(
        [*list(existing.get("pdf_urls", [])), *list(incoming.get("pdf_urls", []))]
    )
    merged["provider_sources"] = _unique_provider_sources(
        [
            *list(existing.get("provider_sources", [])),
            *list(incoming.get("provider_sources", [])),
        ]
    )
    return merged


def _unique_sorted(values: list[Any]) -> list[Any]:
    return sorted({value for value in values if value})


def _unique_provider_sources(values: list[Any]) -> list[dict[str, Any]]:
    keyed: dict[tuple[Any, Any], dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        key = (value.get("provider"), value.get("external_id"))
        keyed[key] = value
    return [keyed[key] for key in sorted(keyed)]


def _term_score(text: str, terms: list[str]) -> int:
    folded = text.casefold()
    return sum(1 for term in terms if term in folded)


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
