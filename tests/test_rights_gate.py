from wzkf.rights.license_gate import RightsGate, SourceRecord, SourceStatus


def test_rights_gate_blocks_unlicensed_current_reuters():
    record = SourceRecord(
        source_key="lseg_current_news",
        source_type="news_dataset",
        title="LSEG Reuters Machine Readable News",
        homepage_url="https://www.lseg.com/en/data-analytics/financial-news-service/machine-readable-news",
        rights_policy="metadata_only_unless_licensed",
        license_configured=False,
    )

    decision = RightsGate().evaluate(record)

    assert decision.status == SourceStatus.METADATA_ONLY
    assert decision.full_text_allowed is False
    assert "license" in decision.reason.lower()


def test_youtube_only_source_abstains_without_authorization():
    record = SourceRecord(
        source_key="youtube_only_episode",
        source_type="podcast",
        title="YouTube Only Episode",
        homepage_url="https://www.youtube.com/watch?v=abc",
        rights_policy="blocked_without_authorization",
        authorized_transcript=False,
        authorized_audio=False,
    )

    decision = RightsGate().evaluate(record)

    assert decision.status == SourceStatus.ABSTAINED
    assert decision.full_text_allowed is False
    assert "youtube" in decision.reason.lower()


def test_official_transcript_source_is_allowed_for_private_research():
    record = SourceRecord(
        source_key="signals_threads",
        source_type="podcast",
        title="Signals and Threads",
        homepage_url="https://signalsandthreads.com/example",
        rights_policy="official_public_research_private",
        authorized_transcript=True,
    )

    decision = RightsGate().evaluate(record)

    assert decision.status == SourceStatus.ALLOWED
    assert decision.full_text_allowed is True
    assert decision.raw_export_allowed is False
