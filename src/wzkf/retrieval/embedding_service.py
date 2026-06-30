from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from wzkf.jobs.cost_ledger import FileCostLedger
from wzkf.storage.hashing import canonical_json_hash, sha256_text


class EmbeddingProvider(Protocol):
    model_name: str

    def embed(self, text: str) -> list[float]:
        pass


@dataclass(frozen=True)
class CachedEmbeddingResult:
    embedding: list[float]
    operation_key: str
    cache_hit: bool


class FileOperationCache:
    def __init__(self, path: Path):
        self.path = Path(path)

    def get(self, operation_key: str) -> list[float] | None:
        return self._load()["operations"].get(operation_key, {}).get("embedding")

    def put(self, operation_key: str, embedding: list[float]) -> None:
        manifest = self._load()
        manifest["operations"][operation_key] = {"embedding": embedding}
        self._write(manifest)

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"version": 1, "operations": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, manifest: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")


class CachedEmbeddingService:
    def __init__(
        self,
        provider: EmbeddingProvider,
        cache: FileOperationCache,
        config: dict[str, object],
        prompt_hash: str = sha256_text(""),
        cost_ledger: FileCostLedger | None = None,
        provider_name: str = "local",
    ):
        self.provider = provider
        self.cache = cache
        self.config = config
        self.prompt_hash = prompt_hash
        self.cost_ledger = cost_ledger
        self.provider_name = provider_name
        self.model_name = provider.model_name

    def embed_text(self, text: str) -> CachedEmbeddingResult:
        operation_key = canonical_json_hash(
            {
                "operation_name": "embed_text",
                "model_name": self.provider.model_name,
                "input_hash": sha256_text(text),
                "prompt_hash": self.prompt_hash,
                "config_hash": canonical_json_hash(self.config),
            }
        )
        cached = self.cache.get(operation_key)
        if cached is not None:
            return CachedEmbeddingResult(
                embedding=cached,
                operation_key=operation_key,
                cache_hit=True,
            )
        embedding = self.provider.embed(text)
        self.cache.put(operation_key, embedding)
        if self.cost_ledger is not None:
            self.cost_ledger.record_operation(
                operation_key=operation_key,
                provider=self.provider_name,
                model=self.provider.model_name,
                unit_type="embedding_input_chars",
                input_units=float(len(text)),
                output_units=float(len(embedding)),
                estimated_cost_usd=0.0,
            )
        return CachedEmbeddingResult(
            embedding=embedding,
            operation_key=operation_key,
            cache_hit=False,
        )
