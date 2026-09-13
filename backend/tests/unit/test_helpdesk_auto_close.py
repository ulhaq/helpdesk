from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.helpdesk.models.contact import Contact
from src.helpdesk.models.ticket import Ticket
from src.helpdesk.worker import close_stale_resolved_tickets
from tests.conftest import TestSessionLocal


async def _ticket(
    session, organization_id: int, number: int, status: str, resolved_days_ago: int
) -> Ticket:
    contact = Contact(
        organization_id=organization_id, name="Jane", email=f"jane{number}@example.org"
    )
    session.add(contact)
    await session.flush()
    now = datetime.now(UTC)
    ticket = Ticket(
        organization_id=organization_id,
        number=number,
        subject="Help",
        status=status,
        channel="agent",
        contact_id=contact.id,
        last_message_at=now,
        resolved_at=now - timedelta(days=resolved_days_ago),
        created_at=now - timedelta(days=30),
        updated_at=now,
    )
    session.add(ticket)
    await session.flush()
    return ticket


async def test_closes_only_tickets_resolved_long_enough_ago() -> None:
    async with TestSessionLocal() as session:
        stale = await _ticket(session, 1, 1, "resolved", resolved_days_ago=10)
        other_org = await _ticket(session, 2, 1, "resolved", resolved_days_ago=8)
        recent = await _ticket(session, 1, 2, "resolved", resolved_days_ago=2)
        reopened = await _ticket(session, 1, 3, "open", resolved_days_ago=10)
        ids = {
            "stale": stale.id,
            "other_org": other_org.id,
            "recent": recent.id,
            "reopened": reopened.id,
        }
        await session.commit()

    async with TestSessionLocal() as session:
        closed = await close_stale_resolved_tickets(session, older_than_days=7)
        await session.commit()
    assert closed == 2

    async with TestSessionLocal() as session:
        rs = await session.execute(select(Ticket.id, Ticket.status))
        rows = rs.tuples().all()
    statuses = dict(rows)
    assert statuses[ids["stale"]] == "closed"
    assert statuses[ids["other_org"]] == "closed"
    assert statuses[ids["recent"]] == "resolved"
    assert statuses[ids["reopened"]] == "open"
