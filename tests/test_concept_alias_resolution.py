from wzkf.ontology.alias_resolver import AliasResolver, ConceptReviewStatus


def test_lob_aliases_resolve_to_one_canonical_concept():
    resolver = AliasResolver.with_default_seed()

    names = ["LOB", "Limit Order Book", "order book", "Market Depth", "order book dynamics"]
    resolved = [resolver.resolve(name).canonical_name for name in names]

    assert resolved == ["Limit Order Book"] * len(names)


def test_unknown_concept_goes_to_review_queue():
    resolver = AliasResolver.with_default_seed()

    result = resolver.resolve("queue-reactive fill model")

    assert result.status == ConceptReviewStatus.REVIEW_REQUIRED
    assert result.canonical_name == "queue-reactive fill model"
    assert result.confidence < 0.8
