from pathlib import Path

from wzkf.storage.hashing import sha256_text


class CanonicalStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def put_text(self, document_id: str, text: str) -> tuple[Path, str]:
        digest = sha256_text(text)
        path = self.root / "canonical" / document_id / f"{digest}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(text, encoding="utf-8")
        return path, digest
