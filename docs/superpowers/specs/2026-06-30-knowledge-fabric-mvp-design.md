# WZ Knowledge Fabric MVP Design

## Scope

This design implements the first reviewable slice of the attached
WZ-KNOWLEDGE-FABRIC plan. It creates an isolated research-only Python project
under `wz-knowledge-fabric/` without modifying `weightiz-main`, `weightiz-ui`,
or any live runtime path.

## Architecture

The MVP keeps canonical truth in typed records that map cleanly to PostgreSQL
tables and deterministic raw/canonical file storage. Source intake must pass
through a rights gate before text is normalized, chunked, embedded, searched,
or exported. Obsidian export receives short insight notes only and never raw
transcripts by default.

## Components

- `rights`: source records, license decisions, and ABSTAIN/BLOCKED outcomes.
- `harvesters`: official-feed/API parsers for podcast RSS transcript metadata,
  arXiv Atom, OpenAlex, Crossref, Unpaywall, CORE, GitHub repo fixtures, and
  Reuters metadata-only records.
- `storage`: sha256 hashing and deterministic file placement.
- `chunking`: parent-child chunking with stable chunk hashes.
- `ontology`: canonical concept and alias resolution, persisted concept
  records, evidence maps, and review items.
- `extraction`: evidence-bound structured claims.
- `retrieval`: mock embeddings, hybrid search DTOs, and deterministic context
  packs.
- `jobs`: file-backed local queue, embedding operation cache, and cost ledger
  summary for deterministic MVP processing.
- `export`: Obsidian insight-note and concept-note rendering.
- `db`: SQLAlchemy model metadata and Alembic migration scaffold.
- `api` and `cli`: entrypoints for search, context packs, concepts, source
  validation, fixture ingestion, job status, cost reporting, ontology review,
  and exports.

## Guardrails

The system does not produce trading recommendations, target prices, execution
instructions, or financial advice. It does not scrape YouTube, bypass paywalls,
or ingest current Reuters/LSEG full text without a configured license. Missing
evidence returns ABSTAIN.

## Verification

The first slice is verified by focused pytest coverage for rights gates,
hashing/storage, chunking, alias resolution, claim validation, context packs,
Obsidian export, cost-cache idempotency, DB metadata, CLI help, and a
Signals-and-Threads-style official transcript fixture. Current coverage also
includes arXiv Atom metadata, approved GitHub repo fixtures, Reuters-21578
metadata-only records, file-backed processing jobs, cached embeddings, and
job/cost CLI reporting. The ontology slice is verified by tests for alias
merging, review routing, local concept rebuild, concept API routes, CLI
ontology review, and Obsidian concept-note export. Academic metadata
enrichment is verified by provider fixtures for OpenAlex, Crossref, Unpaywall,
and CORE, with open-access PDF links stored only when the provider record
contains explicit open-access evidence.
