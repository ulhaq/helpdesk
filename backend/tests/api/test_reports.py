from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from src.helpdesk.models.ticket import Ticket
from tests.conftest import TestSessionLocal

_ADMIN_ID = 1
_MEMBER_ID = 2


@pytest.fixture(autouse=True)
def mock_ticket_email(mocker: Any) -> Any:
    return mocker.patch("src.helpdesk.services.ticket.send_email")


def _create(client: TestClient, subject: str) -> int:
    response = client.post(
        "/v1/tickets",
        json={
            "subject": subject,
            "body": "Help",
            "contact": {"name": "Jane", "email": "jane@example.org"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _set(ticket_id: int, **values: Any) -> None:
    async with TestSessionLocal() as session:
        await session.execute(
            update(Ticket).where(Ticket.id == ticket_id).values(**values)
        )
        await session.commit()


def _by_key(items: list[dict]) -> dict[str, int]:
    return {item["key"]: item["count"] for item in items}


async def test_report_summary(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    now = datetime.now(UTC)
    hour = timedelta(hours=1)

    resolved = _create(admin_authenticated, "Resolved last week")
    await _set(
        resolved,
        created_at=now - timedelta(days=2),
        first_response_at=now - timedelta(days=2) + hour,
        resolved_at=now - timedelta(days=2) + 5 * hour,
        status="resolved",
        priority="high",
        assignee_id=_ADMIN_ID,
    )
    pending = _create(admin_authenticated, "Waiting on customer")
    await _set(
        pending,
        created_at=now - timedelta(days=1),
        first_response_at=now - timedelta(days=1) + 3 * hour,
        status="pending",
        channel="widget",
        assignee_id=_MEMBER_ID,
    )
    old = _create(admin_authenticated, "Old backlog")
    await _set(old, created_at=now - timedelta(days=40))
    _create(admin_authenticated, "Fresh and unanswered")
    _create(organization2_admin_authenticated, "Another organization")

    response = admin_authenticated.get("/v1/reports/summary?days=30")
    assert response.status_code == 200, response.text
    rs = response.json()

    assert rs["period_days"] == 30
    assert rs["created"] == 3
    assert rs["resolved"] == 1
    assert rs["backlog"] == 3
    assert rs["unassigned_backlog"] == 2
    assert rs["first_response"] == {
        "median_seconds": 7200,
        "average_seconds": 7200,
        "sample_size": 2,
    }
    assert rs["resolution"]["median_seconds"] == 5 * 3600
    assert _by_key(rs["by_status"]) == {
        "open": 1,
        "pending": 1,
        "resolved": 1,
        "closed": 0,
    }
    assert _by_key(rs["by_channel"]) == {"agent": 2, "widget": 1}
    assert _by_key(rs["by_priority"])["high"] == 1

    assert len(rs["daily"]) == 30
    assert sum(day["created"] for day in rs["daily"]) == 3
    assert sum(day["resolved"] for day in rs["daily"]) == 1

    assert [(a["user_id"], a["open"], a["resolved"]) for a in rs["agents"]] == [
        (_MEMBER_ID, 1, 0),
        (_ADMIN_ID, 0, 1),
    ]


def test_empty_report(admin_authenticated: TestClient) -> None:
    rs = admin_authenticated.get("/v1/reports/summary?days=7").json()
    assert rs["created"] == 0
    assert rs["first_response"]["median_seconds"] is None
    assert len(rs["daily"]) == 7
    assert rs["agents"] == []


@pytest.mark.parametrize("days", [6, 366])
def test_report_period_is_bounded(admin_authenticated: TestClient, days: int) -> None:
    response = admin_authenticated.get(f"/v1/reports/summary?days={days}")
    assert response.status_code == 422


def test_reports_require_permission(standard_authenticated: TestClient) -> None:
    assert standard_authenticated.get("/v1/reports/summary").status_code == 403
