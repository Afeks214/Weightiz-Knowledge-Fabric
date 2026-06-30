from pathlib import Path

from wzkf.export.obsidian import ObsidianExporter, ObsidianInsight
from wzkf.pipeline.local import LocalKnowledgeFabric


def test_obsidian_episode_note_excludes_raw_transcript(tmp_path: Path):
    insight = ObsidianInsight(
        note_type="podcast_episode_insight",
        title="Expect Tests in Practice",
        source_title="Signals and Threads",
        document_id="doc-1",
        canonical_hash="sha256:canonical",
        license_status="official_public_research_private",
        concepts=["Expect Tests", "Market Data Infrastructure"],
        summary="The episode discusses reviewable engineering artifacts.",
        claims=[("Expect tests make output changes reviewable.", ["child-1"])],
        raw_transcript="THIS RAW TRANSCRIPT MUST NOT BE EXPORTED",
    )

    path = ObsidianExporter(tmp_path).export_insight(insight)
    body = path.read_text()

    assert path.name == "Expect Tests in Practice.md"
    assert "raw_transcript_exported: false" in body
    assert "child-1" in body
    assert "THIS RAW TRANSCRIPT MUST NOT BE EXPORTED" not in body


def test_local_obsidian_export_changed_only_uses_content_ledger(tmp_path: Path):
    fabric = LocalKnowledgeFabric(tmp_path)
    fabric.ingest_signals_threads_fixture(Path("tests/fixtures/signals_threads/episode.html"))

    first = fabric.export_obsidian(changed_only=True)
    second = fabric.export_obsidian(changed_only=True)
    forced = fabric.export_obsidian(changed_only=False)

    assert first
    assert second == []
    assert forced
    assert (tmp_path / "obsidian_export" / ".export-ledger.json").exists()
