from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from wzkf.storage.hashing import sha256_text


OPENAI_EMBEDDINGS_ENDPOINT = "https://api.openai.com/v1/embeddings"


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider cannot produce evidence-safe vectors."""


class EmbeddingHttpTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> dict[str, Any]:
        pass


class UrllibEmbeddingHttpTransport:
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise EmbeddingProviderError(
                f"embedding provider request failed with HTTP {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise EmbeddingProviderError("embedding provider request failed") from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise EmbeddingProviderError("embedding provider returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise EmbeddingProviderError("embedding provider returned non-object JSON")
        return parsed


class MockEmbeddingProvider:
    model_name = "mock-hash-embedding-v1"

    def embed(self, text: str) -> list[float]:
        digest = sha256_text(text)
        return [int(digest[index : index + 2], 16) / 255 for index in range(0, 16, 2)]


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        api_key: str | None,
        model_name: str = "text-embedding-3-small",
        transport: EmbeddingHttpTransport | None = None,
        endpoint: str = OPENAI_EMBEDDINGS_ENDPOINT,
    ):
        self.api_key = api_key.strip() if api_key else None
        self.model_name = model_name
        self.transport = transport or UrllibEmbeddingHttpTransport()
        self.endpoint = endpoint

    def embed(self, text: str) -> list[float]:
        if not self.api_key:
            raise EmbeddingProviderError("openai embedding provider requires api_key")
        response = self.transport.post_json(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload={"model": self.model_name, "input": text},
        )
        return _parse_openai_embedding_response(response)


def _parse_openai_embedding_response(response: dict[str, Any]) -> list[float]:
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise EmbeddingProviderError("embedding provider response missing data")
    first = data[0]
    if not isinstance(first, dict):
        raise EmbeddingProviderError("embedding provider response missing embedding object")
    embedding = first.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise EmbeddingProviderError("embedding provider response missing embedding")
    try:
        return [float(value) for value in embedding]
    except (TypeError, ValueError) as exc:
        raise EmbeddingProviderError("embedding provider returned non-numeric embedding") from exc
