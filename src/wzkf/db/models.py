from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
)
from sqlalchemy.types import UserDefinedType


metadata = MetaData()


class PgVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int | None = None):
        self.dimensions = dimensions

    def get_col_spec(self, **kw) -> str:
        if self.dimensions is None:
            return "vector"
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect):
        def process(value):
            if value is None or isinstance(value, str):
                return value
            return "[" + ",".join(f"{float(item):.12g}" for item in value) + "]"

        return process

sources = Table(
    "sources",
    metadata,
    Column("id", Text, primary_key=True),
    Column("source_key", Text, nullable=False, unique=True),
    Column("source_type", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("publisher", Text),
    Column("homepage_url", Text),
    Column("rss_url", Text),
    Column("rights_policy", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

documents = Table(
    "documents",
    metadata,
    Column("id", Text, primary_key=True),
    Column("source_id", Text, ForeignKey("sources.id")),
    Column("document_type", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("canonical_url", Text),
    Column("published_at", DateTime(timezone=True)),
    Column("authors_json", JSON, nullable=False),
    Column("guests_json", JSON, nullable=False),
    Column("abstract", Text),
    Column("license_status", Text, nullable=False),
    Column("ingestion_status", Text, nullable=False),
    Column("source_hash", Text),
    Column("canonical_hash", Text),
    Column("raw_path", Text),
    Column("canonical_text_path", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

raw_artifacts = Table(
    "raw_artifacts",
    metadata,
    Column("id", Text, primary_key=True),
    Column("document_id", Text, ForeignKey("documents.id")),
    Column("artifact_type", Text, nullable=False),
    Column("storage_path", Text, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("retrieved_at", DateTime(timezone=True), nullable=False),
    Column("retrieval_method", Text, nullable=False),
)

parent_chunks = Table(
    "parent_chunks",
    metadata,
    Column("id", Text, primary_key=True),
    Column("document_id", Text, ForeignKey("documents.id")),
    Column("chunk_index", Integer, nullable=False),
    Column("section_title", Text),
    Column("speaker", Text),
    Column("start_time_sec", Float),
    Column("end_time_sec", Float),
    Column("page_start", Integer),
    Column("page_end", Integer),
    Column("text", Text, nullable=False),
    Column("token_count", Integer, nullable=False),
    Column("chunk_hash", Text, nullable=False),
)

child_chunks = Table(
    "child_chunks",
    metadata,
    Column("id", Text, primary_key=True),
    Column("parent_chunk_id", Text, ForeignKey("parent_chunks.id")),
    Column("document_id", Text, ForeignKey("documents.id")),
    Column("child_index", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("token_count", Integer, nullable=False),
    Column("chunk_hash", Text, nullable=False),
)

embeddings = Table(
    "embeddings",
    metadata,
    Column("id", Text, primary_key=True),
    Column("child_chunk_id", Text, ForeignKey("child_chunks.id")),
    Column("embedding_model", Text, nullable=False),
    Column("embedding", JSON),
    Column("embedding_vector", PgVector()),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

concepts = Table(
    "concepts",
    metadata,
    Column("id", Text, primary_key=True),
    Column("canonical_name", Text, nullable=False, unique=True),
    Column("concept_type", Text, nullable=False),
    Column("description", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

concept_aliases = Table(
    "concept_aliases",
    metadata,
    Column("id", Text, primary_key=True),
    Column("concept_id", Text, ForeignKey("concepts.id")),
    Column("alias", Text, nullable=False),
    Column("alias_source", Text, nullable=False),
    Column("confidence", Float, nullable=False),
)

document_concepts = Table(
    "document_concepts",
    metadata,
    Column("document_id", Text, ForeignKey("documents.id"), primary_key=True),
    Column("concept_id", Text, ForeignKey("concepts.id"), primary_key=True),
    Column("confidence", Float, nullable=False),
    Column("evidence_child_chunk_ids", JSON, nullable=False),
)

claims = Table(
    "claims",
    metadata,
    Column("id", Text, primary_key=True),
    Column("document_id", Text, ForeignKey("documents.id")),
    Column("parent_chunk_id", Text, ForeignKey("parent_chunks.id")),
    Column("claim_text", Text, nullable=False),
    Column("claim_type", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("extraction_model", Text, nullable=False),
    Column("evidence_child_chunk_ids", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

relations = Table(
    "relations",
    metadata,
    Column("id", Text, primary_key=True),
    Column("subject_concept_id", Text, ForeignKey("concepts.id")),
    Column("relation_type", Text, nullable=False),
    Column("object_concept_id", Text, ForeignKey("concepts.id")),
    Column("evidence_child_chunk_id", Text, ForeignKey("child_chunks.id")),
    Column("confidence", Float, nullable=False),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("job_type", Text, nullable=False),
    Column("document_id", Text, ForeignKey("documents.id")),
    Column("input_hash", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_message", Text),
    Column("retry_count", Integer, nullable=False, default=0),
)

costs = Table(
    "costs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("job_id", Text, ForeignKey("jobs.id")),
    Column("provider", Text, nullable=False),
    Column("model", Text),
    Column("unit_type", Text),
    Column("input_units", Float),
    Column("output_units", Float),
    Column("estimated_cost_usd", Float),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

processing_jobs = jobs
cost_ledger = costs

context_packs = Table(
    "context_packs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("query", Text, nullable=False),
    Column("pack_hash", Text, nullable=False),
    Column("included_child_chunk_ids", JSON, nullable=False),
    Column("created_for", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
