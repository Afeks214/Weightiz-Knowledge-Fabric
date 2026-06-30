from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from wzkf.chunking.parent_child import ChildChunk, ParentChildChunker, ParentChunk
from wzkf.harvesters.academic_metadata import HarvestedAcademicRecord
from wzkf.harvesters.arxiv_api import HarvestedPaper
from wzkf.harvesters.github_repo import HarvestedRepo
from wzkf.harvesters.podcast_rss import HarvestedPodcastEpisode
from wzkf.harvesters.reuters_dataset import HarvestedReutersMetadataRecord
from wzkf.storage.canonical_store import CanonicalStore
from wzkf.storage.hashing import canonical_json_hash, sha256_text
from wzkf.storage.raw_store import RawArtifactRef, RawStore


@dataclass(frozen=True)
class FixtureDocument:
    source_key: str
    document_id: str
    document_type: str
    title: str
    source_url: str
    used_transcription: bool
    raw_artifact: RawArtifactRef
    canonical_hash: str
    canonical_text_path: Path
    parent_chunks: list[ParentChunk]
    child_chunks: list[ChildChunk]
    metadata: dict[str, object]


class FixtureIngestor:
    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        self.raw_store = RawStore(self.storage_root)
        self.canonical_store = CanonicalStore(self.storage_root)

    def ingest_signals_threads_fixture(self, fixture_path: Path) -> FixtureDocument:
        html = Path(fixture_path).read_bytes()
        parser = _SignalsThreadsParser()
        parser.feed(html.decode("utf-8"))
        title = parser.title or parser.h1 or "Untitled Signals and Threads Episode"
        source_url = parser.source_url or "fixture://signals_threads"
        document_id = sha256_text(f"signals_threads:{source_url}:{title}")[:24]
        raw = self.raw_store.put(document_id, "html", html)
        transcript_lines = [
            f"{speaker} [{start}]: {text}" for speaker, start, text in parser.transcript_rows
        ]
        canonical_text = "\n".join(transcript_lines).strip()
        chunks = ParentChildChunker(parent_token_target=240, child_token_target=40).chunk(
            document_id=document_id,
            text=canonical_text,
            section_title=title,
        )
        canonical_path, canonical_hash = self.canonical_store.put_text(document_id, canonical_text)
        return FixtureDocument(
            source_key="signals_threads",
            document_id=document_id,
            document_type="podcast_episode",
            title=title,
            source_url=source_url,
            used_transcription=False,
            raw_artifact=raw,
            canonical_hash=canonical_hash,
            canonical_text_path=canonical_path,
            parent_chunks=chunks.parent_chunks,
            child_chunks=chunks.child_chunks,
            metadata={"license_status": "official_public_research_private"},
        )

    def ingest_harvested_podcast_transcript(
        self,
        episode: HarvestedPodcastEpisode,
        transcript_text: str,
        retrieved_at: str,
    ) -> FixtureDocument:
        normalized = transcript_text.strip()
        document_id = sha256_text(
            f"{episode.source_key}:{episode.source_url}:{episode.selected_artifact_url}:{episode.title}"
        )[:24]
        raw = self.raw_store.put(
            document_id,
            "text",
            normalized.encode("utf-8"),
            retrieval_method="podcast_rss_transcript",
        )
        canonical_text = f"# {episode.title}\n\n{normalized}"
        chunks = ParentChildChunker(parent_token_target=480, child_token_target=80).chunk(
            document_id=document_id,
            text=canonical_text,
            section_title=episode.title,
        )
        canonical_path, canonical_hash = self.canonical_store.put_text(document_id, canonical_text)
        return FixtureDocument(
            source_key=episode.source_key,
            document_id=document_id,
            document_type="podcast_episode",
            title=episode.title,
            source_url=episode.source_url,
            used_transcription=episode.used_transcription,
            raw_artifact=raw,
            canonical_hash=canonical_hash,
            canonical_text_path=canonical_path,
            parent_chunks=chunks.parent_chunks,
            child_chunks=chunks.child_chunks,
            metadata={
                "audio_url": episode.audio_url,
                "license_status": "official_public_research_private",
                "retrieved_at": retrieved_at,
                "selected_artifact_type": episode.selected_artifact_type,
                "selected_artifact_url": episode.selected_artifact_url,
                "transcript_url": episode.transcript_url,
            },
        )

    def ingest_arxiv_fixture(self, fixture_path: Path) -> FixtureDocument:
        xml_bytes = Path(fixture_path).read_bytes()
        root = ElementTree.fromstring(xml_bytes)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)
        if entry is None:
            raise ValueError("arXiv fixture has no Atom entry")

        title = _text(entry.find("atom:title", ns))
        summary = _text(entry.find("atom:summary", ns))
        source_url = _text(entry.find("atom:id", ns))
        arxiv_id = _arxiv_id_from_url(source_url)
        authors = [
            _text(author.find("atom:name", ns))
            for author in entry.findall("atom:author", ns)
        ]
        categories = [
            category.attrib.get("term", "") for category in entry.findall("atom:category", ns)
        ]
        document_id = sha256_text(f"arxiv:{arxiv_id}:{title}")[:24]
        raw = self.raw_store.put(document_id, "xml", xml_bytes)
        canonical_text = (
            f"# {title}\n\n"
            f"arXiv ID: {arxiv_id}\n"
            f"Authors: {', '.join(authors)}\n"
            f"Categories: {', '.join(categories)}\n\n"
            f"## Abstract\n{summary}"
        )
        chunks = ParentChildChunker(parent_token_target=240, child_token_target=40).chunk(
            document_id=document_id,
            text=canonical_text,
            section_title="Abstract",
        )
        canonical_path, canonical_hash = self.canonical_store.put_text(document_id, canonical_text)
        return FixtureDocument(
            source_key="arxiv:qfin_market_microstructure",
            document_id=document_id,
            document_type="paper",
            title=title,
            source_url=source_url,
            used_transcription=False,
            raw_artifact=raw,
            canonical_hash=canonical_hash,
            canonical_text_path=canonical_path,
            parent_chunks=chunks.parent_chunks,
            child_chunks=chunks.child_chunks,
            metadata={"arxiv_id": arxiv_id, "authors": authors, "categories": categories},
        )

    def ingest_harvested_arxiv_paper(self, harvested: HarvestedPaper) -> FixtureDocument:
        document_id = sha256_text(
            f"{harvested.source_key}:{harvested.arxiv_id}:{harvested.title}"
        )[:24]
        raw_payload = json.dumps(
            {
                "arxiv_id": harvested.arxiv_id,
                "title": harvested.title,
                "abstract": harvested.abstract,
                "authors": harvested.authors,
                "categories": harvested.categories,
                "source_url": harvested.source_url,
                "pdf_url": harvested.pdf_url,
                "license_status": harvested.license_status,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        raw = self.raw_store.put(
            document_id,
            "json",
            raw_payload,
            retrieval_method="arxiv_atom",
        )
        canonical_text = (
            f"# {harvested.title}\n\n"
            f"arXiv ID: {harvested.arxiv_id}\n"
            f"Authors: {', '.join(harvested.authors)}\n"
            f"Categories: {', '.join(harvested.categories)}\n"
            f"PDF: {harvested.pdf_url}\n\n"
            f"## Abstract\n{harvested.abstract}"
        )
        chunks = ParentChildChunker(parent_token_target=240, child_token_target=40).chunk(
            document_id=document_id,
            text=canonical_text,
            section_title="Abstract",
        )
        canonical_path, canonical_hash = self.canonical_store.put_text(document_id, canonical_text)
        return FixtureDocument(
            source_key=harvested.source_key,
            document_id=document_id,
            document_type="paper",
            title=harvested.title,
            source_url=harvested.source_url,
            used_transcription=False,
            raw_artifact=raw,
            canonical_hash=canonical_hash,
            canonical_text_path=canonical_path,
            parent_chunks=chunks.parent_chunks,
            child_chunks=chunks.child_chunks,
            metadata={
                "arxiv_id": harvested.arxiv_id,
                "authors": harvested.authors,
                "categories": harvested.categories,
                "pdf_url": harvested.pdf_url,
                "license_status": harvested.license_status,
            },
        )

    def ingest_academic_metadata_record(
        self,
        harvested: HarvestedAcademicRecord,
    ) -> FixtureDocument:
        payload = {
            "provider": harvested.provider,
            "query_id": harvested.query_id,
            "external_id": harvested.external_id,
            "doi": harvested.doi,
            "title": harvested.title,
            "abstract": harvested.abstract,
            "authors": harvested.authors,
            "source_url": harvested.source_url,
            "landing_page_url": harvested.landing_page_url,
            "pdf_url": harvested.pdf_url,
            "license_status": harvested.license_status,
            "is_open_access": harvested.is_open_access,
            "dedupe_key": _academic_dedupe_key(harvested),
            "providers": [harvested.provider],
            "source_urls": [harvested.source_url],
            "pdf_urls": [harvested.pdf_url] if harvested.pdf_url else [],
            "provider_sources": [_academic_provider_source(harvested)],
        }
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        document_id = canonical_json_hash({"academic_paper": payload["dedupe_key"]})[:24]
        raw = self.raw_store.put(
            document_id,
            "json",
            payload_bytes,
            retrieval_method="academic_metadata_api",
        )
        canonical_text = (
            f"# {harvested.title}\n\n"
            f"Provider: {harvested.provider}\n"
            f"External ID: {harvested.external_id}\n"
            f"DOI: {harvested.doi or 'unknown'}\n"
            f"Authors: {', '.join(harvested.authors)}\n"
            f"Landing page: {harvested.landing_page_url or harvested.source_url}\n"
            f"PDF: {harvested.pdf_url or 'metadata-only'}\n"
            f"License status: {harvested.license_status}\n\n"
            f"## Abstract\n{harvested.abstract}"
        )
        chunks = ParentChildChunker(parent_token_target=240, child_token_target=40).chunk(
            document_id=document_id,
            text=canonical_text,
            section_title="Academic metadata",
        )
        canonical_path, canonical_hash = self.canonical_store.put_text(document_id, canonical_text)
        return FixtureDocument(
            source_key=harvested.source_key,
            document_id=document_id,
            document_type="paper",
            title=harvested.title,
            source_url=harvested.source_url,
            used_transcription=False,
            raw_artifact=raw,
            canonical_hash=canonical_hash,
            canonical_text_path=canonical_path,
            parent_chunks=chunks.parent_chunks,
            child_chunks=chunks.child_chunks,
            metadata=payload,
        )

    def ingest_github_repo_fixture(
        self,
        repo_root: Path,
        source_key: str,
        commit_hash: str,
    ) -> FixtureDocument:
        root = Path(repo_root)
        files = _selected_repo_files(root)
        payload = {
            "source_key": source_key,
            "commit_hash": commit_hash,
            "files": [
                {"path": path, "text": (root / path).read_text(encoding="utf-8")}
                for path in files
            ],
        }
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        document_id = canonical_json_hash(
            {"source_key": source_key, "commit_hash": commit_hash, "paths": files}
        )[:24]
        raw = self.raw_store.put(document_id, "json", payload_bytes)
        canonical_text = "\n\n".join(
            f"## {path}\n{(root / path).read_text(encoding='utf-8')}" for path in files
        )
        chunks = ParentChildChunker(parent_token_target=320, child_token_target=60).chunk(
            document_id=document_id,
            text=canonical_text,
            section_title=source_key,
        )
        canonical_path, canonical_hash = self.canonical_store.put_text(document_id, canonical_text)
        return FixtureDocument(
            source_key=source_key,
            document_id=document_id,
            document_type="github_repo",
            title=_repo_title(source_key),
            source_url=_repo_url(source_key),
            used_transcription=False,
            raw_artifact=raw,
            canonical_hash=canonical_hash,
            canonical_text_path=canonical_path,
            parent_chunks=chunks.parent_chunks,
            child_chunks=chunks.child_chunks,
            metadata={"commit_hash": commit_hash, "paths": files},
        )

    def ingest_harvested_repo(self, harvested: HarvestedRepo, repo_root: Path) -> FixtureDocument:
        root = Path(repo_root)
        payload = {
            "source_key": harvested.source_key,
            "commit_hash": harvested.commit_hash,
            "files": [
                {"path": path, "text": (root / path).read_text(encoding="utf-8")}
                for path in harvested.paths
            ],
        }
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        document_id = canonical_json_hash(
            {
                "source_key": harvested.source_key,
                "commit_hash": harvested.commit_hash,
                "paths": harvested.paths,
            }
        )[:24]
        raw = self.raw_store.put(
            document_id,
            "json",
            payload_bytes,
            retrieval_method="github_clone",
        )
        canonical_text = "\n\n".join(
            f"## {path}\n{(root / path).read_text(encoding='utf-8')}"
            for path in harvested.paths
        )
        chunks = ParentChildChunker(parent_token_target=320, child_token_target=60).chunk(
            document_id=document_id,
            text=canonical_text,
            section_title=harvested.source_key,
        )
        canonical_path, canonical_hash = self.canonical_store.put_text(document_id, canonical_text)
        return FixtureDocument(
            source_key=harvested.source_key,
            document_id=document_id,
            document_type="github_repo",
            title=_repo_title(harvested.source_key),
            source_url=harvested.source_url,
            used_transcription=False,
            raw_artifact=raw,
            canonical_hash=canonical_hash,
            canonical_text_path=canonical_path,
            parent_chunks=chunks.parent_chunks,
            child_chunks=chunks.child_chunks,
            metadata={"commit_hash": harvested.commit_hash, "paths": harvested.paths},
        )

    def ingest_reuters_metadata_record(
        self,
        harvested: HarvestedReutersMetadataRecord,
    ) -> FixtureDocument:
        payload = {
            "dataset_id": harvested.dataset_id,
            "dataset_title": harvested.dataset_title,
            "record_id": harvested.record_id,
            "title": harvested.title,
            "source_url": harvested.source_url,
            "published_at": harvested.published_at,
            "topics": harvested.topics,
            "places": harvested.places,
            "split": harvested.split,
            "license_status": harvested.license_status,
            "metadata_only": harvested.metadata_only,
        }
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        document_id = canonical_json_hash(
            {
                "source_key": harvested.source_key,
                "dataset_id": harvested.dataset_id,
                "record_id": harvested.record_id,
                "metadata_only": True,
            }
        )[:24]
        raw = self.raw_store.put(document_id, "json", payload_bytes)
        canonical_text = (
            f"# {harvested.title}\n\n"
            f"Dataset: {harvested.dataset_title}\n"
            f"Record ID: {harvested.record_id}\n"
            f"Published: {harvested.published_at or 'unknown'}\n"
            f"Topics: {', '.join(harvested.topics)}\n"
            f"Places: {', '.join(harvested.places)}\n"
            f"Split: {harvested.split or 'unknown'}\n"
            f"License status: {harvested.license_status}\n"
            "Metadata-only record. Full text was intentionally not ingested."
        )
        chunks = ParentChildChunker(parent_token_target=240, child_token_target=40).chunk(
            document_id=document_id,
            text=canonical_text,
            section_title=harvested.dataset_title,
        )
        canonical_path, canonical_hash = self.canonical_store.put_text(document_id, canonical_text)
        return FixtureDocument(
            source_key=harvested.source_key,
            document_id=document_id,
            document_type="news_dataset_record",
            title=harvested.title,
            source_url=harvested.source_url,
            used_transcription=False,
            raw_artifact=raw,
            canonical_hash=canonical_hash,
            canonical_text_path=canonical_path,
            parent_chunks=chunks.parent_chunks,
            child_chunks=chunks.child_chunks,
            metadata=payload,
        )


class _SignalsThreadsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.h1 = ""
        self.source_url = ""
        self.transcript_rows: list[tuple[str, str, str]] = []
        self._capture: str | None = None
        self._text: list[str] = []
        self._speaker = ""
        self._start = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key: value or "" for key, value in attrs}
        if tag == "article":
            self.source_url = attrs_map.get("data-source-url", self.source_url)
        if tag in {"title", "h1"}:
            self._capture = tag
            self._text = []
        if tag == "p" and "data-speaker" in attrs_map:
            self._capture = "transcript"
            self._text = []
            self._speaker = attrs_map.get("data-speaker", "")
            self._start = attrs_map.get("data-start", "")

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == tag and tag in {"title", "h1"}:
            text = " ".join(part.strip() for part in self._text if part.strip())
            if tag == "title":
                self.title = text
            else:
                self.h1 = text
            self._capture = None
            self._text = []
        elif self._capture == "transcript" and tag == "p":
            text = " ".join(part.strip() for part in self._text if part.strip())
            if text:
                self.transcript_rows.append((self._speaker, self._start, text))
            self._capture = None
            self._text = []
            self._speaker = ""
            self._start = ""


def _text(element: ElementTree.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return " ".join(element.text.split())


def _arxiv_id_from_url(url: str) -> str:
    tail = url.rstrip("/").split("/")[-1]
    return re.sub(r"v\d+$", "", tail)


def _academic_dedupe_key(harvested: HarvestedAcademicRecord) -> str:
    if harvested.doi:
        return f"doi:{harvested.doi}"
    return f"{harvested.provider}:{harvested.external_id}"


def _academic_provider_source(harvested: HarvestedAcademicRecord) -> dict[str, str | None]:
    return {
        "external_id": harvested.external_id,
        "license_status": harvested.license_status,
        "pdf_url": harvested.pdf_url,
        "provider": harvested.provider,
        "source_url": harvested.source_url,
    }


def _selected_repo_files(root: Path) -> list[str]:
    candidates: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        lowered = rel.casefold()
        if any(blocked in lowered for blocked in ["secret", "token", "password", "credential"]):
            continue
        name = path.name.casefold()
        is_readme = name == "readme" or name.startswith("readme.")
        is_license = name == "license" or name.startswith("license.")
        if is_readme or is_license or rel.startswith(("docs/", "examples/", "tests/", "src/")):
            candidates.append(rel)
    return candidates


def _repo_title(source_key: str) -> str:
    if source_key == "janestreet_ppx_expect":
        return "janestreet/ppx_expect fixture repository"
    return source_key.replace("_", "/")


def _repo_url(source_key: str) -> str:
    if source_key == "janestreet_ppx_expect":
        return "https://github.com/janestreet/ppx_expect"
    return f"https://github.com/{source_key.replace('_', '/')}"
