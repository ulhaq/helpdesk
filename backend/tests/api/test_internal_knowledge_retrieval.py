"""Internal knowledge and semantic search in the AI assistant. Claude and the
embedding model are faked; these tests inspect what reaches Claude."""

import re
from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.helpdesk.assistant import get_ai_client
from src.helpdesk.config import settings
from src.helpdesk.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingError,
    InputType,
    get_embedder,
)
from src.helpdesk.models.ai_request_log import AiRequestLog
from src.helpdesk.models.knowledge import KnowledgeChunk
from src.helpdesk.worker import embed_pending_chunks
from src.main import app
from tests.api.test_assistant import FakeClaude, cite, message, text
from tests.conftest import TestSessionLocal

# Words with the same meaning share an axis, so the fake model behaves like a
# real one on paraphrases: "money back" lands next to "refund".
_CONCEPTS = {
    "refund": 0,
    "refunds": 0,
    "money": 0,
    "reimburse": 0,
    "delivery": 1,
    "parcels": 1,
    "escalate": 2,
    "manager": 2,
    "supervisor": 2,
}


class FakeEmbedder:
    def __init__(self) -> None:
        self.fail = False
        self.queries: list[str] = []

    @property
    def model(self) -> str:
        return "fake-embedding"

    async def embed(
        self, texts: Sequence[str], input_type: InputType
    ) -> list[list[float]]:
        if self.fail:
            raise EmbeddingError("model server is down")
        if input_type == "query":
            self.queries.extend(texts)
        return [self._vector(t) for t in texts]

    @staticmethod
    def _vector(value: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        vector[-1] = 0.05
        for word in re.findall(r"[a-z]+", value.lower()):
            if word in _CONCEPTS:
                vector[_CONCEPTS[word]] += 1.0
        return vector


@pytest.fixture
def claude() -> Iterator[FakeClaude]:
    fake = FakeClaude()
    app.dependency_overrides[get_ai_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_ai_client, None)


@pytest.fixture
def embedder() -> Iterator[FakeEmbedder]:
    fake = FakeEmbedder()
    app.dependency_overrides[get_embedder] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_embedder, None)


@pytest.fixture
def search_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_full_context_max_chars", 0)


@pytest.fixture(autouse=True)
def mock_ticket_email(mocker: Any) -> Any:
    return mocker.patch("src.helpdesk.services.ticket.send_email")


@pytest.fixture
def slug(admin_authenticated: TestClient) -> str:
    return admin_authenticated.get("/v1/helpdesk/support-site").json()["slug"]


def _article(client: TestClient, title: str, body: str) -> dict:
    response = client.post(
        "/v1/kb/articles", json={"title": title, "body": body, "status": "published"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _document(client: TestClient, title: str, body: str) -> dict:
    response = client.post(
        "/v1/knowledge/documents", json={"title": title, "text": body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _draft(client: TestClient, subject: str, body: str) -> dict:
    ticket = client.post(
        "/v1/tickets",
        json={
            "subject": subject,
            "body": body,
            "contact": {"name": "Jane Customer", "email": "jane@example.org"},
        },
    ).json()
    response = client.post(f"/v1/tickets/{ticket['id']}/reply-suggestion")
    assert response.status_code == 200, response.text
    return response.json()


def _ask(client: TestClient, slug: str, question: str) -> dict:
    response = client.post(f"/v1/widget/{slug}/answers", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


def _titles(claude: FakeClaude) -> list[str]:
    content = claude.requests[-1]["messages"][0]["content"]
    return [block["title"] for block in content if block["type"] == "document"]


async def _embed_everything(embedder: FakeEmbedder) -> None:
    await embed_pending_chunks(TestSessionLocal, embedder, batch_size=1000)


async def _last_log() -> AiRequestLog:
    async with TestSessionLocal() as session:
        rs = await session.execute(
            select(AiRequestLog).order_by(AiRequestLog.id.desc()).limit(1)
        )
        return rs.scalar_one()


async def test_reply_drafts_use_internal_documents(
    admin_authenticated: TestClient, claude: FakeClaude
) -> None:
    _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")
    document = _document(
        admin_authenticated, "VIP refunds", "VIP customers get refunds up to 60 days."
    )
    claude.response = message(
        text("As a VIP you can get a refund.", cite(1, "VIP customers get refunds"))
    )

    draft = _draft(admin_authenticated, "Refund after 45 days?", "I am a VIP.")

    assert _titles(claude) == ["Refund policy", "Internal: VIP refunds"]
    assert draft["sources"] == [
        {
            "source_type": "document",
            "title": "VIP refunds",
            "slug": None,
            "cited_text": "VIP customers get refunds",
        }
    ]
    entry = await _last_log()
    assert (entry.cited_article_ids, entry.cited_document_ids) == ([], [document["id"]])


@pytest.mark.parametrize("semantic_search", [False, True])
async def test_widget_answers_never_see_internal_documents(
    admin_authenticated: TestClient,
    slug: str,
    claude: FakeClaude,
    request: pytest.FixtureRequest,
    semantic_search: bool,
) -> None:
    # Without an embedder this small knowledge base is sent whole; with one it
    # is searched. Neither path may include internal documents.
    _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")
    _document(admin_authenticated, "VIP refunds", "VIP refunds within 60 days.")
    if semantic_search:
        await _embed_everything(request.getfixturevalue("embedder"))

    _ask(admin_authenticated, slug, "refunds")

    assert _titles(claude) == ["Refund policy"]
    expected_mode = "hybrid" if semantic_search else "full"
    assert (await _last_log()).retrieval_mode == expected_mode


async def test_with_an_embedder_a_small_knowledge_base_is_searched(
    admin_authenticated: TestClient,
    slug: str,
    claude: FakeClaude,
    embedder: FakeEmbedder,
) -> None:
    _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")
    _article(admin_authenticated, "Shipping", "Parcels ship in 2 days.")
    await _embed_everything(embedder)

    _ask(admin_authenticated, slug, "refund")

    assert _titles(claude) == ["Refund policy"]
    content = claude.requests[-1]["messages"][0]["content"]
    assert all("cache_control" not in block for block in content)
    assert (await _last_log()).retrieval_mode == "hybrid"


async def test_semantic_search_finds_paraphrases(
    admin_authenticated: TestClient,
    claude: FakeClaude,
    embedder: FakeEmbedder,
) -> None:
    _document(
        admin_authenticated,
        "Escalation process",
        "Escalate unresolved complaints to the duty manager.",
    )
    _article(admin_authenticated, "Shipping", "Parcels ship in 2 days.")
    await _embed_everything(embedder)

    _draft(
        admin_authenticated,
        "Customer demands a supervisor",
        "Please pass me to someone senior.",
    )

    # No keyword overlaps; only the meaning matches.
    assert _titles(claude) == ["Internal: Escalation process"]
    assert embedder.queries == [
        "Customer demands a supervisor\nPlease pass me to someone senior."
    ]
    assert (await _last_log()).retrieval_mode == "hybrid"


async def test_keyword_and_semantic_rankings_are_fused(
    admin_authenticated: TestClient,
    slug: str,
    claude: FakeClaude,
    embedder: FakeEmbedder,
) -> None:
    _article(admin_authenticated, "Shipping", "Parcels ship in 2 days.")
    _article(admin_authenticated, "Money back guarantee", "We reimburse you.")
    _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")
    await _embed_everything(embedder)

    _ask(admin_authenticated, slug, "refund")

    # Found by both rankings first, by meaning alone second, unrelated never.
    assert _titles(claude) == ["Refund policy", "Money back guarantee"]


async def test_embedding_failures_fall_back_to_full_text_search(
    admin_authenticated: TestClient,
    slug: str,
    claude: FakeClaude,
    embedder: FakeEmbedder,
) -> None:
    # A configured but failing model still searches - by keywords only - rather
    # than sending the whole knowledge base.
    _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")
    embedder.fail = True

    _ask(admin_authenticated, slug, "refund")

    assert _titles(claude) == ["Refund policy"]
    assert (await _last_log()).retrieval_mode == "search"


async def test_deleted_documents_leave_the_assistant_context(
    admin_authenticated: TestClient, claude: FakeClaude, search_mode: None
) -> None:
    document = _document(admin_authenticated, "VIP refunds", "VIP refunds: 60 days.")
    response = admin_authenticated.delete(f"/v1/knowledge/documents/{document['id']}")
    assert response.status_code == 204

    _draft(admin_authenticated, "VIP refunds", "How long do VIP refunds take?")

    assert _titles(claude) == []
    async with TestSessionLocal() as session:
        rs = await session.execute(
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document["id"])
        )
        assert rs.scalar_one() == 0


# --- knowledge search tester


def _search(client: TestClient, query: str, **extra: Any) -> dict:
    response = client.post("/v1/knowledge/search", json={"query": query, **extra})
    assert response.status_code == 200, response.text
    return response.json()


async def test_search_explains_the_ranking_without_calling_claude(
    admin_authenticated: TestClient, claude: FakeClaude, embedder: FakeEmbedder
) -> None:
    money = _document(admin_authenticated, "Money back guarantee", "We reimburse you.")
    refund = _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")
    _article(admin_authenticated, "Shipping", "Parcels ship in 2 days.")
    await _embed_everything(embedder)

    result = _search(admin_authenticated, "refund")

    assert claude.requests == []
    assert result["terms"] == ["refund"]
    assert result["semantic"] == "ok"
    assert result["sends_everything"] is False
    assert result["pending_embeddings"] == 0
    first, second = result["results"]
    assert (first["title"], first["source_type"], first["source_id"]) == (
        "Refund policy",
        "article",
        refund["id"],
    )
    assert (first["keyword_rank"], first["semantic_rank"]) == (1, 2)
    assert first["selected"] is True
    assert (second["title"], second["source_type"], second["slug"]) == (
        "Money back guarantee",
        "document",
        None,
    )
    assert second["source_id"] == money["id"]
    assert (second["keyword_rank"], second["semantic_rank"]) == (None, 1)
    assert second["distance"] < result["max_distance"]
    assert first["score"] > second["score"]


async def test_search_counts_pending_embeddings_and_can_exclude_internal(
    admin_authenticated: TestClient, embedder: FakeEmbedder
) -> None:
    _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")
    _document(admin_authenticated, "Refund exceptions", "VIP refunds: 60 days.")

    # Nothing embedded yet: found by keywords only.
    result = _search(admin_authenticated, "refunds", include_internal=False)

    assert result["pending_embeddings"] == 2
    [only] = result["results"]
    assert (only["title"], only["semantic_rank"]) == ("Refund policy", None)


def test_search_without_an_embedding_model(admin_authenticated: TestClient) -> None:
    _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")

    result = _search(admin_authenticated, "refund")

    assert (result["semantic"], result["pending_embeddings"]) == ("off", 0)
    # Without an embedder, a small knowledge base is still sent whole.
    assert result["sends_everything"] is True
    assert [r["keyword_rank"] for r in result["results"]] == [1]


def test_search_when_the_embedding_model_fails(
    admin_authenticated: TestClient, embedder: FakeEmbedder
) -> None:
    _article(admin_authenticated, "Refund policy", "Refunds within 30 days.")
    embedder.fail = True

    assert _search(admin_authenticated, "refund")["semantic"] == "unavailable"


def test_search_requires_the_knowledge_base_permission(
    no_roles_authenticated: TestClient,
) -> None:
    response = no_roles_authenticated.post(
        "/v1/knowledge/search", json={"query": "refund"}
    )
    assert response.status_code == 403
