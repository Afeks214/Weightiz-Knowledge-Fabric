# WZ-KNOWLEDGE-FABRIC - Codex Instructions

## Mission

Build a research-only evidence knowledge system for podcasts, papers,
open-source repositories, and legally available research datasets.

The system ingests sources, preserves provenance, normalizes text, creates
parent/child chunks, extracts concepts and claims, builds retrieval indexes,
and exports concise Obsidian insight notes.

## Non-Negotiable Rules

- Do not build trading recommendations.
- Do not build target prices.
- Do not build live execution or order-routing functionality.
- Do not bypass paywalls.
- Do not scrape YouTube audio or captions unless explicit platform
  authorization and rights are provided.
- Do not ingest current Reuters/LSEG full text unless a license is configured.
- Do not depend on Google Scholar scraping.
- Prefer official transcripts over transcription.
- Prefer RSS transcript tags over audio transcription.
- Prefer authorized RSS enclosure audio over any platform scrape.
- Every document must have source_url, retrieved_at, source_hash,
  canonical_hash, and license_status.
- Every chunk must have chunk_hash and provenance.
- Every LLM-generated summary, claim, method, caveat, or Weightiz idea hook
  must include evidence_child_chunk_ids.
- Missing evidence must return ABSTAIN, not guessed output.
- Obsidian files are exports, not the canonical database.
- Raw transcripts must not be exported into Obsidian by default.
- Re-running ingestion must be idempotent.
- All expensive API calls must be cached by input_hash, prompt_hash, and
  model_name.
- Keep patches reviewable and evidence-bound.

## Engineering Style

- Small modules.
- Typed Pydantic models.
- Deterministic serialization.
- Content hashes everywhere.
- Snapshot tests for exported Markdown.
- Golden fixtures for source parsers.
- ABSTAIN-first behavior.

## Definition Of Done

A feature is complete only when:

1. It has tests.
2. It has a fixture when source parsing is involved.
3. It is idempotent.
4. It records source and canonical hashes.
5. It cannot silently fabricate missing evidence.
6. It updates README or docs.
7. It passes the focused verification command for the touched slice.
