from collections.abc import Sequence
from typing import ClassVar, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.enums import ArticleStatus
from src.helpdesk.models.kb import KbArticle, KbCategory
from src.platform.repositories.base import OrganizationScopedRepository


class KbCategoryRepository(OrganizationScopedRepository[KbCategory]):
    search_fields: ClassVar[list[str]] = ["name"]

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(KbCategory, db)

    async def get_by_slug(self, slug: str) -> KbCategory | None:
        return await self._get_by_field("slug", slug)

    async def list_ordered(self) -> Sequence[KbCategory]:
        stmt = select(KbCategory)
        stmt = self._apply_organization_scope(stmt)
        stmt = self._include_deleted(stmt)
        stmt = stmt.order_by(KbCategory.position, KbCategory.name)
        rs = await self.db.execute(stmt)
        return rs.scalars().all()


class KbArticleRepository(OrganizationScopedRepository[KbArticle]):
    search_fields: ClassVar[list[str]] = ["title", "body"]

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(KbArticle, db)

    async def get_by_slug(self, slug: str) -> KbArticle | None:
        return await self._get_by_field("slug", slug)

    async def count(self) -> int:
        """Active articles in the current scope, drafts included."""
        stmt = select(func.count()).select_from(KbArticle)
        stmt = self._apply_organization_scope(stmt)
        stmt = self._include_deleted(stmt)
        rs = await self.db.execute(stmt)
        return int(rs.scalar_one())

    async def detach_category(self, category_id: int) -> None:
        for article in await self.filter_by(category_id=category_id):
            article.category_id = None
        await self.save()

    async def published_counts_by_category(self) -> dict[int, int]:
        stmt = (
            select(KbArticle.category_id, func.count())
            .where(
                KbArticle.status == ArticleStatus.PUBLISHED,
                KbArticle.category_id.is_not(None),
            )
            .group_by(KbArticle.category_id)
        )
        stmt = self._apply_organization_scope(stmt)
        stmt = self._include_deleted(stmt)
        rs = await self.db.execute(stmt)
        counts: dict[int, int] = {}
        for category_id, count in rs.all():
            counts[category_id] = count
        return counts

    async def list_published(
        self,
        *,
        search: str | None = None,
        category_id: int | None = None,
        order: Literal["title", "recent"] = "title",
        limit: int = 50,
    ) -> Sequence[KbArticle]:
        stmt = select(KbArticle).where(KbArticle.status == ArticleStatus.PUBLISHED)
        if category_id is not None:
            stmt = stmt.where(KbArticle.category_id == category_id)
        if search_expressions := self._get_search_expressions(search):
            stmt = stmt.where(or_(*search_expressions))
        stmt = self._apply_organization_scope(stmt)
        stmt = self._include_deleted(stmt)
        if order == "recent":
            stmt = stmt.order_by(KbArticle.published_at.desc(), KbArticle.id.desc())
        else:
            stmt = stmt.order_by(KbArticle.title)
        rs = await self.db.execute(stmt.limit(limit))
        return rs.unique().scalars().all()
