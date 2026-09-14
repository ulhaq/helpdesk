from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends

from src.helpdesk.enums import (
    ArticleStatus,
    HelpdeskAuditAction,
    HelpdeskErrorCode,
    HelpdeskUsageMetric,
)
from src.helpdesk.kb_chunks import split_article
from src.helpdesk.markdown import render_markdown
from src.helpdesk.models.kb import KbArticle, KbCategory
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.schemas.kb import (
    KbArticleIn,
    KbArticleOut,
    KbArticlePatch,
    KbArticleSummaryOut,
    KbCategoryIn,
    KbCategoryOut,
    KbCategoryPatch,
    MarkdownPreviewIn,
    MarkdownPreviewOut,
)
from src.helpdesk.slugs import slugify
from src.platform.core.dependencies import authenticate
from src.platform.core.exceptions import AlreadyExistsException
from src.platform.core.security import Auth
from src.platform.schemas.common import PageQueryParams, PaginatedResponse
from src.platform.services.base import BaseService

# Fields that may be cleared with an explicit null; every other patch field is
# required, so a null there is ignored.
_NULLABLE_CATEGORY_FIELDS = {"description"}
_NULLABLE_ARTICLE_FIELDS = {"category_id"}


def _changes(schema_in: Any, nullable: set[str]) -> dict[str, Any]:
    return {
        key: value
        for key, value in schema_in.model_dump(exclude_unset=True).items()
        if value is not None or key in nullable
    }


class KbService(BaseService):
    """The knowledge base as managed by the organization's team."""

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        current_user: Annotated[Auth, Depends(authenticate)],
    ) -> None:
        super().__init__(repos)
        organization_id = current_user.organization_id
        self.categories = repos.kb_category
        self.categories.set_organization_scope(organization_id)
        self.articles = repos.kb_article
        self.articles.set_organization_scope(organization_id)
        self.chunks = repos.kb_article_chunk
        self.chunks.set_organization_scope(organization_id)
        self.current_user = current_user

    # --- categories

    async def list_categories(self) -> list[KbCategoryOut]:
        return [
            KbCategoryOut.model_validate(category)
            for category in await self.categories.list_ordered()
        ]

    async def create_category(self, schema_in: KbCategoryIn) -> KbCategoryOut:
        if schema_in.slug is not None:
            await self._assert_category_slug_free(schema_in.slug)
            slug = schema_in.slug
        else:
            slug = await self._unique_category_slug(schema_in.name)
        category = await self.categories.create(
            **schema_in.model_dump(exclude={"slug"}), slug=slug
        )
        await self._audit_category(HelpdeskAuditAction.KB_CATEGORY_CREATE, category)
        return KbCategoryOut.model_validate(category)

    async def patch_category(
        self, identifier: int, schema_in: KbCategoryPatch
    ) -> KbCategoryOut:
        category = await self.categories.get_one(identifier)
        changes = _changes(schema_in, _NULLABLE_CATEGORY_FIELDS)
        if "slug" in changes and changes["slug"] != category.slug:
            await self._assert_category_slug_free(changes["slug"])
        category = await self.categories.update(category, **changes)
        await self._audit_category(HelpdeskAuditAction.KB_CATEGORY_UPDATE, category)
        return KbCategoryOut.model_validate(category)

    async def delete_category(self, identifier: int) -> None:
        category = await self.categories.get_one(identifier)
        # Articles outlive their category; they just become uncategorized.
        await self.articles.detach_category(category.id)
        await self.categories.delete(category)
        await self._audit_category(HelpdeskAuditAction.KB_CATEGORY_DELETE, category)

    # --- articles

    async def paginate_articles(
        self, params: PageQueryParams
    ) -> PaginatedResponse[KbArticleSummaryOut]:
        items, total = await self.articles.paginate(
            sort=params.sort,
            filters=params.filters,
            page_size=params.page_size,
            page_number=params.page_number,
            search=params.search,
        )
        return PaginatedResponse(
            items=[KbArticleSummaryOut.model_validate(item) for item in items],
            page_number=params.page_number,
            page_size=params.page_size,
            total=total,
        )

    async def get_article(self, identifier: int) -> KbArticleOut:
        return KbArticleOut.model_validate(await self.articles.get_one(identifier))

    async def create_article(self, schema_in: KbArticleIn) -> KbArticleOut:
        await self._require_capacity(
            HelpdeskUsageMetric.KB_ARTICLES,
            self.current_user.organization_id,
            await self.articles.count(),
        )
        if schema_in.category_id is not None:
            await self.categories.get_one(schema_in.category_id)
        if schema_in.slug is not None:
            await self._assert_article_slug_free(schema_in.slug)
            slug = schema_in.slug
        else:
            slug = await self._unique_article_slug(schema_in.title)

        article = await self.articles.create(
            **schema_in.model_dump(exclude={"slug"}),
            slug=slug,
            author_id=self.current_user.id,
            published_at=(
                datetime.now(UTC)
                if schema_in.status == ArticleStatus.PUBLISHED
                else None
            ),
        )
        await self._index_article(article)
        await self.repos.db.refresh(article, ["category"])
        await self._audit_article(HelpdeskAuditAction.KB_ARTICLE_CREATE, article)
        return KbArticleOut.model_validate(article)

    async def patch_article(
        self, identifier: int, schema_in: KbArticlePatch
    ) -> KbArticleOut:
        article = await self.articles.get_one(identifier)
        changes = _changes(schema_in, _NULLABLE_ARTICLE_FIELDS)
        if "slug" in changes and changes["slug"] != article.slug:
            await self._assert_article_slug_free(changes["slug"])
        if changes.get("category_id") is not None:
            await self.categories.get_one(changes["category_id"])
        if (
            changes.get("status") == ArticleStatus.PUBLISHED
            and article.published_at is None
        ):
            changes["published_at"] = datetime.now(UTC)

        article = await self.articles.update(article, **changes)
        if "title" in changes or "body" in changes:
            await self._index_article(article)
        await self.repos.db.refresh(article, ["category"])
        await self._audit_article(HelpdeskAuditAction.KB_ARTICLE_UPDATE, article)
        return KbArticleOut.model_validate(article)

    async def delete_article(self, identifier: int) -> None:
        article = await self.articles.get_one(identifier)
        await self.articles.delete(article)
        await self._audit_article(HelpdeskAuditAction.KB_ARTICLE_DELETE, article)

    def preview(self, schema_in: MarkdownPreviewIn) -> MarkdownPreviewOut:
        return MarkdownPreviewOut(html=render_markdown(schema_in.body))

    # --- helpers

    async def _index_article(self, article: KbArticle) -> None:
        """Rebuild the sections the AI assistant retrieves. Drafts are indexed
        too; search only returns sections of published articles."""
        await self.chunks.replace_for_article(
            article, split_article(article.title, article.body)
        )

    async def _unique_article_slug(self, title: str) -> str:
        base = slugify(title, max_length=200, fallback="article")
        slug, suffix = base, 2
        while await self.articles.get_by_slug(slug) is not None:
            slug, suffix = f"{base}-{suffix}", suffix + 1
        return slug

    async def _unique_category_slug(self, name: str) -> str:
        base = slugify(name, max_length=130, fallback="category")
        slug, suffix = base, 2
        while await self.categories.get_by_slug(slug) is not None:
            slug, suffix = f"{base}-{suffix}", suffix + 1
        return slug

    async def _assert_article_slug_free(self, slug: str) -> None:
        if await self.articles.get_by_slug(slug) is not None:
            raise AlreadyExistsException(
                f"Article slug already exists. [{slug=}]",
                error_code=HelpdeskErrorCode.KB_SLUG_TAKEN,
            )

    async def _assert_category_slug_free(self, slug: str) -> None:
        if await self.categories.get_by_slug(slug) is not None:
            raise AlreadyExistsException(
                f"Category slug already exists. [{slug=}]",
                error_code=HelpdeskErrorCode.KB_SLUG_TAKEN,
            )

    async def _audit_article(
        self, action: HelpdeskAuditAction, article: KbArticle
    ) -> None:
        await self.log_audit(
            action,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="kb_article",
            resource_id=article.id,
            details={"title": article.title, "status": article.status},
        )

    async def _audit_category(
        self, action: HelpdeskAuditAction, category: KbCategory
    ) -> None:
        await self.log_audit(
            action,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="kb_category",
            resource_id=category.id,
            details={"name": category.name},
        )
