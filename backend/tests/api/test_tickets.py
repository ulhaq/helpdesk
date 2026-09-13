from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.helpdesk.enums import HelpdeskUsageMetric
from src.helpdesk.hooks import unassign_tickets_of_removed_member
from src.platform.models.billing import PlanSetting
from src.platform.models.notification import Notification
from src.platform.repositories.repository_manager import RepositoryManager
from tests.conftest import TestSessionLocal

_FREE_PLAN_ID = 1  # seeded in conftest
_ADMIN_ID = 1  # admin@example.org, organization 1
_MEMBER_ID = 2  # standard@example.org, organization 1
_ORG2_ADMIN_ID = 4  # admin2@example.org, organization 2


@pytest.fixture(autouse=True)
def mock_ticket_email(mocker: Any) -> Any:
    return mocker.patch("src.helpdesk.services.ticket.send_email")


def _create(client: TestClient, **overrides: Any) -> dict:
    payload = {
        "subject": "Cannot log in",
        "body": "I get an error when I try to log in.",
        "contact": {"name": "Jane Customer", "email": "jane@example.org"},
    } | overrides
    response = client.post("/v1/tickets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _reply(client: TestClient, ticket_id: int, **payload: Any) -> Any:
    return client.post(f"/v1/tickets/{ticket_id}/messages", json=payload)


def test_create_a_ticket(admin_authenticated: TestClient) -> None:
    rs = _create(admin_authenticated, priority="high")

    assert rs["number"] == 1
    assert rs["subject"] == "Cannot log in"
    assert rs["status"] == "open"
    assert rs["priority"] == "high"
    assert rs["channel"] == "agent"
    assert rs["organization_id"] == 1
    assert rs["contact"]["email"] == "jane@example.org"
    assert rs["assignee"] is None
    assert rs["first_response_at"] is None
    assert len(rs["messages"]) == 1
    assert rs["messages"][0]["author_type"] == "agent"
    assert rs["messages"][0]["author_user_id"] == _ADMIN_ID
    assert rs["messages"][0]["body"] == "I get an error when I try to log in."


def test_ticket_numbers_are_sequential_per_organization(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    assert _create(admin_authenticated)["number"] == 1
    assert _create(admin_authenticated)["number"] == 2
    assert _create(organization2_admin_authenticated)["number"] == 1


def test_ticket_reuses_contact_with_same_email(
    admin_authenticated: TestClient,
) -> None:
    first = _create(admin_authenticated)
    second = _create(
        admin_authenticated,
        contact={"name": "Jane C.", "email": "JANE@example.org"},
    )

    assert first["contact"]["id"] == second["contact"]["id"]
    assert admin_authenticated.get("/v1/contacts").json()["total"] == 1


def test_ticket_for_existing_contact(admin_authenticated: TestClient) -> None:
    contact = admin_authenticated.post(
        "/v1/contacts", json={"name": "John", "email": "john@example.org"}
    ).json()

    rs = _create(admin_authenticated, contact=None, contact_id=contact["id"])
    assert rs["contact"]["id"] == contact["id"]


@pytest.mark.parametrize(
    "contact_fields",
    [
        {},
        {"contact_id": 1, "contact": {"name": "Jane", "email": "jane@example.org"}},
    ],
)
def test_ticket_requires_exactly_one_contact(
    admin_authenticated: TestClient, contact_fields: dict
) -> None:
    response = admin_authenticated.post(
        "/v1/tickets", json={"subject": "Help", "body": "Please"} | contact_fields
    )
    assert response.status_code == 422


def test_ticket_cannot_use_another_organizations_contact(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    other_contact = organization2_admin_authenticated.post(
        "/v1/contacts", json={"name": "Jane", "email": "jane@example.org"}
    ).json()

    response = admin_authenticated.post(
        "/v1/tickets",
        json={"subject": "Help", "body": "Please", "contact_id": other_contact["id"]},
    )
    assert response.status_code == 404


def test_list_and_filter_tickets(admin_authenticated: TestClient) -> None:
    _create(admin_authenticated, subject="Billing question")
    login = _create(admin_authenticated, subject="Login broken")
    admin_authenticated.patch(f"/v1/tickets/{login['id']}", json={"status": "resolved"})

    response = admin_authenticated.get("/v1/tickets?sort=-number")
    assert response.status_code == 200
    assert [t["number"] for t in response.json()["items"]] == [2, 1]

    response = admin_authenticated.get("/v1/tickets?status__eq=open")
    assert [t["subject"] for t in response.json()["items"]] == ["Billing question"]

    response = admin_authenticated.get("/v1/tickets?q=login")
    assert [t["subject"] for t in response.json()["items"]] == ["Login broken"]


def test_tickets_are_isolated_between_organizations(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    ticket = _create(admin_authenticated)

    client = organization2_admin_authenticated
    assert client.get(f"/v1/tickets/{ticket['id']}").status_code == 404
    assert _reply(client, ticket["id"], body="Hi").status_code == 404
    assert client.get("/v1/tickets").json()["total"] == 0


def test_public_reply_emails_contact_and_waits_on_customer(
    admin_authenticated: TestClient, mock_ticket_email: Any
) -> None:
    ticket = _create(admin_authenticated)

    response = _reply(admin_authenticated, ticket["id"], body="Try resetting it.")
    assert response.status_code == 201, response.text
    assert response.json()["author_type"] == "agent"
    assert response.json()["author_name"]
    assert response.json()["is_internal"] is False

    detail = admin_authenticated.get(f"/v1/tickets/{ticket['id']}").json()
    assert detail["status"] == "pending"
    assert detail["first_response_at"] is not None
    assert len(detail["messages"]) == 2

    mock_ticket_email.assert_called_once()
    kwargs = mock_ticket_email.call_args.kwargs
    assert kwargs["address"] == "jane@example.org"
    assert kwargs["email_template"] == "ticket-reply"
    assert kwargs["data"]["ticket_number"] == 1
    assert kwargs["data"]["message_body"] == "Try resetting it."


def test_internal_note_is_not_sent_to_contact(
    admin_authenticated: TestClient, mock_ticket_email: Any
) -> None:
    ticket = _create(admin_authenticated)

    response = _reply(
        admin_authenticated, ticket["id"], body="Probably SSO.", is_internal=True
    )
    assert response.status_code == 201
    assert response.json()["is_internal"] is True

    detail = admin_authenticated.get(f"/v1/tickets/{ticket['id']}").json()
    assert detail["status"] == "open"
    assert detail["first_response_at"] is None
    mock_ticket_email.assert_not_called()


def test_closed_ticket_only_accepts_internal_notes(
    admin_authenticated: TestClient,
) -> None:
    ticket = _create(admin_authenticated)
    admin_authenticated.patch(f"/v1/tickets/{ticket['id']}", json={"status": "closed"})

    response = _reply(admin_authenticated, ticket["id"], body="Hello?")
    assert response.status_code == 409
    assert response.json()["error_code"] == "ticket_closed"

    response = _reply(admin_authenticated, ticket["id"], body="Note", is_internal=True)
    assert response.status_code == 201


def test_status_changes_track_resolution(admin_authenticated: TestClient) -> None:
    ticket = _create(admin_authenticated)
    url = f"/v1/tickets/{ticket['id']}"

    rs = admin_authenticated.patch(url, json={"status": "resolved"}).json()
    assert rs["resolved_at"] is not None
    assert rs["closed_at"] is None

    rs = admin_authenticated.patch(url, json={"status": "closed"}).json()
    assert rs["resolved_at"] is not None
    assert rs["closed_at"] is not None

    rs = admin_authenticated.patch(url, json={"status": "open"}).json()
    assert rs["resolved_at"] is None
    assert rs["closed_at"] is None


def test_patch_ignores_explicit_nulls(admin_authenticated: TestClient) -> None:
    ticket = _create(admin_authenticated)

    response = admin_authenticated.patch(
        f"/v1/tickets/{ticket['id']}", json={"subject": None, "priority": "urgent"}
    )
    assert response.status_code == 200
    assert response.json()["subject"] == "Cannot log in"
    assert response.json()["priority"] == "urgent"


async def test_assign_a_ticket_notifies_assignee(
    admin_authenticated: TestClient,
) -> None:
    ticket = _create(admin_authenticated)

    response = admin_authenticated.put(
        f"/v1/tickets/{ticket['id']}/assignee", json={"assignee_id": _MEMBER_ID}
    )
    assert response.status_code == 200, response.text
    assert response.json()["assignee"]["id"] == _MEMBER_ID

    async with TestSessionLocal() as session:
        notifications = (
            (
                await session.execute(
                    select(Notification).where(Notification.user_id == _MEMBER_ID)
                )
            )
            .scalars()
            .all()
        )
    assert [n.type for n in notifications] == ["ticket_assigned"]
    assert notifications[0].payload["ticket_id"] == ticket["id"]

    response = admin_authenticated.put(
        f"/v1/tickets/{ticket['id']}/assignee", json={"assignee_id": None}
    )
    assert response.status_code == 200
    assert response.json()["assignee"] is None


def test_cannot_assign_to_non_member(admin_authenticated: TestClient) -> None:
    ticket = _create(admin_authenticated)

    response = admin_authenticated.put(
        f"/v1/tickets/{ticket['id']}/assignee", json={"assignee_id": _ORG2_ADMIN_ID}
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "assignee_not_member"

    response = admin_authenticated.post(
        "/v1/tickets",
        json={
            "subject": "Help",
            "body": "Please",
            "contact": {"name": "Jane", "email": "jane@example.org"},
            "assignee_id": _ORG2_ADMIN_ID,
        },
    )
    assert response.status_code == 422


async def test_removed_member_tickets_are_unassigned(
    admin_authenticated: TestClient,
) -> None:
    ticket = _create(admin_authenticated, assignee_id=_MEMBER_ID)
    assert ticket["assignee"]["id"] == _MEMBER_ID

    async with TestSessionLocal() as session:
        await unassign_tickets_of_removed_member(
            repos=RepositoryManager(session), organization_id=1, user_id=_MEMBER_ID
        )
        await session.commit()

    detail = admin_authenticated.get(f"/v1/tickets/{ticket['id']}").json()
    assert detail["assignee"] is None


def test_delete_a_ticket(admin_authenticated: TestClient) -> None:
    ticket = _create(admin_authenticated)

    assert admin_authenticated.delete(f"/v1/tickets/{ticket['id']}").status_code == 204
    assert admin_authenticated.get(f"/v1/tickets/{ticket['id']}").status_code == 404
    # Numbers of deleted tickets are never reused.
    assert _create(admin_authenticated)["number"] == 2


def test_tickets_require_permission(no_roles_authenticated: TestClient) -> None:
    assert no_roles_authenticated.get("/v1/tickets").status_code == 403
    response = no_roles_authenticated.post(
        "/v1/tickets",
        json={
            "subject": "Help",
            "body": "Please",
            "contact": {"name": "Jane", "email": "jane@example.org"},
        },
    )
    assert response.status_code == 403


def test_member_cannot_delete_tickets(standard_authenticated: TestClient) -> None:
    ticket = _create(standard_authenticated)

    response = standard_authenticated.delete(f"/v1/tickets/{ticket['id']}")
    assert response.status_code == 403


async def test_monthly_ticket_limit(admin_authenticated: TestClient) -> None:
    async with TestSessionLocal() as session:
        session.add(
            PlanSetting(
                plan_id=_FREE_PLAN_ID,
                key=HelpdeskUsageMetric.TICKETS_PER_MONTH,
                value=1,
            )
        )
        await session.commit()

    _create(admin_authenticated)
    response = admin_authenticated.post(
        "/v1/tickets",
        json={
            "subject": "Second",
            "body": "Over the limit",
            "contact": {"name": "Jane", "email": "jane@example.org"},
        },
    )
    assert response.status_code == 429
    assert response.json()["error_code"] == "limit_exceeded"
