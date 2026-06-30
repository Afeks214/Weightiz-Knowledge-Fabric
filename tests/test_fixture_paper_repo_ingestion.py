from pathlib import Path

from wzkf.harvesters.arxiv_api import ArxivAtomHarvester
from wzkf.harvesters.github_repo import GitHubRepoHarvester
from wzkf.harvesters.reuters_dataset import ReutersDatasetPolicyError, ReutersMetadataHarvester
from wzkf.ingest.fixture_ingestor import FixtureIngestor


def test_arxiv_qfin_fixture_ingests_metadata_and_chunks(tmp_path: Path):
    ingestor = FixtureIngestor(storage_root=tmp_path)

    document = ingestor.ingest_arxiv_fixture(Path("tests/fixtures/papers/arxiv_qfin.xml"))

    assert document.source_key == "arxiv:qfin_market_microstructure"
    assert document.document_type == "paper"
    assert document.title == "A Limit Order Book Fixture for Market Microstructure"
    assert document.metadata["arxiv_id"] == "2606.30001"
    assert document.raw_artifact.sha256
    assert document.canonical_hash
    assert document.canonical_text_path.exists()
    assert document.canonical_text_path.read_text(encoding="utf-8").startswith(
        "# A Limit Order Book"
    )
    assert document.parent_chunks
    assert document.child_chunks


def test_github_repo_fixture_ingests_docs_license_tests_and_source(tmp_path: Path):
    ingestor = FixtureIngestor(storage_root=tmp_path)

    document = ingestor.ingest_github_repo_fixture(
        repo_root=Path("tests/fixtures/repos/janestreet_ppx_expect"),
        source_key="janestreet_ppx_expect",
        commit_hash="fixture-commit",
    )

    assert document.source_key == "janestreet_ppx_expect"
    assert document.document_type == "github_repo"
    assert document.metadata["commit_hash"] == "fixture-commit"
    assert document.canonical_text_path.exists()
    assert "README.md" in document.metadata["paths"]
    assert "LICENSE" in document.metadata["paths"]
    assert "tests/test_expect.ml" in document.metadata["paths"]
    assert "src/expect_runner.ml" in document.metadata["paths"]
    assert document.child_chunks


def test_fixture_ingestor_can_ingest_harvested_arxiv_record(tmp_path: Path):
    atom = Path("tests/fixtures/papers/arxiv_qfin.xml").read_text(encoding="utf-8")
    harvested = ArxivAtomHarvester(query_id="qfin_market_microstructure").parse(atom)[0]

    document = FixtureIngestor(tmp_path).ingest_harvested_arxiv_paper(harvested)

    assert document.source_key == harvested.source_key
    assert document.source_url == harvested.source_url
    assert document.title == harvested.title
    assert document.metadata["pdf_url"] == harvested.pdf_url
    assert document.raw_artifact.retrieval_method == "arxiv_atom"
    assert document.child_chunks


def test_fixture_ingestor_can_ingest_harvested_repo_record(tmp_path: Path):
    harvested = GitHubRepoHarvester().harvest_local_repo(
        Path("tests/fixtures/repos/janestreet_ppx_expect"),
        source_key="janestreet_ppx_expect",
        commit_hash="fixture-commit",
    )

    document = FixtureIngestor(tmp_path).ingest_harvested_repo(
        harvested,
        Path("tests/fixtures/repos/janestreet_ppx_expect"),
    )

    assert document.source_key == harvested.source_key
    assert document.source_url == harvested.source_url
    assert document.metadata["paths"] == harvested.paths
    assert document.raw_artifact.retrieval_method == "github_clone"
    assert document.child_chunks


def test_github_repo_harvester_selects_common_readme_and_license_variants(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "README.mdx").write_text("# Project\n", encoding="utf-8")
    (repo / "LICENSE.md").write_text("MIT\n", encoding="utf-8")
    (repo / "src" / "main.ml").write_text("let x = 1\n", encoding="utf-8")
    (repo / "tests" / "test_main.ml").write_text("let%expect_test _ = ()\n", encoding="utf-8")
    (repo / "secret-notes.md").write_text("do not ingest\n", encoding="utf-8")

    harvested = GitHubRepoHarvester().harvest_local_repo(
        repo,
        source_key="example_repo",
        commit_hash="abc123",
    )
    document = FixtureIngestor(tmp_path / "storage").ingest_harvested_repo(harvested, repo)

    assert harvested.paths == [
        "LICENSE.md",
        "README.mdx",
        "src/main.ml",
        "tests/test_main.ml",
    ]
    assert document.metadata["paths"] == harvested.paths
    assert "secret-notes.md" not in document.canonical_text_path.read_text(encoding="utf-8")


def test_reuters_metadata_fixture_ingests_without_full_text(tmp_path: Path):
    fixture = Path("tests/fixtures/reuters/reuters_21578_metadata.json").read_text(
        encoding="utf-8"
    )
    harvested = ReutersMetadataHarvester().parse(fixture)[0]

    document = FixtureIngestor(tmp_path).ingest_reuters_metadata_record(harvested)

    assert document.source_key == "reuters_21578"
    assert document.document_type == "news_dataset_record"
    assert document.metadata["metadata_only"] is True
    assert document.metadata["record_id"] == "reut2-000001"
    assert document.child_chunks
    canonical_text = document.canonical_text_path.read_text(encoding="utf-8")
    assert "Fixture record for commodity market categories" in canonical_text
    assert "full wire story" not in canonical_text.casefold()


def test_reuters_metadata_harvester_rejects_full_text_records():
    payload = """
{
  "dataset_id": "reuters_21578",
  "dataset_title": "Reuters-21578",
  "source_url": "fixture://reuters",
  "license_status": "historical_research_dataset_metadata_only",
  "records": [
    {
      "record_id": "reut2-unsafe",
      "title": "Unsafe fixture",
      "body": "This is the full wire story and must not enter metadata-only mode."
    }
  ]
}
"""

    try:
        ReutersMetadataHarvester().parse(payload)
    except ReutersDatasetPolicyError as exc:
        assert "full-text field" in str(exc)
    else:
        raise AssertionError("metadata-only harvester accepted a full-text record")
