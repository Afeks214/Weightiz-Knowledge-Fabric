from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wzkf.storage.hashing import sha256_bytes


@dataclass(frozen=True)
class RawArtifactRef:
    document_id: str
    artifact_type: str
    storage_path: str
    sha256: str
    byte_count: int
    retrieval_method: str = "fixture"


class RawStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def put(
        self,
        document_id: str,
        artifact_type: str,
        data: bytes,
        retrieval_method: str = "fixture",
    ) -> RawArtifactRef:
        digest = sha256_bytes(data)
        suffix = _suffix_for(artifact_type)
        path = self.root / "raw" / document_id / artifact_type / f"{digest}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return RawArtifactRef(
            document_id=document_id,
            artifact_type=artifact_type,
            storage_path=str(path),
            sha256=digest,
            byte_count=len(data),
            retrieval_method=retrieval_method,
        )


def _suffix_for(artifact_type: str) -> str:
    return {
        "html": ".html",
        "json": ".json",
        "markdown": ".md",
        "pdf": ".pdf",
        "rss": ".xml",
        "xml": ".xml",
        "text": ".txt",
    }.get(artifact_type, ".bin")
