from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.helpdesk.enums import HelpdeskUsageMetric
from src.platform.models.billing import PlanSetting
from src.platform.models.notification import Notification
from tests.conftest import TestSessionLocal

_FREE_PLAN_ID = 1  # seeded in conftest
_ADMIN_ID = 1  # Owner of organization 1 (all permissions)
_MEMBER_ID = 2  # Member of organization 1 (can reply to tickets)


@pytest.fixture(autouse=True)
def widget_email(mocker: Any) -> Any:
    return mocker.patch("src.helpdesk.services.widget.send_email")


@pytest.fixture(autouse=True)
def ticket_email(mocker: Any) -> Any:
    return mocker.patch("src.helpdesk.services.ticket.send_email")


@pytest.fixture
def slug(admin_authenticated: TestClient) -> str:
    response = admin_authenticated.get("/v1/helpdesk/support-site")
    assert response.status_code == 200, response.text
    return response.json()["slug"]


def _submit(client: TestClient, slug: str, **overrides: Any) -> dict:
    payload = {
        "name": "Jane Customer",
        "email": "jane@example.org",
        "subject": "Where is my order?",
        "body": "Order 1234 has not arrived.",
    } | overrides
    response = client.post(f"/v1/widget/{slug}/tickets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _as_contact(token: str) -> dict[str, str]:
    return {"X-Contact-Token": token}


def _emailed_token(mock_email: Any) -> str:
    url = mock_email.call_args.kwargs["data"]["conversation_url"]
    return parse_qs(urlparse(url).query)["token"][0]


async def _notifications(notification_type: str) -> list[Notification]:
    async with TestSessionLocal() as session:
        rs = await session.execute(
            select(Notification)
            .where(Notification.type == notification_type)
            .order_by(Notification.user_id)
        )
        return list(rs.scalars().all())


def test_widget_config(client: TestClient, slug: str) -> None:
    response = client.get(f"/v1/widget/{slug}")
    assert response.status_code == 200
    assert response.json() == {
        "organization_name": "Acme Corp",
        "brand_color": "#293e70",
        "greeting": None,
        "help_center_enabled": True,
    }


def test_unknown_support_site(client: TestClient) -> None:
    assert client.get("/v1/widget/no-such-site").status_code == 404
    response = client.post(
        "/v1/widget/no-such-site/tickets",
        json={
            "name": "Jane",
            "email": "jane@example.org",
            "subject": "Hi",
            "body": "Hello",
        },
    )
    assert response.status_code == 404


def test_disabled_widget_is_unavailable(
    admin_authenticated: TestClient, slug: str
) -> None:
    admin_authenticated.patch(
        "/v1/helpdesk/support-site", json={"widget_enabled": False}
    )
    assert admin_authenticated.get(f"/v1/widget/{slug}").status_code == 404


def test_customer_opens_a_ticket(
    admin_authenticated: TestClient, slug: str, widget_email: Any
) -> None:
    rs = _submit(admin_authenticated, slug)

    assert rs["access_token"]
    ticket = rs["ticket"]
    assert ticket["number"] == 1
    assert ticket["status"] == "open"
    assert [
        (m["author_type"], m["author_name"], m["body"]) for m in ticket["messages"]
    ] == [("contact", "Jane Customer", "Order 1234 has not arrived.")]

    widget_email.assert_called_once()
    kwargs = widget_email.call_args.kwargs
    assert kwargs["address"] == "jane@example.org"
    assert kwargs["email_template"] == "ticket-received"
    assert f"/widget/{slug}?token=" in kwargs["data"]["conversation_url"]

    agent_view = admin_authenticated.get(f"/v1/tickets/{ticket['id']}").json()
    assert agent_view["channel"] == "widget"
    assert agent_view["contact"]["email"] == "jane@example.org"


async def test_new_widget_ticket_notifies_agents(client: TestClient, slug: str) -> None:
    _submit(client, slug)

    notifications = await _notifications("ticket_created")
    # Everyone in the organization who can reply; not the member without roles.
    assert [n.user_id for n in notifications] == [_ADMIN_ID, _MEMBER_ID]
    assert notifications[0].payload["contact_name"] == "Jane Customer"


def test_submitted_token_opens_only_that_ticket(client: TestClient, slug: str) -> None:
    older = _submit(client, slug, subject="Older question")
    newer = _submit(client, slug, subject="New question")
    token = newer["access_token"]

    response = client.get(
        f"/v1/widget/{slug}/tickets/{newer['ticket']['id']}", headers=_as_contact(token)
    )
    assert response.status_code == 200

    # Anyone can type an email address into the widget, so the token handed to
    # the browser must not reveal the contact's other conversations.
    response = client.get(
        f"/v1/widget/{slug}/tickets/{older['ticket']['id']}", headers=_as_contact(token)
    )
    assert response.status_code == 404

    listing = client.get(f"/v1/widget/{slug}/tickets", headers=_as_contact(token))
    assert [t["subject"] for t in listing.json()["tickets"]] == ["New question"]


def test_emailed_link_opens_all_conversations(
    client: TestClient, slug: str, widget_email: Any
) -> None:
    _submit(client, slug, subject="First")
    _submit(client, slug, subject="Second")
    token = _emailed_token(widget_email)

    response = client.get(f"/v1/widget/{slug}/tickets", headers=_as_contact(token))
    assert response.status_code == 200
    assert response.json()["contact_name"] == "Jane Customer"
    assert [t["subject"] for t in response.json()["tickets"]] == ["Second", "First"]


def test_access_link_is_only_sent_to_known_contacts(
    client: TestClient, slug: str, widget_email: Any
) -> None:
    response = client.post(
        f"/v1/widget/{slug}/access-link", json={"email": "stranger@example.org"}
    )
    assert response.status_code == 202
    widget_email.assert_not_called()

    _submit(client, slug)
    widget_email.reset_mock()

    response = client.post(
        f"/v1/widget/{slug}/access-link", json={"email": "jane@example.org"}
    )
    assert response.status_code == 202
    widget_email.assert_called_once()
    assert widget_email.call_args.kwargs["email_template"] == "ticket-access"
    token = _emailed_token(widget_email)
    listing = client.get(f"/v1/widget/{slug}/tickets", headers=_as_contact(token))
    assert len(listing.json()["tickets"]) == 1


def test_internal_notes_are_hidden_from_customers(
    admin_authenticated: TestClient, slug: str
) -> None:
    rs = _submit(admin_authenticated, slug)
    ticket_id = rs["ticket"]["id"]
    admin_authenticated.post(
        f"/v1/tickets/{ticket_id}/messages",
        json={"body": "Customer seems upset", "is_internal": True},
    )
    admin_authenticated.post(
        f"/v1/tickets/{ticket_id}/messages", json={"body": "It ships tomorrow."}
    )

    response = admin_authenticated.get(
        f"/v1/widget/{slug}/tickets/{ticket_id}",
        headers=_as_contact(rs["access_token"]),
    )
    assert [m["body"] for m in response.json()["messages"]] == [
        "Order 1234 has not arrived.",
        "It ships tomorrow.",
    ]


def test_agent_reply_email_links_to_the_conversation(
    admin_authenticated: TestClient, slug: str, ticket_email: Any
) -> None:
    rs = _submit(admin_authenticated, slug)
    admin_authenticated.post(
        f"/v1/tickets/{rs['ticket']['id']}/messages", json={"body": "On its way."}
    )

    token = _emailed_token(ticket_email)
    assert (
        f"/widget/{slug}?token="
        in (ticket_email.call_args.kwargs["data"]["conversation_url"])
    )
    response = admin_authenticated.get(
        f"/v1/widget/{slug}/tickets", headers=_as_contact(token)
    )
    assert len(response.json()["tickets"]) == 1


async def test_customer_reply_reopens_ticket_and_notifies_assignee(
    admin_authenticated: TestClient, slug: str
) -> None:
    rs = _submit(admin_authenticated, slug)
    ticket_id = rs["ticket"]["id"]
    admin_authenticated.put(
        f"/v1/tickets/{ticket_id}/assignee", json={"assignee_id": _MEMBER_ID}
    )
    admin_authenticated.post(
        f"/v1/tickets/{ticket_id}/messages", json={"body": "Can you check again?"}
    )
    assert admin_authenticated.get(f"/v1/tickets/{ticket_id}").json()["status"] == (
        "pending"
    )

    response = admin_authenticated.post(
        f"/v1/widget/{slug}/tickets/{ticket_id}/messages",
        json={"body": "Still nothing."},
        headers=_as_contact(rs["access_token"]),
    )
    assert response.status_code == 201, response.text
    assert response.json()["author_type"] == "contact"
    assert response.json()["author_name"] == "Jane Customer"

    detail = admin_authenticated.get(f"/v1/tickets/{ticket_id}").json()
    assert detail["status"] == "open"
    assert detail["messages"][-1]["body"] == "Still nothing."

    notifications = await _notifications("ticket_customer_replied")
    assert [n.user_id for n in notifications] == [_MEMBER_ID]


def test_customer_cannot_reply_to_closed_ticket(
    admin_authenticated: TestClient, slug: str
) -> None:
    rs = _submit(admin_authenticated, slug)
    ticket_id = rs["ticket"]["id"]
    admin_authenticated.patch(f"/v1/tickets/{ticket_id}", json={"status": "closed"})

    response = admin_authenticated.post(
        f"/v1/widget/{slug}/tickets/{ticket_id}/messages",
        json={"body": "Hello?"},
        headers=_as_contact(rs["access_token"]),
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "ticket_closed"


def test_invalid_or_missing_token_is_rejected(client: TestClient, slug: str) -> None:
    assert client.get(f"/v1/widget/{slug}/tickets").status_code == 401
    response = client.get(
        f"/v1/widget/{slug}/tickets", headers=_as_contact("not-a-token")
    )
    assert response.status_code == 401


def test_token_is_bound_to_its_organization(
    slug: str, organization2_admin_authenticated: TestClient
) -> None:
    client = organization2_admin_authenticated
    other_slug = client.get("/v1/helpdesk/support-site").json()["slug"]
    rs = _submit(client, other_slug)

    response = client.get(
        f"/v1/widget/{slug}/tickets", headers=_as_contact(rs["access_token"])
    )
    assert response.status_code == 401


def test_deleted_contact_loses_access(
    admin_authenticated: TestClient, slug: str
) -> None:
    rs = _submit(admin_authenticated, slug)
    contact_id = admin_authenticated.get(f"/v1/tickets/{rs['ticket']['id']}").json()[
        "contact"
    ]["id"]
    admin_authenticated.delete(f"/v1/contacts/{contact_id}")

    response = admin_authenticated.get(
        f"/v1/widget/{slug}/tickets", headers=_as_contact(rs["access_token"])
    )
    assert response.status_code == 401


async def test_widget_respects_monthly_ticket_limit(
    client: TestClient, slug: str
) -> None:
    async with TestSessionLocal() as session:
        session.add(
            PlanSetting(
                plan_id=_FREE_PLAN_ID,
                key=HelpdeskUsageMetric.TICKETS_PER_MONTH,
                value=1,
            )
        )
        await session.commit()

    _submit(client, slug)
    response = client.post(
        f"/v1/widget/{slug}/tickets",
        json={
            "name": "Jane",
            "email": "jane@example.org",
            "subject": "Again",
            "body": "Over the limit",
        },
    )
    assert response.status_code == 429
