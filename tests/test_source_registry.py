from pathlib import Path

import pytest

from wzkf.registry.source_registry import SourceRegistry, SourceRegistryError
from wzkf.rights.license_gate import SourceStatus


def test_source_registry_loads_unique_sources_and_evaluates_rights():
    registry = SourceRegistry.from_files(
        sources_path=Path("config/sources.yaml"),
        rights_policies_path=Path("config/rights_policies.yaml"),
    )

    signals = registry.require_source("signals_threads")
    openalex = registry.require_source("openalex")
    lseg = registry.require_source("lseg_current_news")

    assert signals.title == "Signals and Threads"
    assert openalex.source_type == "academic_api"
    assert registry.rights_decision_for("openalex").status == SourceStatus.METADATA_ONLY
    assert registry.rights_decision_for("signals_threads").status == SourceStatus.ALLOWED
    assert registry.rights_decision_for("lseg_current_news").status == SourceStatus.METADATA_ONLY
    assert lseg.rights_policy == "metadata_only_unless_licensed"


def test_source_registry_rejects_unknown_rights_policy(tmp_path: Path):
    sources = tmp_path / "sources.yaml"
    policies = tmp_path / "rights.yaml"
    sources.write_text(
        """
podcasts:
  - id: bad_source
    title: Bad Source
    strategy: official_transcript_first
    rights_policy: missing_policy
""",
        encoding="utf-8",
    )
    policies.write_text("policies: {}\n", encoding="utf-8")

    with pytest.raises(SourceRegistryError, match="missing_policy"):
        SourceRegistry.from_files(sources, policies)
