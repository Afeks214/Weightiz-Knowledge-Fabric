from pathlib import Path

from typer.testing import CliRunner

from wzkf.cli import app
from wzkf.harvesters.academic_metadata import AcademicMetadataHarvester
from wzkf.ingest.fixture_ingestor import FixtureIngestor


def test_academic_metadata_harvesters_normalize_provider_records():
    fixtures = {
        "openalex": "tests/fixtures/academic_metadata/openalex_work.json",
        "crossref": "tests/fixtures/academic_metadata/crossref_work.json",
        "unpaywall": "tests/fixtures/academic_metadata/unpaywall_work.json",
        "core": "tests/fixtures/academic_metadata/core_work.json",
    }

    records = {
        provider: AcademicMetadataHarvester(
            provider=provider,
            query_id="qfin_market_microstructure",
        ).parse(Path(path).read_text(encoding="utf-8"))[0]
        for provider, path in fixtures.items()
    }

    assert records["openalex"].title == "OpenAlex Limit Order Book Paper"
    assert records["openalex"].abstract == "Limit order book evidence requires citations."
    assert records["openalex"].pdf_url == "https://example.org/openalex-lob.pdf"
    assert records["openalex"].license_status == "open_access_pdf_allowed"

    assert records["crossref"].title == "Crossref Metadata Only Paper"
    assert records["crossref"].pdf_url is None
    assert records["crossref"].license_status == "metadata_only"

    assert records["unpaywall"].pdf_url == "https://example.org/unpaywall-open.pdf"
    assert records["unpaywall"].is_open_access is True

    assert records["core"].pdf_url == "https://core.ac.uk/download/pdf/123.pdf"
    assert "THIS FULL TEXT" not in records["core"].abstract


def test_fixture_ingestor_ingests_academic_metadata_without_core_full_text(tmp_path: Path):
    fixture = Path("tests/fixtures/academic_metadata/core_work.json").read_text(encoding="utf-8")
    harvested = AcademicMetadataHarvester(
        provider="core",
        query_id="qfin_market_microstructure",
    ).parse(fixture)[0]

    document = FixtureIngestor(tmp_path).ingest_academic_metadata_record(harvested)

    assert document.source_key == "core:qfin_market_microstructure"
    assert document.document_type == "paper"
    assert document.metadata["provider"] == "core"
    assert document.metadata["pdf_url"] == "https://core.ac.uk/download/pdf/123.pdf"
    assert document.raw_artifact.sha256
    assert document.canonical_hash
    assert document.child_chunks
    canonical_text = document.canonical_text_path.read_text(encoding="utf-8")
    assert "CORE Open Metadata Paper" in canonical_text
    assert "THIS FULL TEXT MUST NOT BE STORED" not in canonical_text


def test_cli_ingest_academic_metadata_fixture(tmp_path: Path):
    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "academic",
            "--provider",
            "openalex",
            "--query",
            "qfin_market_microstructure",
            "--fixture",
            "tests/fixtures/academic_metadata/openalex_work.json",
            "--storage-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "harvested academic:openalex:qfin_market_microstructure: 1 records" in result.output
    assert (tmp_path / "manifests" / "corpus.json").exists()
