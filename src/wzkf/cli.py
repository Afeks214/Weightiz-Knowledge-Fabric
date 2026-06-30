from __future__ import annotations

import os
from pathlib import Path

import typer

from wzkf.harvesters.academic_metadata import (
    AcademicMetadataError,
    CachedAcademicMetadataClient,
    FileAcademicResponseCache,
)
from wzkf.harvesters.arxiv_api import ArxivAtomHarvester
from wzkf.harvesters.podcast_rss import PodcastRssHarvester, PodcastRssPolicyError
from wzkf.ingest.fixture_ingestor import FixtureIngestor
from wzkf.jobs.cost_ledger import FileCostLedger
from wzkf.jobs.queue import JobStatus, LocalJobQueue
from wzkf.jobs.rq_worker import (
    DEFAULT_REDIS_URL,
    DEFAULT_RQ_QUEUE,
    enqueue_embedding_job,
    work_rq_jobs,
)
from wzkf.jobs.runner import JobRunResult, KnowledgeJobRunner
from wzkf.pipeline.local import LocalKnowledgeFabric
from wzkf.registry.source_registry import SourceRegistry, SourceRegistryError
from wzkf.retrieval.context_pack import ContextPackBuilder
from wzkf.retrieval.embedding_service import CachedEmbeddingService, FileOperationCache
from wzkf.retrieval.embeddings import (
    EmbeddingProviderError,
    MockEmbeddingProvider,
    OPENAI_EMBEDDINGS_ENDPOINT,
    OpenAIEmbeddingProvider,
)
from wzkf.retrieval.live_postgres import live_postgres_search, resolve_query_embedding
from wzkf.smoke.live_small import LiveSmallSmokeConfig, LiveSmallSmokeError, run_live_small_smoke


app = typer.Typer(no_args_is_help=True, help="WZ Knowledge Fabric CLI")
sources_app = typer.Typer(help="Source registry commands")
ingest_app = typer.Typer(help="Ingestion commands")
process_app = typer.Typer(help="Processing commands")
export_app = typer.Typer(help="Export commands")
jobs_app = typer.Typer(help="Job commands")
costs_app = typer.Typer(help="Cost ledger commands")
ontology_app = typer.Typer(help="Ontology commands")
smoke_app = typer.Typer(help="Smoke and acceptance commands")


@sources_app.command("validate")
def validate_sources(
    sources: Path = typer.Option(Path("config/sources.yaml"), "--sources"),
    rights_policies: Path = typer.Option(
        Path("config/rights_policies.yaml"),
        "--rights-policies",
    ),
) -> None:
    try:
        registry = SourceRegistry.from_files(sources, rights_policies)
    except SourceRegistryError as exc:
        typer.echo(f"source registry invalid: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"sources.yaml valid: {len(registry.sources)} sources")


@ingest_app.command("podcast")
def ingest_podcast(
    source: str = typer.Option(..., "--source"),
    fixture: Path | None = typer.Option(None, "--fixture"),
    rss_feed: Path | None = typer.Option(None, "--rss-feed"),
    transcript_fixture: Path | None = typer.Option(None, "--transcript-fixture"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    if rss_feed is not None:
        try:
            episode = PodcastRssHarvester().harvest_first_episode(
                rss_feed.read_text(encoding="utf-8"),
                source_key=source,
            )
        except PodcastRssPolicyError as exc:
            typer.echo(f"ABSTAIN: {exc}")
            raise typer.Exit(code=1) from exc
        if episode.selected_artifact_type != "transcript" or transcript_fixture is None:
            typer.echo("ABSTAIN: RSS audio transcription is not wired in the MVP")
            raise typer.Exit(code=1)
        document = LocalKnowledgeFabric(storage_root).ingest_signals_threads_fixture(
            transcript_fixture
        )
        typer.echo(
            f"selected transcript {episode.selected_artifact_url}; "
            f"ingested {document.title}"
        )
        return

    if source != "signals_threads" or fixture is None:
        typer.echo("ABSTAIN: fixture-backed signals_threads ingestion is the only MVP path")
        raise typer.Exit(code=1)
    document = LocalKnowledgeFabric(storage_root).ingest_signals_threads_fixture(fixture)
    typer.echo(f"ingested {document.source_key}:{document.title}")


@ingest_app.command("papers")
def ingest_papers(
    query: str = typer.Option(..., "--query"),
    fixture: Path | None = typer.Option(None, "--fixture"),
    atom: Path | None = typer.Option(None, "--atom"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    if atom is not None:
        papers = ArxivAtomHarvester(query_id=query).parse(atom.read_text(encoding="utf-8"))
        fabric = LocalKnowledgeFabric(storage_root)
        ingestor = FixtureIngestor(storage_root)
        for paper in papers:
            fabric._record(ingestor.ingest_harvested_arxiv_paper(paper))
        typer.echo(f"harvested arxiv:{query}: {len(papers)} papers")
        return

    if query != "qfin_market_microstructure" or fixture is None:
        typer.echo(
            "ABSTAIN: fixture-backed qfin_market_microstructure "
            "ingestion is the only MVP path"
        )
        raise typer.Exit(code=1)
    document = LocalKnowledgeFabric(storage_root).ingest_arxiv_fixture(fixture)
    typer.echo(f"ingested {document.source_key}:{document.title}")


@ingest_app.command("repo")
def ingest_repo(
    source: str = typer.Option(..., "--source"),
    fixture: Path | None = typer.Option(None, "--fixture"),
    commit_hash: str = typer.Option("fixture-commit", "--commit-hash"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    if fixture is None:
        typer.echo("ABSTAIN: repo ingestion requires an approved fixture path in the MVP")
        raise typer.Exit(code=1)
    document = LocalKnowledgeFabric(storage_root).ingest_github_repo_fixture(
        fixture,
        source_key=source,
        commit_hash=commit_hash,
    )
    typer.echo(f"ingested {document.source_key}:{document.title}")


@ingest_app.command("academic")
def ingest_academic(
    provider: str = typer.Option(..., "--provider"),
    query: str = typer.Option(..., "--query"),
    fixture: Path | None = typer.Option(None, "--fixture"),
    search_query: str | None = typer.Option(None, "--search-query"),
    doi: str | None = typer.Option(None, "--doi"),
    limit: int = typer.Option(25, "--limit", min=1),
    api_key: str | None = typer.Option(None, "--api-key"),
    email: str | None = typer.Option(None, "--email"),
    cache_path: Path | None = typer.Option(None, "--cache-path"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    if fixture is not None:
        documents = LocalKnowledgeFabric(storage_root).ingest_academic_metadata_fixture(
            provider=provider,
            fixture_path=fixture,
            query_id=query,
        )
        typer.echo(f"harvested academic:{provider}:{query}: {len(documents)} records")
        return

    if search_query is None and doi is None:
        typer.echo("ABSTAIN: academic ingestion requires --fixture, --search-query, or --doi")
        raise typer.Exit(code=1)
    if search_query is not None and doi is not None:
        typer.echo("ABSTAIN: use only one of --search-query or --doi")
        raise typer.Exit(code=1)

    response_cache = FileAcademicResponseCache(
        cache_path or storage_root / "cache" / "academic-api-responses.json"
    )
    client = CachedAcademicMetadataClient(
        provider=provider,
        query_id=query,
        cache=response_cache,
        config=_academic_client_config(provider, api_key=api_key, email=email),
    )
    try:
        result = (
            client.fetch_doi(doi)
            if doi is not None
            else client.fetch_query(search_query or "", limit=limit)
        )
    except AcademicMetadataError as exc:
        typer.echo(f"ABSTAIN: {exc}")
        raise typer.Exit(code=1) from exc

    fabric = LocalKnowledgeFabric(storage_root)
    ingestor = FixtureIngestor(storage_root)
    for record in result.records:
        fabric._record(ingestor.ingest_academic_metadata_record(record))
    typer.echo(
        f"harvested academic:{provider}:{query}: {len(result.records)} records "
        f"cache_hit={str(result.cache_hit).lower()} operation_key={result.operation_key}"
    )


@ingest_app.command("news")
def ingest_news(
    source: str = typer.Option(..., "--source"),
    fixture: Path | None = typer.Option(None, "--fixture"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    if source != "reuters_21578" or fixture is None:
        typer.echo("ABSTAIN: Reuters-21578 metadata fixture is the only MVP news path")
        raise typer.Exit(code=1)
    documents = LocalKnowledgeFabric(storage_root).ingest_reuters_metadata_fixture(fixture)
    typer.echo(f"metadata-only {source} records ingested: {len(documents)}")


@app.command("search")
def search(
    query: str,
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
    database_url: str | None = typer.Option(None, "--database-url"),
    embedding_model: str = typer.Option(MockEmbeddingProvider.model_name, "--embedding-model"),
    query_embedding: str | None = typer.Option(None, "--query-embedding"),
    limit: int = typer.Option(10, "--limit", min=1),
) -> None:
    resolved_database_url = _database_url(database_url)
    if resolved_database_url:
        try:
            results = live_postgres_search(
                query=query,
                database_url=resolved_database_url,
                embedding_model=embedding_model,
                query_embedding=resolve_query_embedding(query, query_embedding),
                limit=limit,
            )
        except ValueError as exc:
            typer.echo(f"ABSTAIN: {exc}")
            raise typer.Exit(code=1) from exc
    else:
        results = LocalKnowledgeFabric(storage_root).search(query, limit=limit)
    if not results:
        typer.echo(f"ABSTAIN: no indexed evidence chunks for query: {query}")
        return
    for result in results:
        typer.echo(
            f"{result.score:.2f}\t{result.document_id}\t"
            f"{result.child_chunk_id}\t{result.source_url}"
        )


@app.command("context-pack")
def context_pack(
    query: str,
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
    database_url: str | None = typer.Option(None, "--database-url"),
    embedding_model: str = typer.Option(MockEmbeddingProvider.model_name, "--embedding-model"),
    query_embedding: str | None = typer.Option(None, "--query-embedding"),
    limit: int = typer.Option(10, "--limit", min=1),
) -> None:
    resolved_database_url = _database_url(database_url)
    if resolved_database_url:
        try:
            results = live_postgres_search(
                query=query,
                database_url=resolved_database_url,
                embedding_model=embedding_model,
                query_embedding=resolve_query_embedding(query, query_embedding),
                limit=limit,
            )
        except ValueError as exc:
            typer.echo(f"ABSTAIN: {exc}")
            raise typer.Exit(code=1) from exc
        pack = ContextPackBuilder().build(query, results, created_for="codex")
    else:
        pack = LocalKnowledgeFabric(storage_root).context_pack(query, created_for="codex")
    typer.echo(pack.model_dump_json())


@export_app.command("obsidian")
def export_obsidian(
    changed_only: bool = typer.Option(False, "--changed-only"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    paths = LocalKnowledgeFabric(storage_root).export_obsidian(changed_only=changed_only)
    typer.echo(f"obsidian exported {len(paths)} notes")


@process_app.command("document")
def process_document(
    document_id: str = typer.Option(..., "--document-id"),
    embedding_provider: str = typer.Option("mock", "--embedding-provider"),
    embedding_model: str | None = typer.Option(None, "--embedding-model"),
    api_key: str | None = typer.Option(None, "--api-key"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    fabric = LocalKnowledgeFabric(storage_root)
    document = fabric.get_document(document_id)
    if document is None:
        typer.echo(f"ABSTAIN: document not found: {document_id}")
        raise typer.Exit(code=1)
    try:
        service = _embedding_service(
            storage_root,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            api_key=api_key,
        )
    except EmbeddingProviderError as exc:
        typer.echo(f"ABSTAIN: {exc}")
        raise typer.Exit(code=1) from exc
    queue = LocalJobQueue(_jobs_path(storage_root))
    queue.enqueue(
        job_type="embed_document",
        document_id=document_id,
        input_hash=document["canonical_hash"],
        payload={
            "embedding_provider": service.provider_name,
            "embedding_model": service.model_name,
        },
    )
    result = _run_pending_embedding_jobs(fabric, queue, service)
    _echo_job_run_result(result)


@process_app.command("all")
def process_all(
    pending: bool = typer.Option(False, "--pending"),
    embedding_provider: str = typer.Option("mock", "--embedding-provider"),
    embedding_model: str | None = typer.Option(None, "--embedding-model"),
    api_key: str | None = typer.Option(None, "--api-key"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    if not pending:
        typer.echo("ABSTAIN: use --pending to run queued processing jobs")
        raise typer.Exit(code=1)
    try:
        service = _embedding_service(
            storage_root,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            api_key=api_key,
        )
    except EmbeddingProviderError as exc:
        typer.echo(f"ABSTAIN: {exc}")
        raise typer.Exit(code=1) from exc
    result = _run_pending_embedding_jobs(
        LocalKnowledgeFabric(storage_root),
        LocalJobQueue(_jobs_path(storage_root)),
        service,
    )
    _echo_job_run_result(result)


@jobs_app.command("status")
def jobs_status(storage_root: Path = typer.Option(Path("data"), "--storage-root")) -> None:
    queue = LocalJobQueue(_jobs_path(storage_root))
    parts = [f"total={queue.count()}"]
    for status in JobStatus:
        parts.append(f"{status.value.lower()}={queue.count(status=status)}")
    typer.echo("jobs " + " ".join(parts))


@jobs_app.command("enqueue-rq")
def jobs_enqueue_rq(
    document_id: str = typer.Option(..., "--document-id"),
    redis_url: str = typer.Option(DEFAULT_REDIS_URL, "--redis-url"),
    queue_name: str = typer.Option(DEFAULT_RQ_QUEUE, "--queue-name"),
    embedding_provider: str = typer.Option("mock", "--embedding-provider"),
    embedding_model: str | None = typer.Option(None, "--embedding-model"),
    storage_root: Path = typer.Option(Path("data"), "--storage-root"),
) -> None:
    try:
        result = enqueue_embedding_job(
            redis_url=redis_url,
            storage_root=storage_root,
            document_id=document_id,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            queue_name=queue_name,
        )
    except (EmbeddingProviderError, ValueError) as exc:
        typer.echo(f"ABSTAIN: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(
        "rq enqueued "
        f"local_job_id={result['local_job_id']} "
        f"rq_job_id={result['rq_job_id']} "
        f"created={str(result['created_rq_job']).lower()}"
    )


@jobs_app.command("work-rq")
def jobs_work_rq(
    redis_url: str = typer.Option(DEFAULT_REDIS_URL, "--redis-url"),
    queue_name: str = typer.Option(DEFAULT_RQ_QUEUE, "--queue-name"),
    burst: bool = typer.Option(True, "--burst/--no-burst"),
    max_jobs: int | None = typer.Option(None, "--max-jobs", min=1),
) -> None:
    worked = work_rq_jobs(
        redis_url=redis_url,
        queue_name=queue_name,
        burst=burst,
        max_jobs=max_jobs,
    )
    typer.echo(
        f"rq worker queue={queue_name} "
        f"burst={str(burst).lower()} worked={str(worked).lower()}"
    )


@costs_app.command("report")
def costs_report(storage_root: Path = typer.Option(Path("data"), "--storage-root")) -> None:
    summary = FileCostLedger(_costs_path(storage_root)).summary()
    typer.echo(
        f"costs operations={summary.operations} "
        f"estimated_cost_usd={summary.estimated_cost_usd:.6f}"
    )


@ontology_app.command("review")
def ontology_review(storage_root: Path = typer.Option(Path("data"), "--storage-root")) -> None:
    fabric = LocalKnowledgeFabric(storage_root)
    concepts = fabric.rebuild_ontology()
    review_items = fabric.concept_review_items()
    names = ", ".join(concept.canonical_name for concept in concepts) or "none"
    typer.echo(
        f"ontology concepts={len(concepts)} "
        f"review_items={len(review_items)} resolved={names}"
    )


@smoke_app.command("live-small")
def smoke_live_small(
    storage_root: Path = typer.Option(Path("data/live-small-smoke"), "--storage-root"),
    database_url: str | None = typer.Option(None, "--database-url"),
    podcast_rss_url: str = typer.Option(
        "https://feeds.transistor.fm/cheeky-pint-with-john-collison",
        "--podcast-rss-url",
    ),
    arxiv_api_url: str = typer.Option(
        (
            "https://export.arxiv.org/api/query"
            "?search_query=all:%22limit%20order%20book%22&start=0&max_results=1"
        ),
        "--arxiv-api-url",
    ),
    academic_search_query: str = typer.Option("limit order book", "--academic-search-query"),
    github_repo_url: str = typer.Option(
        "https://github.com/janestreet/ppx_expect.git",
        "--github-repo-url",
    ),
    context_query: str = typer.Option("limit order book market depth", "--context-query"),
    use_rq: bool = typer.Option(False, "--use-rq/--direct"),
    redis_url: str = typer.Option(DEFAULT_REDIS_URL, "--redis-url"),
    queue_name: str = typer.Option(DEFAULT_RQ_QUEUE, "--queue-name"),
) -> None:
    resolved_database_url = _database_url(database_url)
    if not resolved_database_url:
        typer.echo("ABSTAIN: live-small smoke requires --database-url or DATABASE_URL")
        raise typer.Exit(code=1)
    try:
        result = run_live_small_smoke(
            LiveSmallSmokeConfig(
                storage_root=storage_root,
                database_url=resolved_database_url,
                podcast_rss_url=podcast_rss_url,
                arxiv_api_url=arxiv_api_url,
                academic_search_query=academic_search_query,
                github_repo_url=github_repo_url,
                context_query=context_query,
                use_rq=use_rq,
                redis_url=redis_url,
                queue_name=queue_name,
            )
        )
    except LiveSmallSmokeError as exc:
        typer.echo(f"ABSTAIN: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"live-small status={result.status}")
    typer.echo(f"evidence_path={result.evidence_path}")
    typer.echo(
        "counts "
        f"documents={result.db_counts['documents']} "
        f"raw_artifacts={result.db_counts['raw_artifacts']} "
        f"child_chunks={result.db_counts['child_chunks']} "
        f"embeddings={result.db_counts['embeddings']} "
        f"concepts={result.db_counts['concepts']} "
        f"claims={result.db_counts['claims']} "
        f"context_packs={result.db_counts['context_packs']}"
    )
    typer.echo(
        f"api_search_status={result.api_search_status} "
        f"api_search_result_count={result.api_search_result_count} "
        f"api_context_status={result.api_context_status}"
    )
    typer.echo(
        f"context_pack_hash={result.context_pack_hash} "
        f"obsidian_notes={result.obsidian_note_count} "
        f"cost_operations={result.cost_operations}"
    )
    if result.rq_used:
        typer.echo(
            f"rq worked={str(result.rq_worked).lower()} "
            f"succeeded={result.rq_succeeded} "
            f"failed={result.rq_failed} "
            f"pending={result.rq_pending}"
        )


def _run_pending_embedding_jobs(
    fabric: LocalKnowledgeFabric,
    queue: LocalJobQueue,
    service: CachedEmbeddingService,
) -> JobRunResult:
    return KnowledgeJobRunner(
        fabric=fabric,
        queue=queue,
        embedding_service=service,
    ).run_pending()


def _embedding_service(
    storage_root: Path,
    embedding_provider: str,
    embedding_model: str | None,
    api_key: str | None,
) -> CachedEmbeddingService:
    normalized_provider = embedding_provider.lower().strip()
    if normalized_provider == "mock":
        return CachedEmbeddingService(
            provider=MockEmbeddingProvider(),
            cache=FileOperationCache(_operation_cache_path(storage_root)),
            config={"dimension": 8},
            cost_ledger=FileCostLedger(_costs_path(storage_root)),
            provider_name="mock",
        )
    if normalized_provider == "openai":
        resolved_api_key = api_key or os.environ.get("WZKF_OPENAI_API_KEY")
        if not resolved_api_key or not resolved_api_key.strip():
            raise EmbeddingProviderError("openai embedding provider requires api_key")
        resolved_api_key = resolved_api_key.strip()
        model_name = embedding_model or "text-embedding-3-small"
        return CachedEmbeddingService(
            provider=OpenAIEmbeddingProvider(
                api_key=resolved_api_key,
                model_name=model_name,
            ),
            cache=FileOperationCache(_operation_cache_path(storage_root)),
            config={
                "endpoint": OPENAI_EMBEDDINGS_ENDPOINT,
                "provider": "openai",
            },
            cost_ledger=FileCostLedger(_costs_path(storage_root)),
            provider_name="openai",
        )
    raise EmbeddingProviderError(f"unsupported embedding provider: {embedding_provider}")


def _echo_job_run_result(result: JobRunResult) -> None:
    typer.echo(
        f"processed jobs succeeded={result.succeeded} "
        f"failed={result.failed} skipped={result.skipped}"
    )


def _jobs_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "jobs.json"


def _operation_cache_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "operation-cache.json"


def _costs_path(storage_root: Path) -> Path:
    return Path(storage_root) / "manifests" / "cost-ledger.json"


def _database_url(database_url: str | None) -> str | None:
    return database_url or os.environ.get("DATABASE_URL")


def _academic_client_config(
    provider: str,
    api_key: str | None,
    email: str | None,
) -> dict[str, str]:
    config: dict[str, str] = {}
    provider_upper = provider.upper().replace("-", "_")
    resolved_api_key = api_key or os.environ.get(f"WZKF_{provider_upper}_API_KEY")
    if resolved_api_key:
        config["api_key"] = resolved_api_key
    resolved_email = (
        email
        or os.environ.get(f"WZKF_{provider_upper}_EMAIL")
        or os.environ.get("WZKF_ACADEMIC_EMAIL")
    )
    if resolved_email:
        config["email"] = resolved_email
        config["mailto"] = resolved_email
    return config


app.add_typer(sources_app, name="sources")
app.add_typer(ingest_app, name="ingest")
app.add_typer(process_app, name="process")
app.add_typer(export_app, name="export")
app.add_typer(jobs_app, name="jobs")
app.add_typer(costs_app, name="costs")
app.add_typer(ontology_app, name="ontology")
app.add_typer(smoke_app, name="smoke")
