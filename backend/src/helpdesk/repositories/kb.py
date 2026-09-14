from collections.abc import Sequence
from datetime import UTC, datetime
from typing import ClassVar, Literal

from sqlalchemy import Select, delete, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.enums import ArticleStatus
from src.helpdesk.kb_chunks import ArticleChunk
from src.helpdesk.models.kb import KbArticle, KbArticleChunk, KbCategory
from src.platform.repositories.base import OrganizationScopedRepository

# Full-text document for a chunk: heading words outrank body words. Must stay
# identical to the `ix_kb_article_chunk_search` index expression, or Postgres
# can't use the index. 'simple' has no stemming or stopwords, so it works for
# Danish and English content alike; query terms use prefix matching instead.
_SEARCH_VECTOR = (
    "setweight(to_tsvector('simple'::regconfig, kb_article_chunk.heading), "
    "'A'::\"char\") || "
    "setweight(to_tsvector('simple'::regconfig, kb_article_chunk.content), "
    "'B'::\"char\")"
)


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

    async def published_chars(self) -> int:
        """Total title and body length of the published articles."""
        stmt = select(
            func.coalesce(
                func.sum(func.length(KbArticle.title) + func.length(KbArticle.body)),
                0,
            )
        ).where(KbArticle.status == ArticleStatus.PUBLISHED)
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
        limit: int | None = 50,
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
        if limit is not None:
            stmt = stmt.limit(limit)
        rs = await self.db.execute(stmt)
        return rs.unique().scalars().all()


class KbArticleChunkRepository(OrganizationScopedRepository[KbArticleChunk]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(KbArticleChunk, db)

    async def replace_for_article(
        self, article: KbArticle, chunks: Sequence[ArticleChunk]
    ) -> None:
        existing = self._apply_organization_scope(
            select(KbArticleChunk.id).where(KbArticleChunk.article_id == article.id)
        )
        await self.db.execute(
            delete(KbArticleChunk).where(KbArticleChunk.id.in_(existing))
        )
        now = datetime.now(UTC)
        self.db.add_all(
            [
                KbArticleChunk(
                    organization_id=article.organization_id,
                    article_id=article.id,
                    position=position,
                    heading=chunk.heading,
                    content=chunk.content,
                    created_at=now,
                    updated_at=now,
                )
                for position, chunk in enumerate(chunks)
            ]
        )
        await self.save()

    async def search(
        self, terms: Sequence[str], *, limit: int
    ) -> list[tuple[KbArticleChunk, KbArticle]]:
        """Chunks of active, published articles matching any of `terms`, best
        match first."""
        stmt = (
            select(KbArticleChunk, KbArticle)
            .join(KbArticle, KbArticle.id == KbArticleChunk.article_id)
            .where(
                KbArticle.organization_id == KbArticleChunk.organization_id,
                KbArticle.status == ArticleStatus.PUBLISHED,
                KbArticle.deleted_at.is_(None),
            )
        )
        stmt = self._apply_organization_scope(stmt)
        if self.db.get_bind().dialect.name == "postgresql":
            return await self._search_full_text(stmt, terms, limit)
        return await self._search_substrings(stmt, terms, limit)

    async def _search_full_text(
        self, stmt: Select, terms: Sequence[str], limit: int
    ) -> list[tuple[KbArticleChunk, KbArticle]]:
        vector = literal_column(_SEARCH_VECTOR)
        # Terms are letters and digits only (see `retrieval.query_terms`), so
        # they're safe inside tsquery syntax. Prefix matching (`:*`) stands in
        # for stemming: "invoice" also finds "invoices".
        query = func.to_tsquery(
            literal_column("'simple'::regconfig"),
            " | ".join(f"{term}:*" for term in terms),
        )
        # Normalization 1 divides by 1 + log(length): long sections don't win
        # just by repeating words.
        rank = func.ts_rank(vector, query, 1)
        stmt = (
            stmt.where(vector.op("@@")(query))
            .order_by(rank.desc(), KbArticleChunk.id)
            .limit(limit)
        )
        rs = await self.db.execute(stmt)
        return [(chunk, article) for chunk, article in rs.tuples().all()]

    async def _search_substrings(
        self, stmt: Select, terms: Sequence[str], limit: int
    ) -> list[tuple[KbArticleChunk, KbArticle]]:
        """Portable fallback for databases without full-text search (the
        SQLite test suite): substring matches, ranked like the Postgres
        weights - a heading hit counts double."""
        stmt = stmt.where(
            or_(
                *(
                    field.ilike(f"%{term}%")
                    for term in terms
                    for field in (KbArticleChunk.heading, KbArticleChunk.content)
                )
            )
        )
        rs = await self.db.execute(stmt)
        rows = [(chunk, article) for chunk, article in rs.tuples().all()]

        def score(chunk: KbArticleChunk) -> int:
            heading, content = chunk.heading.lower(), chunk.content.lower()
            return sum(2 * heading.count(t) + content.count(t) for t in terms)

        rows.sort(key=lambda row: (-score(row[0]), row[0].id))
        return rows[:limit]
