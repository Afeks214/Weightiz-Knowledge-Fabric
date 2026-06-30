from wzkf.retrieval.context_pack import ContextPackBuilder
from wzkf.retrieval.hybrid_search import SearchResult


def test_context_pack_is_deterministic_and_cited():
    result = SearchResult(
        child_chunk_id="child-1",
        parent_chunk_id="parent-1",
        document_id="doc-1",
        source_title="ppx_expect README",
        source_url="https://github.com/janestreet/ppx_expect",
        text="Expect tests save program output and make diffs reviewable.",
        chunk_hash="sha256:child",
        score=0.91,
    )
    builder = ContextPackBuilder()

    first = builder.build("expect tests Weightiz artifacts", [result], created_for="codex")
    second = builder.build("expect tests Weightiz artifacts", [result], created_for="codex")

    assert first.abstain is False
    assert first.pack_hash == second.pack_hash
    assert first.included_chunks[0].child_chunk_id == "child-1"
    assert first.included_chunks[0].source_url.startswith("https://")


def test_context_pack_expands_child_hit_to_parent_context():
    result = SearchResult(
        child_chunk_id="child-1",
        parent_chunk_id="parent-1",
        document_id="doc-1",
        source_title="ppx_expect README",
        source_url="https://github.com/janestreet/ppx_expect",
        text="Expect tests save program output.",
        parent_text="Parent context includes the surrounding rationale and review workflow.",
        chunk_hash="sha256:child",
        score=0.91,
    )

    pack = ContextPackBuilder().build("expect tests", [result], created_for="codex")

    assert pack.included_chunks[0].text == result.parent_text
    assert pack.included_chunks[0].child_text == result.text


def test_context_pack_abstains_without_evidence():
    pack = ContextPackBuilder().build("unanswerable query", [], created_for="chatgpt")

    assert pack.abstain is True
    assert pack.abstain_reason == "No cited evidence chunks matched the query."
    assert pack.included_chunks == []
