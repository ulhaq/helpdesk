from typing import Annotated

from fastapi import Depends

from src.helpdesk.enums import ArticleStatus
from src.helpdesk.markdown import plain_excerpt, render_markdown
from src.helpdesk.models.kb import KbArticle, KbCategory
from src.helpdesk.models.support_site import SupportSite
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.schemas.kb import (
    HelpArticleOut,
    HelpArticleSummaryOut,
    HelpCategoryOut,
    HelpCategoryRef,
    HelpCenterOut,
    HelpSearchOut,
)
from src.platform.core.exceptions import NotFoundException
from src.platform.services.base import BaseService

_RECENT_ARTICLES = 6


def _category_ref(category: KbCategory | None) -> HelpCategoryRef | None:
    if category is None:
        return None
    return HelpCategoryRef(name=category.name, slug=category.slug)


def _summary(article: KbArticle) -> HelpArticleSummaryOut:
    return HelpArticleSummaryOut(
        title=article.title,
        slug=article.slug,
        excerpt=plain_excerpt(article.body),
        category=_category_ref(article.category),
        updated_at=article.updated_at,
    )


class HelpCenterService(BaseService):
    """Public, read-only view of an organization's published articles."""

    def __init__(self, repos: Annotated[HelpdeskRepositoryManager, Depends()]) -> None:
        super().__init__(repos)
        self.sites = repos.support_site
        self.categories = repos.kb_category
        self.articles = repos.kb_article

    async def home(self, slug: str) -> HelpCenterOut:
        site = await self._site(slug)
        counts = await self.articles.published_counts_by_category()
        recent = await self.articles.list_published(
            order="recent", limit=_RECENT_ARTICLES
        )
        return HelpCenterOut(
            organization_name=await self.sites.get_organization_name(site),
            brand_color=site.brand_color,
            widget_enabled=site.widget_enabled,
            # Categories with nothing published yet are hidden.
            categories=[
                HelpCategoryOut(
                    name=category.name,
                    slug=category.slug,
                    description=category.description,
                    article_count=counts[category.id],
                )
                for category in await self.categories.list_ordered()
                if counts.get(category.id)
            ],
            recent_articles=[_summary(article) for article in recent],
        )

    async def search(
        self, slug: str, query: str | None, category_slug: str | None
    ) -> HelpSearchOut:
        await self._site(slug)
        category = None
        if category_slug is not None:
            category = await self.categories.get_by_slug(category_slug)
            if category is None:
                raise NotFoundException(f"Category not found. [{category_slug=}]")
        articles = await self.articles.list_published(
            search=query, category_id=category.id if category else None
        )
        return HelpSearchOut(
            category=_category_ref(category),
            articles=[_summary(article) for article in articles],
        )

    async def article(self, slug: str, article_slug: str) -> HelpArticleOut:
        await self._site(slug)
        article = await self.articles.get_by_slug(article_slug)
        if article is None or article.status != ArticleStatus.PUBLISHED:
            raise NotFoundException(f"Article not found. [{article_slug=}]")
        return HelpArticleOut(
            title=article.title,
            slug=article.slug,
            html=render_markdown(article.body),
            category=_category_ref(article.category),
            published_at=article.published_at,
            updated_at=article.updated_at,
        )

    async def _site(self, slug: str) -> SupportSite:
        site = await self.sites.get_by_slug(slug)
        if site is None or not site.help_center_enabled:
            raise NotFoundException(f"Help center not found. [{slug=}]")
        self.categories.set_organization_scope(site.organization_id)
        self.articles.set_organization_scope(site.organization_id)
        return site
