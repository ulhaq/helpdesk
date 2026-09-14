"""Which knowledge base content reaches Claude. Claude is faked (see
test_assistant.py); these tests inspect the documents it was sent.

The SQLite test database uses the repository's portable substring search;
the PostgreSQL full-text query is exercised against a real database only.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.helpdesk.assistant import get_ai_client
from src.helpdesk.config import settings
from src.helpdesk.models.ai_request_log import AiRequestLog
from src.main import app
from tests.api.test_assistant import FakeClaude, cite, message, text
from tests.conftest import TestSessionLocal

SHIPPING = """Everything about getting your order.

## Delivery times

Orders ship within 2 business days. Express delivery arrives the next day.

## Returns

Send the parcel back within 30 days for a refund.
"""


@pytest.fixture
def claude() -> Iterator[FakeClaude]:
    fake = FakeClaude()
    app.dependency_overrides[get_ai_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_ai_client, None)


@pytest.fixture
def search_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Treat every help center as too large to send whole."""
    monkeypatch.setattr(settings, "ai_full_context_max_chars", 0)


@pytest.fixture(autouse=True)
def mock_ticket_email(mocker: Any) -> Any:
    return mocker.patch("src.helpdesk.services.ticket.send_email")


@pytest.fixture
def slug(admin_authenticated: TestClient) -> str:
    return admin_authenticated.get("/v1/helpdesk/support-site").json()["slug"]


def _article(
    client: TestClient, title: str, body: str, status: str = "published"
) -> dict:
    response = client.post(
        "/v1/kb/articles", json={"title": title, "body": body, "status": status}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _ask(client: TestClient, slug: str, question: str) -> dict:
    response = client.post(f"/v1/widget/{slug}/answers", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


def _documents(claude: FakeClaude) -> list[dict[str, Any]]:
    content = claude.requests[-1]["messages"][0]["content"]
    return [block for block in content if block["type"] == "document"]


async def _logs() -> list[AiRequestLog]:
    async with TestSessionLocal() as session:
        rs = await session.execute(select(AiRequestLog).order_by(AiRequestLog.id))
        return list(rs.scalars().all())


async def test_a_small_help_center_is_sent_whole(
    admin_authenticated: TestClient, slug: str, claude: FakeClaude
) -> None:
    _article(admin_authenticated, "Shipping", SHIPPING)
    _article(admin_authenticated, "Billing", "Invoices are sent monthly.")

    _ask(admin_authenticated, slug, "Do you sell boats?")

    documents = _documents(claude)
    assert [d["title"] for d in documents] == ["Billing", "Shipping"]
    assert documents[1]["source"]["data"] == f"Shipping\n\n{SHIPPING}"
    assert documents[-1]["cache_control"] == {"type": "ephemeral"}
    [entry] = await _logs()
    assert (entry.retrieval_mode, entry.chunk_ids) == ("full", [])


async def test_a_large_help_center_sends_only_matching_sections(
    admin_authenticated: TestClient, slug: str, claude: FakeClaude, search_mode: None
) -> None:
    shipping = _article(admin_authenticated, "Shipping", SHIPPING)
    _article(admin_authenticated, "Billing", "Invoices are sent monthly.")
    claude.response = message(
        text("Orders ship within 2 business days.", cite(0, "Orders ship"))
    )

    answer = _ask(admin_authenticated, slug, "How long does delivery take?")

    [document] = _documents(claude)
    assert document["title"] == "Shipping"
    assert document["source"]["data"] == (
        "Shipping > Delivery times\n\nOrders ship within 2 business days. "
        "Express delivery arrives the next day."
    )
    # Searched sections differ per request, so they aren't cached.
    assert "cache_control" not in document
    assert answer["answered"] is True
    assert answer["sources"][0]["slug"] == shipping["slug"]

    [entry] = await _logs()
    assert entry.feature == "widget_answer"
    assert entry.query == "How long does delivery take?"
    assert entry.retrieval_mode == "search"
    assert len(entry.chunk_ids) == 1
    assert entry.cited_article_ids == [shipping["id"]]
    assert entry.outcome == "grounded"


async def test_no_matching_section_skips_claude(
    admin_authenticated: TestClient, slug: str, claude: FakeClaude, search_mode: None
) -> None:
    _article(admin_authenticated, "Shipping", SHIPPING)

    answer = _ask(admin_authenticated, slug, "Do you sell boats?")

    assert answer == {"answered": False, "text": None, "sources": []}
    assert claude.requests == []
    [entry] = await _logs()
    assert (entry.outcome, entry.chunk_ids) == ("no_match", [])


def test_search_skips_drafts_deleted_articles_and_other_organizations(
    admin_authenticated: TestClient,
    organization2_admin_authenticated: TestClient,
    slug: str,
    claude: FakeClaude,
    search_mode: None,
) -> None:
    _article(admin_authenticated, "Drone delivery", "Delivery by drone.", "draft")
    removed = _article(admin_authenticated, "Horse delivery", "Delivery by horse.")
    assert admin_authenticated.delete(f"/v1/kb/articles/{removed['id']}").is_success
    _article(organization2_admin_authenticated, "Boat delivery", "Delivery by boat.")
    _article(admin_authenticated, "Shipping", SHIPPING)

    _ask(admin_authenticated, slug, "delivery")

    assert {d["title"] for d in _documents(claude)} == {"Shipping"}


def test_editing_an_article_reindexes_it(
    admin_authenticated: TestClient, slug: str, claude: FakeClaude, search_mode: None
) -> None:
    article = _article(admin_authenticated, "Shipping", "Orders travel by truck.")
    response = admin_authenticated.patch(
        f"/v1/kb/articles/{article['id']}", json={"body": "Orders travel by bicycle."}
    )
    assert response.status_code == 200, response.text

    _ask(admin_authenticated, slug, "truck")
    assert claude.requests == []

    _ask(admin_authenticated, slug, "bicycle")
    [document] = _documents(claude)
    assert document["source"]["data"] == "Shipping\n\nOrders travel by bicycle."


def test_retrieval_stays_within_the_passage_budget(
    admin_authenticated: TestClient,
    slug: str,
    claude: FakeClaude,
    search_mode: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_retrieval_max_passages", 2)
    for n in range(4):
        _article(admin_authenticated, f"Delivery option {n}", "Delivery details.")

    _ask(admin_authenticated, slug, "delivery")

    assert len(_documents(claude)) == 2


async def test_reply_drafts_search_with_the_ticket(
    admin_authenticated: TestClient, claude: FakeClaude, search_mode: None
) -> None:
    _article(admin_authenticated, "Reset your password", "Use the reset link.")
    _article(admin_authenticated, "Billing", "Invoices are sent monthly.")
    response = admin_authenticated.post(
        "/v1/tickets",
        json={
            "subject": "Cannot reset password",
            "body": "The link never arrives.",
            "contact": {"name": "Jane Customer", "email": "jane@example.org"},
        },
    )
    ticket = response.json()

    response = admin_authenticated.post(f"/v1/tickets/{ticket['id']}/reply-suggestion")
    assert response.status_code == 200, response.text

    assert [d["title"] for d in _documents(claude)] == ["Reset your password"]
    [entry] = await _logs()
    assert entry.feature == "reply_suggestion"
    assert entry.query == "Cannot reset password\nThe link never arrives."
    assert entry.outcome == "ungrounded"
