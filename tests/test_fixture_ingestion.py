from pathlib import Path

from wzkf.ingest.fixture_ingestor import FixtureIngestor


def test_signals_threads_fixture_prefers_official_transcript(tmp_path: Path):
    fixture = Path("tests/fixtures/signals_threads/episode.html")
    ingestor = FixtureIngestor(storage_root=tmp_path)

    document = ingestor.ingest_signals_threads_fixture(fixture)

    assert document.source_key == "signals_threads"
    assert document.title == "Expect Tests for Trading Infrastructure"
    assert document.used_transcription is False
    assert document.raw_artifact.sha256
    assert document.canonical_hash
    assert document.canonical_text_path.exists()
    assert document.canonical_text_path.read_text(encoding="utf-8").startswith("Host [0]:")
    assert document.parent_chunks
    assert document.child_chunks
