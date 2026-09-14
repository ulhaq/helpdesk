"""Text embeddings for semantic knowledge search.

`Embedder` is the seam: retrieval and the embedding worker only use this
protocol. Two implementations ship:

- `OpenAICompatibleEmbedder` - any server exposing OpenAI's `POST /embeddings`,
  e.g. a local model (such as Qwen3-Embedding) behind Ollama, vLLM, llama.cpp,
  LM Studio or Hugging Face TEI.
- `VoyageEmbedder` - Voyage AI's hosted embeddings.

Vectors live in `knowledge_chunk.embedding`, a pgvector column fixed at
`EMBEDDING_DIMENSIONS`: a model must return exactly that many dimensions.
Each chunk records the model that embedded it, so switching models re-embeds
everything in the background.

Semantic search is off while no provider is configured; retrieval then uses
full-text search alone.
"""

import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, Literal, Protocol

import httpx

from src.helpdesk.config import settings

log = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1024

# Retrieval models may embed questions and the passages answering them
# differently.
InputType = Literal["query", "document"]


class EmbeddingError(Exception):
    """The embedding provider failed or returned something unusable."""


class Embedder(Protocol):
    @property
    def model(self) -> str: ...

    async def embed(
        self, texts: Sequence[str], input_type: InputType
    ) -> list[list[float]]: ...


class OpenAICompatibleEmbedder:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        query_prefix: str = "",
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._query_prefix = query_prefix
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            transport=transport,
        )

    @property
    def model(self) -> str:
        return self._model

    async def embed(
        self, texts: Sequence[str], input_type: InputType
    ) -> list[list[float]]:
        if not texts:
            return []
        inputs = list(texts)
        if input_type == "query" and self._query_prefix:
            inputs = [f"{self._query_prefix}{text}" for text in inputs]
        return await _post(
            self._client,
            "/embeddings",
            {"input": inputs, "model": self._model},
            expected=len(inputs),
        )


class VoyageEmbedder:
    _URL = "https://api.voyageai.com/v1/embeddings"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    @property
    def model(self) -> str:
        return self._model

    async def embed(
        self, texts: Sequence[str], input_type: InputType
    ) -> list[list[float]]:
        if not texts:
            return []
        return await _post(
            self._client,
            self._URL,
            {
                "input": list(texts),
                "model": self._model,
                "input_type": input_type,
                "output_dimension": EMBEDDING_DIMENSIONS,
            },
            expected=len(texts),
        )


async def _post(
    client: httpx.AsyncClient, url: str, payload: dict[str, Any], *, expected: int
) -> list[list[float]]:
    """POST an OpenAI-style embeddings request; both providers answer with
    `{"data": [{"index": i, "embedding": [...]}, ...]}`."""
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        items = sorted(response.json()["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in items]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise EmbeddingError(f"Embedding request failed: {exc!r}") from exc
    return checked_vectors(vectors, expected=expected)


def checked_vectors(vectors: list[list[float]], *, expected: int) -> list[list[float]]:
    if len(vectors) != expected:
        raise EmbeddingError(f"Expected {expected} embeddings, got {len(vectors)}")
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingError(
                f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(vector)}"
            )
    return vectors


@lru_cache(maxsize=1)
def _configured_embedder() -> Embedder | None:
    provider = settings.embedding_provider
    if provider is None:
        return None
    if not settings.embedding_model:
        log.warning("HELPDESK_EMBEDDING_MODEL is empty; semantic search is off")
        return None
    key = settings.embedding_api_key
    api_key = key.get_secret_value() if key is not None else ""

    if provider == "voyage":
        if not api_key:
            log.warning("HELPDESK_EMBEDDING_API_KEY is empty; semantic search is off")
            return None
        return VoyageEmbedder(api_key, settings.embedding_model)

    if not settings.embedding_base_url:
        log.warning("HELPDESK_EMBEDDING_BASE_URL is empty; semantic search is off")
        return None
    return OpenAICompatibleEmbedder(
        settings.embedding_base_url,
        settings.embedding_model,
        api_key=api_key or None,
        query_prefix=settings.embedding_query_prefix,
    )


def get_embedder() -> Embedder | None:
    """The configured embedder, or None (full-text search only). Used as a
    FastAPI dependency - tests override it - and by the worker."""
    return _configured_embedder()
