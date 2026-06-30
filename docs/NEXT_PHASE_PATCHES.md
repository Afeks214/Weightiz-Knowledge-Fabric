# Next Phase Patch Register

These items are intentionally written as implementation-ready patch targets.
They preserve the current truth boundary: the local live MVP is proven;
production-grade WZKF is not proven.

## 1. GitHub Actions CI

- Run `uv run pytest`.
- Run `uv run wzkf sources validate`.
- Add a manual Docker acceptance workflow for
  `scripts/run_live_mvp_acceptance.sh` where Docker is available.

## 2. Secret Scanning And Push Protection

- Enable GitHub secret scanning and push protection.
- Add a CI scan for common API key and private key patterns.
- Keep `.env`, raw corpora, Docker volumes, and caches ignored.

## 3. CodeQL And Code Scanning

- Enable CodeQL for Python.
- Add dependency review for pull requests.
- Add a security policy for responsible disclosure.

## 4. OpenLineage-Style Run Metadata

- Emit run manifests for ingestion, embedding, extraction, retrieval, and
  export.
- Include run ID, source IDs, document IDs, job IDs, hashes, status, and error
  records.

## 5. Relevance Benchmark Dataset

- Add golden research questions.
- Require expected source IDs or chunk IDs.
- Report precision, recall, and citation coverage.

## 6. HNSW pgvector Index Migration

- Add migration for an HNSW index on `embeddings.embedding_vector`.
- Benchmark latency and recall against the MVP exact path.
- Document index build and memory tradeoffs.

## 7. Structured Logging

- Add JSON logs with run IDs, job IDs, document IDs, source IDs, and stage
  names.
- Ensure logs never include secrets or raw copyrighted corpus text.

## 8. Config Schema Validation

- Add Pydantic models for sources, rights policies, academic queries, ontology
  seeds, and extraction schemas.
- Fail closed on unknown policy IDs or malformed source records.

## 9. Data Quality Score

- Add per-source and per-document quality scores.
- Include rights confidence, metadata completeness, canonical text quality,
  chunk coverage, citation coverage, and extraction abstain rate.

## 10. Production Deployment Checklist

- Document auth, TLS, secrets, backups, restore test, retention policy,
  observability, rate limits, worker scaling, and disaster recovery gates.
