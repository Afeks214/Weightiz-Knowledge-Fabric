import pytest

from wzkf.retrieval.embeddings import EmbeddingProviderError, OpenAIEmbeddingProvider


class RecordingEmbeddingTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, headers, payload):
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        return self.response


def test_openai_embedding_provider_posts_authorized_embedding_request():
    transport = RecordingEmbeddingTransport(
        {"data": [{"embedding": [0.1, 0.2, 3]}], "model": "text-embedding-3-small"}
    )
    provider = OpenAIEmbeddingProvider(api_key="test-openai-key", transport=transport)

    embedding = provider.embed("Limit order book evidence.")

    assert embedding == [0.1, 0.2, 3.0]
    assert transport.calls == [
        {
            "url": "https://api.openai.com/v1/embeddings",
            "headers": {
                "Authorization": "Bearer test-openai-key",
                "Content-Type": "application/json",
            },
            "payload": {
                "model": "text-embedding-3-small",
                "input": "Limit order book evidence.",
            },
        }
    ]


def test_openai_embedding_provider_requires_api_key_without_transport_call():
    transport = RecordingEmbeddingTransport({"data": [{"embedding": [0.1]}]})
    provider = OpenAIEmbeddingProvider(api_key=None, transport=transport)

    with pytest.raises(EmbeddingProviderError, match="api_key"):
        provider.embed("No credential should call the network.")

    assert transport.calls == []


def test_openai_embedding_provider_rejects_malformed_response():
    provider = OpenAIEmbeddingProvider(
        api_key="test-openai-key",
        transport=RecordingEmbeddingTransport({"data": [{"not_embedding": []}]}),
    )

    with pytest.raises(EmbeddingProviderError, match="embedding"):
        provider.embed("Malformed provider payload.")
