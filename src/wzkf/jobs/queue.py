from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from wzkf.storage.hashing import canonical_json_hash


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ABSTAINED = "ABSTAINED"


@dataclass(frozen=True)
class JobRecord:
    id: str
    job_type: str
    document_id: str
    input_hash: str
    payload: dict[str, Any]
    status: JobStatus
    created_at: str
    updated_at: str
    error_message: str | None = None


class LocalJobQueue:
    def __init__(self, path: Path):
        self.path = Path(path)

    def enqueue(
        self,
        job_type: str,
        document_id: str,
        input_hash: str,
        payload: dict[str, Any],
    ) -> JobRecord:
        manifest = self._load()
        job_id = canonical_json_hash(
            {
                "job_type": job_type,
                "document_id": document_id,
                "input_hash": input_hash,
                "payload": payload,
            }
        )[:32]
        if job_id not in manifest["jobs"]:
            now = _now()
            manifest["jobs"][job_id] = {
                "id": job_id,
                "job_type": job_type,
                "document_id": document_id,
                "input_hash": input_hash,
                "payload": payload,
                "status": JobStatus.PENDING.value,
                "created_at": now,
                "updated_at": now,
                "error_message": None,
            }
            self._write(manifest)
        return _record(manifest["jobs"][job_id])

    def pending(self) -> list[JobRecord]:
        return [
            _record(raw)
            for raw in self._load()["jobs"].values()
            if raw["status"] == JobStatus.PENDING.value
        ]

    def get(self, job_id: str) -> JobRecord | None:
        raw = self._load()["jobs"].get(job_id)
        if raw is None:
            return None
        return _record(raw)

    def count(self, status: JobStatus | None = None) -> int:
        jobs = self._load()["jobs"].values()
        if status is None:
            return len(list(jobs))
        return sum(1 for job in jobs if job["status"] == status.value)

    def mark(self, job_id: str, status: JobStatus, error_message: str | None = None) -> JobRecord:
        manifest = self._load()
        if job_id not in manifest["jobs"]:
            raise KeyError(f"unknown job: {job_id}")
        manifest["jobs"][job_id]["status"] = status.value
        manifest["jobs"][job_id]["updated_at"] = _now()
        manifest["jobs"][job_id]["error_message"] = error_message
        self._write(manifest)
        return _record(manifest["jobs"][job_id])

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "jobs": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, manifest: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")


def _record(raw: dict[str, Any]) -> JobRecord:
    return JobRecord(
        id=raw["id"],
        job_type=raw["job_type"],
        document_id=raw["document_id"],
        input_hash=raw["input_hash"],
        payload=raw["payload"],
        status=JobStatus(raw["status"]),
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        error_message=raw.get("error_message"),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
