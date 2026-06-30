from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from wzkf.storage.hashing import sha256_text


class ObsidianInsight(BaseModel):
    note_type: str
    title: str
    source_title: str
    document_id: str
    canonical_hash: str
    license_status: str
    concepts: list[str] = Field(default_factory=list)
    summary: str
    claims: list[tuple[str, list[str]]] = Field(default_factory=list)
    raw_transcript: str | None = None


class ObsidianConcept(BaseModel):
    canonical_name: str
    concept_id: str
    concept_type: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float
    document_ids: list[str] = Field(default_factory=list)
    evidence_child_chunk_ids: list[str] = Field(default_factory=list)


class ObsidianExporter:
    def __init__(self, export_root: Path):
        self.export_root = Path(export_root)
        self.ledger_path = self.export_root / ".export-ledger.json"

    def export_insight(self, insight: ObsidianInsight, changed_only: bool = False) -> Path | None:
        path = self.export_root / f"{_safe_filename(insight.title)}.md"
        return self._export_note(path, _render(insight), changed_only=changed_only)

    def export_concept(self, concept: ObsidianConcept, changed_only: bool = False) -> Path | None:
        path = self.export_root / f"Concept - {_safe_filename(concept.canonical_name)}.md"
        return self._export_note(path, _render_concept(concept), changed_only=changed_only)

    def _export_note(self, path: Path, body: str, changed_only: bool) -> Path | None:
        self.export_root.mkdir(parents=True, exist_ok=True)
        digest = sha256_text(body)
        ledger = self._load_ledger()
        key = path.name
        if changed_only and path.exists() and ledger["notes"].get(key) == digest:
            return None
        path.write_text(body, encoding="utf-8")
        ledger["notes"][key] = digest
        self._write_ledger(ledger)
        return path

    def _load_ledger(self) -> dict[str, object]:
        if not self.ledger_path.exists():
            return {"version": 1, "notes": {}}
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))

    def _write_ledger(self, ledger: dict[str, object]) -> None:
        self.ledger_path.write_text(
            json.dumps(ledger, sort_keys=True, indent=2),
            encoding="utf-8",
        )


def _render(insight: ObsidianInsight) -> str:
    concepts = "\n".join(f'  - "[[{concept}]]"' for concept in insight.concepts)
    claims = "\n".join(
        f"| {claim} | {', '.join(evidence_ids)} |" for claim, evidence_ids in insight.claims
    )
    if not claims:
        claims = "| ABSTAIN | No evidence_child_chunk_ids supplied |"
    return (
        "---\n"
        f"type: {insight.note_type}\n"
        f"source_title: {insight.source_title}\n"
        f"document_id: {insight.document_id}\n"
        f"canonical_hash: {insight.canonical_hash}\n"
        f"license_status: {insight.license_status}\n"
        "raw_transcript_exported: false\n"
        "concepts:\n"
        f"{concepts}\n"
        "---\n\n"
        f"# {insight.title}\n\n"
        "## Executive Summary\n"
        f"{insight.summary}\n\n"
        "## Claims With Evidence\n"
        "| Claim | Evidence |\n"
        "|---|---|\n"
        f"{claims}\n\n"
        "## Deep Links\n"
        f"- Document API: /documents/{insight.document_id}\n"
    )


def _render_concept(concept: ObsidianConcept) -> str:
    aliases = "\n".join(f"  - {alias}" for alias in concept.aliases)
    document_ids = "\n".join(f"  - {document_id}" for document_id in concept.document_ids)
    evidence = "\n".join(
        f"  - {chunk_id}" for chunk_id in concept.evidence_child_chunk_ids
    )
    return (
        "---\n"
        "type: concept\n"
        f"canonical_name: {concept.canonical_name}\n"
        f"concept_id: {concept.concept_id}\n"
        f"concept_type: {concept.concept_type}\n"
        f"confidence: {concept.confidence:.2f}\n"
        "raw_transcript_exported: false\n"
        "aliases:\n"
        f"{aliases}\n"
        "---\n\n"
        f"# {concept.canonical_name}\n\n"
        "## Aliases\n"
        f"{aliases}\n\n"
        "## Evidence Map\n"
        "Documents:\n"
        f"{document_ids}\n\n"
        "Evidence child chunks:\n"
        f"{evidence}\n"
    )


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r"[^\w .-]+", "", title).strip()
    return cleaned or "untitled"
