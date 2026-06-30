import json
from pathlib import Path

import pytest

from wzkf.harvesters import academic_metadata
from wzkf.storage.hashing import canonical_json_hash, sha256_text


class RecordingTransport:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def get_text(
        self,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> str:
        self.calls.append((url, params, headers))
        return self.response_text


def test_cached_academic_metadata_client_fetches_openalex_query_once(tmp_path: Path):
    client_cls = getattr(academic_metadata, "CachedAcademicMetadataClient", None)
    cache_cls = getattr(academic_metadata, "FileAcademicResponseCache", None)
    assert client_cls is not None
    assert cache_cls is not None

    transport = RecordingTransport(
        Path("tests/fixtures/academic_metadata/openalex_work.json").read_text(encoding="utf-8")
    )
    client = client_cls(
        provider="openalex",
        query_id="qfin_market_microstructure",
        cache=cache_cls(tmp_path / "academic-api-cache.json"),
        transport=transport,
        config={"api_key": "test-openalex-key"},
    )

    first = client.fetch_query("limit order book", limit=1)
    second = client.fetch_query("limit order book", limit=1)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(transport.calls) == 1
    assert transport.calls[0] == (
        "https://api.openalex.org/works",
        {"api_key": "test-openalex-key", "per-page": "1", "search": "limit order book"},
        {},
    )
    assert [record.title for record in second.records] == ["OpenAlex Limit Order Book Paper"]
    assert first.operation_key == canonical_json_hash(
        {
            "operation_name": "academic_metadata_fetch",
            "model_name": "openalex",
            "input_hash": sha256_text(
                json.dumps(
                    {
                        "params": {
                            "api_key": "test-openalex-key",
                            "per-page": "1",
                            "search": "limit order book",
                        },
                        "url": "https://api.openalex.org/works",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            "prompt_hash": sha256_text(""),
            "config_hash": canonical_json_hash({"api_key": "test-openalex-key"}),
        }
    )


def test_unpaywall_doi_lookup_requires_email_for_polite_api_use(tmp_path: Path):
    client_cls = getattr(academic_metadata, "CachedAcademicMetadataClient", None)
    cache_cls = getattr(academic_metadata, "FileAcademicResponseCache", None)
    error_cls = getattr(academic_metadata, "AcademicMetadataError")
    assert client_cls is not None
    assert cache_cls is not None

    client = client_cls(
        provider="unpaywall",
        query_id="qfin_market_microstructure",
        cache=cache_cls(tmp_path / "academic-api-cache.json"),
        transport=RecordingTransport("{}"),
    )

    with pytest.raises(error_cls, match="email"):
        client.fetch_doi("10.1234/openalex-lob")


def test_openalex_query_can_use_public_api_without_api_key(tmp_path: Path):
    client_cls = getattr(academic_metadata, "CachedAcademicMetadataClient", None)
    cache_cls = getattr(academic_metadata, "FileAcademicResponseCache", None)
    assert client_cls is not None
    assert cache_cls is not None

    transport = RecordingTransport(
        Path("tests/fixtures/academic_metadata/openalex_work.json").read_text(encoding="utf-8")
    )
    client = client_cls(
        provider="openalex",
        query_id="qfin_market_microstructure",
        cache=cache_cls(tmp_path / "academic-api-cache.json"),
        transport=transport,
    )

    result = client.fetch_query("limit order book", limit=1)

    assert result.cache_hit is False
    assert len(result.records) == 1
    assert transport.calls == [
        (
            "https://api.openalex.org/works",
            {"per-page": "1", "search": "limit order book"},
            {},
        )
    ]
