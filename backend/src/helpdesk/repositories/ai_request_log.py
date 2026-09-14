from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.models.ai_request_log import AiRequestLog
from src.platform.core.exceptions import UnscopedQueryError
from src.platform.repositories.base import OrganizationScopedRepository

# Stored queries are capped; ticket conversations can be long.
_MAX_QUERY_CHARS = 1_000


class AiRequestLogRepository(OrganizationScopedRepository[AiRequestLog]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(AiRequestLog, db)

    async def record(
        self,
        *,
        organization_id: int,
        feature: str,
        query: str,
        retrieval_mode: str,
        chunk_ids: list[int],
        cited_article_ids: list[int],
        cited_document_ids: list[int],
        outcome: str,
    ) -> AiRequestLog:
        return await self.create(
            organization_id=organization_id,
            feature=feature,
            query=query[:_MAX_QUERY_CHARS],
            retrieval_mode=retrieval_mode,
            chunk_ids=chunk_ids,
            cited_article_ids=cited_article_ids,
            cited_document_ids=cited_document_ids,
            outcome=outcome,
        )

    async def delete_before(self, cutoff: datetime) -> int:
        """Delete logs created before `cutoff`; returns how many. Workers call
        this on `.unscoped` to sweep every organization."""
        stmt = delete(AiRequestLog).where(AiRequestLog.created_at < cutoff)
        if self._organization_id is not None:
            stmt = stmt.where(AiRequestLog.organization_id == self._organization_id)
        elif not self._allow_unscoped:
            raise UnscopedQueryError(
                "delete_before needs an organization scope or `.unscoped`."
            )
        rs = await self.db.execute(stmt.returning(AiRequestLog.id))
        return len(rs.all())
