from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.helpdesk.models.ai_request_log import AiRequestLog
from src.helpdesk.worker import purge_ai_request_logs
from tests.conftest import TestSessionLocal


async def test_purges_logs_older_than_the_retention_period() -> None:
    now = datetime.now(UTC)
    async with TestSessionLocal() as session:
        for organization_id, days_ago, query in [
            (1, 100, "old"),
            (2, 95, "old, other organization"),
            (1, 10, "recent"),
        ]:
            session.add(
                AiRequestLog(
                    organization_id=organization_id,
                    feature="widget_answer",
                    query=query,
                    retrieval_mode="full",
                    chunk_ids=[],
                    cited_article_ids=[],
                    outcome="no_match",
                    created_at=now - timedelta(days=days_ago),
                    updated_at=now,
                )
            )
        await session.commit()

    async with TestSessionLocal() as session:
        deleted = await purge_ai_request_logs(session, older_than_days=90)
        await session.commit()
    assert deleted == 2

    async with TestSessionLocal() as session:
        rs = await session.execute(select(AiRequestLog.query))
        assert rs.scalars().all() == ["recent"]
