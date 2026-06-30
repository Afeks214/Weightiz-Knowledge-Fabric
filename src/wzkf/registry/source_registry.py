from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from wzkf.rights.license_gate import RightsDecision, RightsGate, SourceRecord


class SourceRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class RegistrySource:
    source_key: str
    source_type: str
    title: str
    rights_policy: str
    homepage_url: str | None = None
    rss_url: str | None = None
    strategy: str | None = None


class SourceRegistry:
    def __init__(self, sources: dict[str, RegistrySource], policies: set[str]):
        self.sources = sources
        self.policies = policies

    @classmethod
    def from_files(cls, sources_path: Path, rights_policies_path: Path) -> "SourceRegistry":
        raw_sources = _load_yaml(sources_path)
        raw_policies = _load_yaml(rights_policies_path)
        policies = set((raw_policies.get("policies") or {}).keys())
        sources = _flatten_sources(raw_sources)
        _validate_sources(sources, policies)
        return cls({source.source_key: source for source in sources}, policies)

    def require_source(self, source_key: str) -> RegistrySource:
        try:
            return self.sources[source_key]
        except KeyError as exc:
            raise SourceRegistryError(f"unknown source: {source_key}") from exc

    def rights_decision_for(self, source_key: str) -> RightsDecision:
        source = self.require_source(source_key)
        return RightsGate().evaluate(
            SourceRecord(
                source_key=source.source_key,
                source_type=source.source_type,
                title=source.title,
                homepage_url=source.homepage_url,
                rights_policy=source.rights_policy,
                authorized_transcript=source.strategy == "official_transcript_first",
            )
        )


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _flatten_sources(raw: dict[str, Any]) -> list[RegistrySource]:
    flattened: list[RegistrySource] = []
    for section, source_type in [
        ("podcasts", "podcast"),
        ("academic_apis", "academic_api"),
        ("repos", "repo"),
        ("news_datasets", "news_dataset"),
    ]:
        for item in raw.get(section, []) or []:
            source_key = item["id"]
            flattened.append(
                RegistrySource(
                    source_key=source_key,
                    source_type=source_type,
                    title=item.get("title") or _title_from_key(source_key),
                    rights_policy=item.get("rights_policy") or "private_research_only",
                    homepage_url=item.get("homepage_url"),
                    rss_url=item.get("rss_url"),
                    strategy=item.get("strategy"),
                )
            )
    return flattened


def _validate_sources(sources: list[RegistrySource], policies: set[str]) -> None:
    seen: set[str] = set()
    for source in sources:
        if source.source_key in seen:
            raise SourceRegistryError(f"duplicate source id: {source.source_key}")
        seen.add(source.source_key)
        if source.rights_policy not in policies:
            raise SourceRegistryError(
                f"source {source.source_key} references unknown rights policy "
                f"{source.rights_policy}"
            )


def _title_from_key(source_key: str) -> str:
    return source_key.replace("_", " ")
