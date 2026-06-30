from pathlib import Path

import pytest

from wzkf.harvesters.arxiv_api import ArxivAtomHarvester
from wzkf.harvesters.github_repo import GitHubRepoHarvester
from wzkf.harvesters.podcast_rss import PodcastRssHarvester, PodcastRssPolicyError


def test_podcast_rss_prefers_transcript_tag_over_audio_enclosure():
    rss = Path("tests/fixtures/podcast_rss/signals_threads_feed.xml").read_text(encoding="utf-8")

    episode = PodcastRssHarvester().harvest_first_episode(rss, source_key="signals_threads")

    assert episode.source_key == "signals_threads"
    assert episode.title == "Expect Tests for Trading Infrastructure"
    assert episode.transcript_url == "https://signalsandthreads.com/example-expect-tests/transcript.txt"
    assert episode.audio_url == "https://cdn.example.invalid/episode.mp3"
    assert episode.selected_artifact_url == episode.transcript_url
    assert episode.selected_artifact_type == "transcript"
    assert episode.used_transcription is False


def test_podcast_rss_abstains_on_youtube_only_without_authorized_transcript():
    rss = Path("tests/fixtures/podcast_rss/youtube_only_feed.xml").read_text(encoding="utf-8")

    with pytest.raises(PodcastRssPolicyError, match="YouTube"):
        PodcastRssHarvester().harvest_first_episode(rss, source_key="youtube_only")


def test_arxiv_atom_harvester_maps_entries_to_open_paper_records():
    atom = Path("tests/fixtures/papers/arxiv_qfin.xml").read_text(encoding="utf-8")

    papers = ArxivAtomHarvester(query_id="qfin_market_microstructure").parse(atom)

    assert len(papers) == 1
    assert papers[0].source_key == "arxiv:qfin_market_microstructure"
    assert papers[0].arxiv_id == "2606.30001"
    assert papers[0].pdf_url == "https://arxiv.org/pdf/2606.30001"
    assert papers[0].license_status == "open_metadata_pdf_allowed"


def test_github_repo_harvester_selects_docs_license_tests_and_source_without_secrets():
    harvested = GitHubRepoHarvester().harvest_local_repo(
        Path("tests/fixtures/repos/janestreet_ppx_expect"),
        source_key="janestreet_ppx_expect",
        commit_hash="fixture-commit",
    )

    assert harvested.source_key == "janestreet_ppx_expect"
    assert harvested.commit_hash == "fixture-commit"
    assert harvested.source_url == "https://github.com/janestreet/ppx_expect"
    assert harvested.paths == [
        "LICENSE",
        "README.md",
        "src/expect_runner.ml",
        "tests/test_expect.ml",
    ]
    assert all("secret" not in path.casefold() for path in harvested.paths)
