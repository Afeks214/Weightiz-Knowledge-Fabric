# Institutional Due Diligence

## A. Data Governance Model

WZ Knowledge Fabric uses a source catalog first model. Sources are declared in
`config/sources.yaml`, while legal and operational use boundaries are declared
in `config/rights_policies.yaml`.

The governance model separates:

- **Source catalog:** source ID, source type, title, strategy, source URL, and
  rights policy.
- **Rights policy:** whether full text is allowed, raw export is allowed, and
  whether a license is required.
- **License state:** allowed, metadata-only, license-required, blocked, unknown
  review, or abstained.
- **Provenance:** document IDs, source URLs, retrieval timestamps, source
  hashes, canonical hashes, storage paths, and retrieval methods.
- **Raw/canonical artifact separation:** raw artifacts are stored separately
  from normalized canonical text.
- **Hash strategy:** raw artifacts, canonical text, chunks, operations, and
  context packs are content-addressed or hash-derived.
- **ABSTAIN strategy:** missing evidence, unauthorized sources, or unknown
  rights produce abstention or review states instead of guessed output.

## B. Text Knowledge Store Architecture

The repository follows a bronze/silver/gold model:

- **Bronze layer:** raw retrieved artifacts, including RSS/transcript payloads,
  academic metadata payloads, repository files, and historical dataset records.
- **Silver layer:** canonical normalized text files and canonical document
  metadata.
- **Gold layer:** parent chunks, child chunks, embeddings, concepts, claims,
  costs, jobs, and context packs.
- **Obsidian layer:** export-only insight notes and concept notes. Obsidian is
  not the canonical database.

The canonical runtime truth is Postgres plus deterministic raw/canonical
artifact storage. Obsidian receives concise evidence references, not raw corpus
dumps.

## C. Search And Retrieval

The current MVP implements:

- PostgreSQL full-text search over child chunks.
- pgvector semantic retrieval using stored embedding vectors.
- Score fusion as a simple text score plus weighted vector score.
- Parent-child expansion by returning parent context for retrieved children.
- Context-pack citations with document IDs, child chunk IDs, source URLs, and
  chunk hashes.

Future retrieval hardening should add:

- score normalization,
- reciprocal-rank or learned fusion,
- reranking,
- golden query sets,
- precision/recall metrics,
- latency benchmarks,
- HNSW or IVFFlat pgvector index evaluation.

## D. Lineage And Audit

Current audit evidence includes:

- deterministic document IDs,
- source hashes,
- canonical hashes,
- parent and child chunk hashes,
- processing job IDs,
- cost operation keys,
- context pack hashes,
- acceptance run summaries.

Future lineage should add OpenLineage-compatible run manifests:

```json
{
  "run_id": "string",
  "started_at": "timestamp",
  "finished_at": "timestamp",
  "source_ids": [],
  "document_ids": [],
  "raw_hashes": [],
  "canonical_hashes": [],
  "chunk_hashes": [],
  "context_pack_hashes": [],
  "job_ids": [],
  "status": "PASS | FAIL | ABSTAINED"
}
```

## E. Security

Current security posture:

- `.env`, `.venv`, caches, raw/canonical runtime data, Docker volumes, and logs
  are ignored.
- No API keys or credentials are required for the default test path.
- The OpenAI embedding path fails closed when no runtime key is supplied.
- The GitHub repository harvester excludes filenames containing terms such as
  `secret`, `token`, `password`, and `credential`.
- Public evidence artifacts are sanitized to avoid local user paths.

Recommended next controls:

- enable GitHub secret scanning and push protection,
- enable CodeQL/code scanning,
- add dependency review,
- add a public `SECURITY.md`,
- add full repository secret scanning in CI,
- add SBOM/dependency inventory,
- keep raw copyrighted corpora outside the public repository.

## F. Remaining Gaps

- Production deployment is not proven.
- Hosted API authentication, TLS, rate limiting, and monitoring are not proven.
- Paid live OpenAI embeddings are not proven.
- Broad-scale ingestion is not proven.
- Search relevance benchmarks are not proven.
- Observability and OpenLineage-compatible run metadata are not implemented.
- Backup, restore, data retention, and access-control procedures are not
  implemented.
- Licensed current Reuters/LSEG full-text ingestion is not implemented and must
  remain blocked until a license is configured.
