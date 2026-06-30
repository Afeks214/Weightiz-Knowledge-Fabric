from wzkf.chunking.parent_child import ParentChildChunker


def test_parent_child_chunk_relationship_and_hashes_are_stable():
    text = (
        "# Intro\n"
        "Limit order book research studies visible market depth and order flow.\n\n"
        "```python\n"
        "def spread(best_ask, best_bid):\n"
        "    return best_ask - best_bid\n"
        "```\n\n"
        "The implementation pattern should cite the source chunk."
    )

    first = ParentChildChunker(parent_token_target=40, child_token_target=16).chunk(
        document_id="doc-1",
        text=text,
        section_title="Intro",
    )
    second = ParentChildChunker(parent_token_target=40, child_token_target=16).chunk(
        document_id="doc-1",
        text=text,
        section_title="Intro",
    )

    assert first.parent_chunks[0].chunk_hash == second.parent_chunks[0].chunk_hash
    assert first.child_chunks
    assert {child.parent_chunk_id for child in first.child_chunks} == {first.parent_chunks[0].id}
    assert "def spread" in first.parent_chunks[0].text


def test_formula_block_is_not_split_when_possible():
    text = "Method\n\n$$\nmid_t = (bid_t + ask_t) / 2\n$$\n\nThe formula defines the midpoint."

    result = ParentChildChunker(parent_token_target=20, child_token_target=8).chunk(
        document_id="doc-formula",
        text=text,
        section_title="Method",
    )

    combined = "\n".join(child.text for child in result.child_chunks)
    assert "$$\nmid_t = (bid_t + ask_t) / 2\n$$" in combined
