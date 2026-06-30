from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import subprocess
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from wzkf.api.main import create_app
from wzkf.db.models import (
    child_chunks,
    claims,
    concepts,
    context_packs,
    cost_ledger,
    documents,
    embeddings,
    parent_chunks,
    processing_jobs,
    raw_artifacts,
)
from wzkf.db.repositories import KnowledgeRepository
from wzkf.extraction.structured import EvidenceBoundExtractor
from wzkf.harvesters.academic_metadata import (
    AcademicHttpTransport,
    CachedAcademicMetadataClient,
    FileAcademicResponseCache,
)
from wzkf.harvesters.arxiv_api import ArxivAtomHarvester
from wzkf.harvesters.github_repo import GitHubRepoHarvester
from wzkf.harvesters.podcast_rss import PodcastRssHarvester
from wzkf.ingest.fixture_ingestor import FixtureDocument, FixtureIngestor
from wzkf.jobs.cost_ledger import FileCostLedger
from wzkf.jobs.queue import JobStatus, LocalJobQueue
from wzkf.jobs.rq_worker import (
    DEFAULT_REDIS_URL,
    DEFAULT_RQ_QUEUE,
    enqueue_embedding_job,
    work_rq_jobs,
)
from wzkf.pipeline.local import LocalKnowledgeFabric
from wzkf.retrieval.context_pack import ContextPackBuilder
from wzkf.retrieval.embedding_service import CachedEmbeddingService, FileOperationCache
from wzkf.retrieval.embeddings import MockEmbeddingProvider


FetchText = Callable[[str, dict[str, str] | None, dict[str, str] | None], str]
CloneRepo = Callable[[str, Path], str]


class LiveSmallSmokeError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveSmallSmokeConfig:
    storage_root: Path
    database_url: str
    podcast_source_key: str = "cheeky_pint"
    podcast_rss_url: str = "https://feeds.transistor.fm/cheeky-pint-with-john-collison"
    arxiv_query_id: str = "qfin_market_microstructure"
    arxiv_api_url: str = (
        "https://export.arxiv.org/api/query"
        "?search_query=all:%22limit%20order%20book%22&start=0&max_results=1"
    )
    academic_query_id: str = "qfin_market_microstructure"
    academic_search_query: str = "limit order book"
    openalex_limit: int = 1
    crossref_limit: int = 1
    github_source_key: str = "janestreet_ppx_expect"
    github_repo_url: str = "https://github.com/janestreet/ppx_expect.git"
    context_query: str = "limit order book market depth"
    query_embedding: list[float] | None = None
    created_for: str = "codex-live-small-smoke"
    use_rq: bool = False
    redis_url: str = DEFAULT_REDIS_URL
    queue_name: str = DEFAULT_RQ_QUEUE


@dataclass(frozen=True)
class LiveSmallSmokeResult:
    status: str
    document_count: int
    raw_artifact_count: int
    canonical_file_count: int
    parent_chunk_count: int
    child_chunk_count: int
    embedding_count: int
    cost_operations: int
    db_counts: dict[str, int]
    context_pack_hash: str
    api_search_status: int
    api_search_result_count: int
    api_context_status: int
    api_context_pack_hash: str
    obsidian_note_count: int
    evidence_path: Path
    api_search_path: Path
    api_context_pack_path: Path
    document_ids: list[str]
    source_urls: list[str]
    rq_used: bool = False
    rq_worked: bool = False
    rq_succeeded: int = 0
    rq_failed: int = 0
    rq_pending: int = 0


class _AcademicFetchTransport:
    def __init__(self, fetch_text: FetchText):
        self.fetch_text = fetch_text

    def get_text(
        self,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> str:
        return self.fetch_text(url, params, headers)


def run_live_small_smoke(
    config: LiveSmallSmokeConfig,
    fetch_text: FetchText | None = None,
    clone_repo: CloneRepo | None = None,
) -> LiveSmallSmokeResult:
    resolved_fetch = fetch_text or _fetch_text
    resolved_clone = clone_repo or _clone_repo
    root = Path(config.storage_root)
    root.mkdir(parents=True, exist_ok=True)
    evidence_root = root / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)

    fabric = LocalKnowledgeFabric(root)
    ingestor = FixtureIngestor(root)
    retrieved_at = datetime.now(UTC).isoformat()

    ingested = _ingest_live_documents(
        config=config,
        fetch_text=resolved_fetch,
        clone_repo=resolved_clone,
        fabric=fabric,
        ingestor=ingestor,
        retrieved_at=retrieved_at,
    )

    engine = create_engine(config.database_url)
    Session = sessionmaker(bind=engine)
    embedding_provider = MockEmbeddingProvider()
    embedding_service = CachedEmbeddingService(
        provider=embedding_provider,
        cache=FileOperationCache(root / "manifests" / "operation-cache.json"),
        config={"dimension": 8},
        cost_ledger=FileCostLedger(root / "manifests" / "cost-ledger.json"),
        provider_name="mock",
    )
    rq_summary = _run_rq_embeddings(config, root, ingested) if config.use_rq else {}
    manifest_embeddings = _manifest_embeddings(root)

    with Session() as session:
        repo = KnowledgeRepository(session)
        for document in ingested:
            repo.upsert_fixture_document(document)
            job_id = repo.upsert_processing_job(
                job_type="embed_document",
                document_id=document.document_id,
                input_hash=document.canonical_hash,
                status="SUCCEEDED",
            )
            for child in document.child_chunks:
                if config.use_rq:
                    embedding = _required_embedding(
                        manifest_embeddings,
                        embedding_provider.model_name,
                        child.id,
                    )
                else:
                    embedding = embedding_service.embed_text(child.text).embedding
                    fabric.upsert_embedding(child.id, embedding_provider.model_name, embedding)
                repo.upsert_embedding(child.id, embedding_provider.model_name, embedding)
            repo.record_cost(
                job_id=job_id,
                provider="mock",
                model=embedding_provider.model_name,
                estimated_cost_usd=0.0,
            )

        concepts_to_persist = fabric.rebuild_ontology()
        for concept in concepts_to_persist:
            repo.upsert_concept_record(concept)

        extractor = EvidenceBoundExtractor()
        for document in ingested:
            parent_by_child = {
                child.id: child.parent_chunk_id
                for child in document.child_chunks
            }
            extraction = extractor.extract(document.document_id, document.child_chunks)
            for claim in extraction.claims:
                if not claim.evidence_child_chunk_ids:
                    continue
                repo.upsert_claim(
                    claim,
                    parent_chunk_id=parent_by_child[claim.evidence_child_chunk_ids[0]],
                )

        query_embedding = config.query_embedding or embedding_provider.embed(config.context_query)
        if session.get_bind().dialect.name == "postgresql":
            search_results = repo.postgres_hybrid_search_child_chunks(
                query=config.context_query,
                query_embedding=query_embedding,
                embedding_model=embedding_provider.model_name,
                limit=10,
            )
        else:
            search_results = repo.hybrid_search_child_chunks(
                query=config.context_query,
                query_embedding=query_embedding,
                embedding_model=embedding_provider.model_name,
                limit=10,
            )
        context_pack = ContextPackBuilder().build(
            config.context_query,
            search_results,
            created_for=config.created_for,
        )
        repo.upsert_context_pack(context_pack)
        session.commit()

    obsidian_paths = fabric.export_obsidian(changed_only=True)
    api_search_path, api_context_path, api_search_status, api_count, api_context_status, api_hash = (
        _write_api_artifacts(
            config=config,
            root=root,
            engine_dialect=engine.dialect.name,
            query_embedding=query_embedding,
        )
    )
    db_counts = _db_counts(engine)
    summary = FileCostLedger(root / "manifests" / "cost-ledger.json").summary()
    result = LiveSmallSmokeResult(
        status="PASS",
        document_count=len(ingested),
        raw_artifact_count=db_counts["raw_artifacts"],
        canonical_file_count=len(list((root / "canonical").rglob("*.txt"))),
        parent_chunk_count=db_counts["parent_chunks"],
        child_chunk_count=db_counts["child_chunks"],
        embedding_count=db_counts["embeddings"],
        cost_operations=summary.operations,
        db_counts=db_counts,
        context_pack_hash=context_pack.pack_hash,
        api_search_status=api_search_status,
        api_search_result_count=api_count,
        api_context_status=api_context_status,
        api_context_pack_hash=api_hash,
        obsidian_note_count=len(list((root / "obsidian_export").glob("*.md"))),
        evidence_path=evidence_root / "live-small-smoke.json",
        api_search_path=api_search_path,
        api_context_pack_path=api_context_path,
        document_ids=[document.document_id for document in ingested],
        source_urls=[document.source_url for document in ingested],
        rq_used=config.use_rq,
        rq_worked=bool(rq_summary.get("worked", False)),
        rq_succeeded=int(rq_summary.get("succeeded", 0)),
        rq_failed=int(rq_summary.get("failed", 0)),
        rq_pending=int(rq_summary.get("pending", 0)),
    )
    result.evidence_path.write_text(
        json.dumps(_result_json(result), sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return result


def _ingest_live_documents(
    config: LiveSmallSmokeConfig,
    fetch_text: FetchText,
    clone_repo: CloneRepo,
    fabric: LocalKnowledgeFabric,
    ingestor: FixtureIngestor,
    retrieved_at: str,
) -> list[FixtureDocument]:
    documents: list[FixtureDocument] = []

    rss_xml = fetch_text(config.podcast_rss_url, None, None)
    episode = PodcastRssHarvester().harvest_first_episode(
        rss_xml,
        source_key=config.podcast_source_key,
    )
    if episode.selected_artifact_type != "transcript":
        raise LiveSmallSmokeError("podcast smoke requires an authorized transcript URL")
    transcript_text = fetch_text(episode.selected_artifact_url, None, None)
    documents.append(
        fabric._record(
            ingestor.ingest_harvested_podcast_transcript(
                episode,
                transcript_text,
                retrieved_at=retrieved_at,
            )
        )
    )

    arxiv_xml = fetch_text(config.arxiv_api_url, None, None)
    arxiv_records = ArxivAtomHarvester(query_id=config.arxiv_query_id).parse(arxiv_xml)
    if not arxiv_records:
        raise LiveSmallSmokeError("arxiv smoke returned no records")
    documents.append(fabric._record(ingestor.ingest_harvested_arxiv_paper(arxiv_records[0])))

    for provider, limit in [
        ("openalex", config.openalex_limit),
        ("crossref", config.crossref_limit),
    ]:
        client = CachedAcademicMetadataClient(
            provider=provider,
            query_id=config.academic_query_id,
            cache=FileAcademicResponseCache(root_cache_path(config.storage_root, provider)),
            transport=_AcademicFetchTransport(fetch_text),
        )
        result = client.fetch_query(config.academic_search_query, limit=limit)
        if not result.records:
            raise LiveSmallSmokeError(f"{provider} smoke returned no records")
        documents.append(
            fabric._record(ingestor.ingest_academic_metadata_record(result.records[0]))
        )

    repo_root = Path(config.storage_root) / "cache" / "repos" / config.github_source_key
    if repo_root.exists():
        shutil.rmtree(repo_root)
    repo_root.parent.mkdir(parents=True, exist_ok=True)
    commit_hash = clone_repo(config.github_repo_url, repo_root)
    harvested_repo = GitHubRepoHarvester().harvest_local_repo(
        repo_root,
        source_key=config.github_source_key,
        commit_hash=commit_hash,
    )
    if not harvested_repo.paths:
        raise LiveSmallSmokeError("github smoke selected no source files")
    documents.append(fabric._record(ingestor.ingest_harvested_repo(harvested_repo, repo_root)))

    return documents


def _run_rq_embeddings(
    config: LiveSmallSmokeConfig,
    root: Path,
    documents: list[FixtureDocument],
) -> dict[str, int | bool]:
    for document in documents:
        enqueue_embedding_job(
            redis_url=config.redis_url,
            storage_root=root,
            document_id=document.document_id,
            embedding_provider="mock",
            embedding_model=MockEmbeddingProvider.model_name,
            queue_name=config.queue_name,
        )
    worked = work_rq_jobs(
        redis_url=config.redis_url,
        queue_name=config.queue_name,
        burst=True,
        max_jobs=len(documents),
    )
    queue = LocalJobQueue(root / "manifests" / "jobs.json")
    succeeded = queue.count(JobStatus.SUCCEEDED)
    failed = queue.count(JobStatus.FAILED)
    pending = queue.count(JobStatus.PENDING)
    if failed or pending or succeeded < len(documents):
        raise LiveSmallSmokeError(
            "rq embedding jobs did not finish cleanly: "
            f"succeeded={succeeded} failed={failed} pending={pending}"
        )
    return {
        "worked": worked,
        "succeeded": succeeded,
        "failed": failed,
        "pending": pending,
    }


def _manifest_embeddings(root: Path) -> dict[str, list[float]]:
    manifest_path = Path(root) / "manifests" / "corpus.json"
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        key: [float(value) for value in raw["embedding"]]
        for key, raw in payload.get("embeddings", {}).items()
    }


def _required_embedding(
    manifest_embeddings: dict[str, list[float]],
    model_name: str,
    child_chunk_id: str,
) -> list[float]:
    key = f"{model_name}:{child_chunk_id}"
    try:
        return manifest_embeddings[key]
    except KeyError as exc:
        raise LiveSmallSmokeError(f"missing RQ embedding for child chunk: {child_chunk_id}") from exc


def root_cache_path(storage_root: Path, provider: str) -> Path:
    return Path(storage_root) / "cache" / f"{provider}-responses.json"


def _write_api_artifacts(
    config: LiveSmallSmokeConfig,
    root: Path,
    engine_dialect: str,
    query_embedding: list[float],
) -> tuple[Path, Path, int, int, int, str]:
    if engine_dialect == "postgresql":
        client = TestClient(create_app(storage_root=root, database_url=config.database_url))
        search_params = {
            "query": config.context_query,
            "embedding_model": MockEmbeddingProvider.model_name,
            "query_embedding": _embedding_param(query_embedding),
            "limit": "10",
        }
        context_body = {
            "query": config.context_query,
            "created_for": config.created_for,
            "embedding_model": MockEmbeddingProvider.model_name,
            "query_embedding": _embedding_param(query_embedding),
            "limit": 10,
        }
    else:
        client = TestClient(create_app(storage_root=root))
        search_params = {"query": config.context_query, "limit": "10"}
        context_body = {
            "query": config.context_query,
            "created_for": config.created_for,
            "limit": 10,
        }

    search_response = client.get("/search", params=search_params)
    context_response = client.post("/context-packs", json=context_body)
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    search_path = artifacts / "api-search.json"
    context_path = artifacts / "api-context-pack.json"
    search_path.write_text(
        json.dumps(search_response.json(), sort_keys=True, indent=2),
        encoding="utf-8",
    )
    context_path.write_text(
        json.dumps(context_response.json(), sort_keys=True, indent=2),
        encoding="utf-8",
    )
    search_body = search_response.json()
    context_json = context_response.json()
    return (
        search_path,
        context_path,
        search_response.status_code,
        len(search_body.get("results", [])),
        context_response.status_code,
        str(context_json.get("pack_hash", "")),
    )


def _fetch_text(
    url: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    query = urlencode(params or {})
    request_url = f"{url}?{query}" if query else url
    request = Request(request_url, headers=headers or {"User-Agent": "wzkf-live-small-smoke/0.1"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _clone_repo(repo_url: str, destination: Path) -> str:
    destination = Path(destination)
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(destination)],
        check=True,
        text=True,
        capture_output=True,
    )
    completed = subprocess.run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _db_counts(engine) -> dict[str, int]:
    tables = {
        "documents": documents,
        "raw_artifacts": raw_artifacts,
        "parent_chunks": parent_chunks,
        "child_chunks": child_chunks,
        "embeddings": embeddings,
        "concepts": concepts,
        "claims": claims,
        "jobs": processing_jobs,
        "costs": cost_ledger,
        "context_packs": context_packs,
    }
    with engine.connect() as conn:
        return {
            name: int(conn.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in tables.items()
        }


def _embedding_param(value: list[float]) -> str:
    return ",".join(f"{float(item):.12g}" for item in value)


def _result_json(result: LiveSmallSmokeResult) -> dict[str, object]:
    payload = asdict(result)
    for key in ["evidence_path", "api_search_path", "api_context_pack_path"]:
        payload[key] = str(payload[key])
    return payload
