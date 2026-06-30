from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from wzkf.storage.hashing import canonical_json_hash, sha256_text


class AcademicMetadataError(ValueError):
    pass


@dataclass(frozen=True)
class HarvestedAcademicRecord:
    source_key: str
    provider: str
    query_id: str
    external_id: str
    doi: str | None
    title: str
    abstract: str
    authors: list[str]
    source_url: str
    landing_page_url: str | None
    pdf_url: str | None
    license_status: str
    is_open_access: bool


@dataclass(frozen=True)
class AcademicFetchResult:
    records: list[HarvestedAcademicRecord]
    operation_key: str
    cache_hit: bool


class AcademicHttpTransport(Protocol):
    def get_text(
        self,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> str:
        pass


class UrllibAcademicHttpTransport:
    def get_text(
        self,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> str:
        query = urlencode(params)
        request_url = f"{url}?{query}" if query else url
        request = Request(request_url, headers=headers)
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")


class FileAcademicResponseCache:
    def __init__(self, path: Path):
        self.path = Path(path)

    def get(self, operation_key: str) -> str | None:
        return self._load()["responses"].get(operation_key)

    def put(self, operation_key: str, response_text: str) -> None:
        manifest = self._load()
        manifest["responses"][operation_key] = response_text
        self._write(manifest)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "responses": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, manifest: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")


class CachedAcademicMetadataClient:
    def __init__(
        self,
        provider: str,
        query_id: str,
        cache: FileAcademicResponseCache,
        transport: AcademicHttpTransport | None = None,
        config: dict[str, str] | None = None,
    ):
        self.provider = provider
        self.query_id = query_id
        self.cache = cache
        self.transport = transport or UrllibAcademicHttpTransport()
        self.config = config or {}

    def fetch_query(self, query: str, limit: int = 25) -> AcademicFetchResult:
        url, params, headers = _query_request(self.provider, query, limit, self.config)
        return self._fetch(url, params, headers)

    def fetch_doi(self, doi: str) -> AcademicFetchResult:
        if self.provider != "unpaywall":
            raise AcademicMetadataError(f"{self.provider} DOI lookup is not supported")
        email = self.config.get("email") or self.config.get("mailto")
        if not email:
            raise AcademicMetadataError("unpaywall DOI lookup requires an email")
        url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}"
        return self._fetch(url, {"email": email}, {})

    def _fetch(
        self,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> AcademicFetchResult:
        operation_key = _operation_key(
            provider=self.provider,
            url=url,
            params=params,
            config=self.config,
        )
        cached = self.cache.get(operation_key)
        if cached is not None:
            return AcademicFetchResult(
                records=AcademicMetadataHarvester(
                    provider=self.provider,
                    query_id=self.query_id,
                ).parse(cached),
                operation_key=operation_key,
                cache_hit=True,
            )
        response_text = self.transport.get_text(url, params, headers)
        self.cache.put(operation_key, response_text)
        return AcademicFetchResult(
            records=AcademicMetadataHarvester(
                provider=self.provider,
                query_id=self.query_id,
            ).parse(response_text),
            operation_key=operation_key,
            cache_hit=False,
        )


class AcademicMetadataHarvester:
    def __init__(self, provider: str, query_id: str):
        self.provider = provider
        self.query_id = query_id

    def parse(self, metadata_json: str) -> list[HarvestedAcademicRecord]:
        payload = json.loads(metadata_json)
        if self.provider == "openalex":
            return [_openalex_record(item, self.query_id) for item in payload.get("results", [])]
        if self.provider == "crossref":
            items = payload.get("message", {}).get("items", [])
            return [_crossref_record(item, self.query_id) for item in items]
        if self.provider == "unpaywall":
            return [_unpaywall_record(payload, self.query_id)]
        if self.provider == "core":
            return [_core_record(item, self.query_id) for item in payload.get("results", [])]
        raise AcademicMetadataError(f"unsupported academic metadata provider: {self.provider}")


def _query_request(
    provider: str,
    query: str,
    limit: int,
    config: dict[str, str],
) -> tuple[str, dict[str, str], dict[str, str]]:
    if provider == "openalex":
        params = {"per-page": str(limit), "search": query}
        if config.get("api_key"):
            params = {"api_key": config["api_key"], **params}
        elif config.get("email") or config.get("mailto"):
            params["mailto"] = config.get("email") or config.get("mailto") or ""
        return "https://api.openalex.org/works", params, {}
    if provider == "crossref":
        return "https://api.crossref.org/works", {"query": query, "rows": str(limit)}, {}
    if provider == "core":
        headers = {}
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config['api_key']}"
        return "https://api.core.ac.uk/v3/search/works", {"limit": str(limit), "q": query}, headers
    raise AcademicMetadataError(f"{provider} query fetch is not supported")


def _operation_key(
    provider: str,
    url: str,
    params: dict[str, str],
    config: dict[str, str],
) -> str:
    request_payload = json.dumps(
        {"params": params, "url": url},
        sort_keys=True,
        separators=(",", ":"),
    )
    return canonical_json_hash(
        {
            "operation_name": "academic_metadata_fetch",
            "model_name": provider,
            "input_hash": sha256_text(request_payload),
            "prompt_hash": sha256_text(""),
            "config_hash": canonical_json_hash(config),
        }
    )


def _openalex_record(item: dict[str, Any], query_id: str) -> HarvestedAcademicRecord:
    primary_location = item.get("primary_location") or {}
    open_access = item.get("open_access") or {}
    pdf_url = _text_or_none(primary_location.get("pdf_url"))
    is_open_access = bool(open_access.get("is_oa"))
    return HarvestedAcademicRecord(
        source_key=f"openalex:{query_id}",
        provider="openalex",
        query_id=query_id,
        external_id=_required_text(item, "id"),
        doi=_normalize_doi(item.get("doi")),
        title=_required_text(item, "title"),
        abstract=_abstract_from_openalex(item.get("abstract_inverted_index") or {}),
        authors=[
            _required_text(authorship.get("author", {}), "display_name")
            for authorship in item.get("authorships", [])
            if authorship.get("author", {}).get("display_name")
        ],
        source_url=_required_text(item, "id"),
        landing_page_url=_text_or_none(primary_location.get("landing_page_url"))
        or _text_or_none(open_access.get("oa_url")),
        pdf_url=pdf_url if is_open_access else None,
        license_status=_license_status(is_open_access=is_open_access, pdf_url=pdf_url),
        is_open_access=is_open_access,
    )


def _crossref_record(item: dict[str, Any], query_id: str) -> HarvestedAcademicRecord:
    doi = _normalize_doi(item.get("DOI"))
    title = _first_text(item.get("title")) or "Untitled Crossref Work"
    return HarvestedAcademicRecord(
        source_key=f"crossref:{query_id}",
        provider="crossref",
        query_id=query_id,
        external_id=doi or _required_text(item, "URL"),
        doi=doi,
        title=title,
        abstract=_strip_markup(_text_or_none(item.get("abstract")) or ""),
        authors=[
            _person_name(author)
            for author in item.get("author", [])
            if _person_name(author)
        ],
        source_url=_text_or_none(item.get("URL")) or _doi_url(doi),
        landing_page_url=_text_or_none(item.get("URL")) or _doi_url(doi),
        pdf_url=None,
        license_status="metadata_only",
        is_open_access=False,
    )


def _unpaywall_record(item: dict[str, Any], query_id: str) -> HarvestedAcademicRecord:
    location = item.get("best_oa_location") or {}
    pdf_url = _text_or_none(location.get("url_for_pdf"))
    is_open_access = bool(item.get("is_oa"))
    doi = _normalize_doi(item.get("doi"))
    return HarvestedAcademicRecord(
        source_key=f"unpaywall:{query_id}",
        provider="unpaywall",
        query_id=query_id,
        external_id=doi or _required_text(item, "title"),
        doi=doi,
        title=_required_text(item, "title"),
        abstract=_text_or_none(item.get("abstract")) or "",
        authors=[
            _person_name(author)
            for author in item.get("z_authors", [])
            if _person_name(author)
        ],
        source_url=_doi_url(doi) or _text_or_none(location.get("url")) or "",
        landing_page_url=_text_or_none(location.get("url")) or _doi_url(doi),
        pdf_url=pdf_url if is_open_access else None,
        license_status=_license_status(is_open_access=is_open_access, pdf_url=pdf_url),
        is_open_access=is_open_access,
    )


def _core_record(item: dict[str, Any], query_id: str) -> HarvestedAcademicRecord:
    pdf_url = _text_or_none(item.get("downloadUrl"))
    doi = _normalize_doi(item.get("doi"))
    landing = _first_text(item.get("sourceFulltextUrls")) or pdf_url
    return HarvestedAcademicRecord(
        source_key=f"core:{query_id}",
        provider="core",
        query_id=query_id,
        external_id=str(item.get("id") or doi or _required_text(item, "title")),
        doi=doi,
        title=_required_text(item, "title"),
        abstract=_text_or_none(item.get("abstract")) or "",
        authors=[
            _core_author(author)
            for author in item.get("authors", [])
            if _core_author(author)
        ],
        source_url=landing or _doi_url(doi) or "",
        landing_page_url=landing,
        pdf_url=pdf_url,
        license_status=_license_status(is_open_access=bool(pdf_url), pdf_url=pdf_url),
        is_open_access=bool(pdf_url),
    )


def _abstract_from_openalex(inverted: dict[str, list[int]]) -> str:
    words_by_position: dict[int, str] = {}
    for word, positions in inverted.items():
        for position in positions:
            words_by_position[int(position)] = word
    return " ".join(words_by_position[position] for position in sorted(words_by_position))


def _license_status(is_open_access: bool, pdf_url: str | None) -> str:
    if is_open_access and pdf_url:
        return "open_access_pdf_allowed"
    return "metadata_only"


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = _text_or_none(payload.get(key))
    if value is None:
        raise AcademicMetadataError(f"academic metadata record missing {key}")
    return value


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    stripped = " ".join(value.split())
    return stripped or None


def _first_text(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return _text_or_none(value[0])
    return _text_or_none(value)


def _normalize_doi(value: Any) -> str | None:
    text = _text_or_none(value)
    if text is None:
        return None
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.IGNORECASE).casefold()


def _doi_url(doi: str | None) -> str | None:
    if not doi:
        return None
    return f"https://doi.org/{doi}"


def _strip_markup(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(without_tags.split())


def _person_name(author: dict[str, Any]) -> str:
    raw = _text_or_none(author.get("raw_author_name"))
    if raw:
        return raw
    given = _text_or_none(author.get("given"))
    family = _text_or_none(author.get("family"))
    return " ".join(part for part in [given, family] if part)


def _core_author(author: Any) -> str:
    if isinstance(author, dict):
        return _text_or_none(author.get("name")) or ""
    return _text_or_none(author) or ""
