import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wzkf.storage.hashing import canonical_json_hash


@dataclass(frozen=True)
class OperationKey:
    value: str


class OperationCache:
    def __init__(self) -> None:
        self._succeeded: dict[str, str] = {}

    def key_for(
        self,
        operation_name: str,
        model_name: str,
        input_hash: str,
        prompt_hash: str,
        config_hash: str,
    ) -> OperationKey:
        return OperationKey(
            canonical_json_hash(
                {
                    "operation_name": operation_name,
                    "model_name": model_name,
                    "input_hash": input_hash,
                    "prompt_hash": prompt_hash,
                    "config_hash": config_hash,
                }
            )
        )

    def has_succeeded(self, key: OperationKey) -> bool:
        return key.value in self._succeeded

    def mark_succeeded(self, key: OperationKey, result_hash: str) -> None:
        self._succeeded[key.value] = result_hash

    def result_hash_for(self, key: OperationKey) -> str | None:
        return self._succeeded.get(key.value)


@dataclass(frozen=True)
class CostLedgerSummary:
    operations: int
    estimated_cost_usd: float


class FileCostLedger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def record_operation(
        self,
        operation_key: str,
        provider: str,
        model: str,
        unit_type: str,
        input_units: float,
        output_units: float,
        estimated_cost_usd: float,
    ) -> None:
        manifest = self._load()
        if operation_key not in manifest["operations"]:
            manifest["operations"][operation_key] = {
                "operation_key": operation_key,
                "provider": provider,
                "model": model,
                "unit_type": unit_type,
                "input_units": input_units,
                "output_units": output_units,
                "estimated_cost_usd": estimated_cost_usd,
                "created_at": datetime.now(UTC).isoformat(),
            }
            self._write(manifest)

    def summary(self) -> CostLedgerSummary:
        operations = self._load()["operations"]
        return CostLedgerSummary(
            operations=len(operations),
            estimated_cost_usd=sum(
                float(operation["estimated_cost_usd"]) for operation in operations.values()
            ),
        )

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "operations": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, manifest: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
