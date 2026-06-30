from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


FULL_TEXT_FIELDS = {"article_text", "body", "content", "full_text", "text"}


class ReutersDatasetPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class HarvestedReutersMetadataRecord:
    source_key: str
    dataset_id: str
    dataset_title: str
    record_id: str
    title: str
    source_url: str
    published_at: str | None
    topics: list[str]
    places: list[str]
    split: str | None
    license_status: str
    metadata_only: bool = True


class ReutersMetadataHarvester:
    def parse(self, metadata_json: str) -> list[HarvestedReutersMetadataRecord]:
        payload = json.loads(metadata_json)
        dataset_id = _required_text(payload, "dataset_id")
        dataset_title = _required_text(payload, "dataset_title")
        source_url = _required_text(payload, "source_url")
        license_status = _required_text(payload, "license_status")
        records = payload.get("records", [])
        if not isinstance(records, list):
            raise ReutersDatasetPolicyError("Reuters metadata fixture records must be a list")

        harvested: list[HarvestedReutersMetadataRecord] = []
        for record in records:
            if not isinstance(record, dict):
                raise ReutersDatasetPolicyError("Reuters metadata record must be an object")
            forbidden = FULL_TEXT_FIELDS.intersection(record)
            if forbidden:
                names = ", ".join(sorted(forbidden))
                raise ReutersDatasetPolicyError(
                    f"metadata-only Reuters record includes full-text field(s): {names}"
                )
            record_id = _required_text(record, "record_id")
            harvested.append(
                HarvestedReutersMetadataRecord(
                    source_key=dataset_id,
                    dataset_id=dataset_id,
                    dataset_title=dataset_title,
                    record_id=record_id,
                    title=_required_text(record, "title"),
                    source_url=str(record.get("source_url") or f"{source_url}#{record_id}"),
                    published_at=_optional_text(record.get("published_at")),
                    topics=_string_list(record.get("topics", [])),
                    places=_string_list(record.get("places", [])),
                    split=_optional_text(record.get("split")),
                    license_status=license_status,
                )
            )
        return harvested


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReutersDatasetPolicyError(f"Reuters metadata fixture missing {key}")
    return " ".join(value.split())


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReutersDatasetPolicyError("Reuters optional metadata fields must be strings")
    return " ".join(value.split())


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ReutersDatasetPolicyError("Reuters metadata list field must be a list")
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ReutersDatasetPolicyError("Reuters metadata list values must be strings")
        strings.append(" ".join(item.split()))
    return strings
