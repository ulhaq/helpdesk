import json

import httpx
import pytest

from src.helpdesk.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingError,
    OpenAICompatibleEmbedder,
    VoyageEmbedder,
)


def _vectors_handler(requests: list[httpx.Request], dimensions: int):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        inputs = json.loads(request.content)["input"]
        # Returned out of order: the embedder must sort by index.
        data = [
            {"index": i, "embedding": [float(i)] * dimensions}
            for i in reversed(range(len(inputs)))
        ]
        return httpx.Response(200, json={"data": data})

    return handler


async def test_openai_compatible_embedder() -> None:
    requests: list[httpx.Request] = []
    embedder = OpenAICompatibleEmbedder(
        "http://models.local/v1/",
        "qwen3-embedding",
        api_key="secret",
        query_prefix="Query: ",
        transport=httpx.MockTransport(_vectors_handler(requests, EMBEDDING_DIMENSIONS)),
    )

    vectors = await embedder.embed(["first", "second"], "document")
    await embedder.embed(["refund?"], "query")

    assert [vector[0] for vector in vectors] == [0.0, 1.0]
    document_request, query_request = requests
    assert str(document_request.url) == "http://models.local/v1/embeddings"
    assert document_request.headers["Authorization"] == "Bearer secret"
    assert json.loads(document_request.content) == {
        "input": ["first", "second"],
        "model": "qwen3-embedding",
    }
    # Only queries get the instruction prefix.
    assert json.loads(query_request.content)["input"] == ["Query: refund?"]


async def test_voyage_embedder() -> None:
    requests: list[httpx.Request] = []
    embedder = VoyageEmbedder(
        "secret",
        "voyage-3.5",
        transport=httpx.MockTransport(_vectors_handler(requests, EMBEDDING_DIMENSIONS)),
    )

    await embedder.embed(["refund?"], "query")

    [request] = requests
    assert str(request.url) == "https://api.voyageai.com/v1/embeddings"
    assert json.loads(request.content) == {
        "input": ["refund?"],
        "model": "voyage-3.5",
        "input_type": "query",
        "output_dimension": EMBEDDING_DIMENSIONS,
    }


async def test_a_model_with_other_dimensions_is_rejected() -> None:
    embedder = OpenAICompatibleEmbedder(
        "http://models.local/v1",
        "small-model",
        transport=httpx.MockTransport(_vectors_handler([], 384)),
    )
    with pytest.raises(EmbeddingError, match="1024 dimensions"):
        await embedder.embed(["text"], "document")


async def test_server_errors_raise_embedding_errors() -> None:
    embedder = OpenAICompatibleEmbedder(
        "http://models.local/v1",
        "qwen3-embedding",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    with pytest.raises(EmbeddingError):
        await embedder.embed(["text"], "document")
    assert await embedder.embed([], "document") == []
