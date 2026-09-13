"""Public help center API - no authentication, rate limited per client IP."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status

from src.helpdesk.schemas.kb import HelpArticleOut, HelpCenterOut, HelpSearchOut
from src.helpdesk.services.help_center import HelpCenterService
from src.platform.core.limiter import limiter

router = APIRouter(prefix="/help/{slug}")

SlugPath = Annotated[str, Path(max_length=64)]


@router.get("", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def get_help_center(
    request: Request,
    service: Annotated[HelpCenterService, Depends()],
    slug: SlugPath,
) -> HelpCenterOut:
    return await service.home(slug)


@router.get("/articles", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def search_help_articles(
    request: Request,
    service: Annotated[HelpCenterService, Depends()],
    slug: SlugPath,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[str | None, Query(max_length=140)] = None,
) -> HelpSearchOut:
    return await service.search(slug, q or None, category)


@router.get("/articles/{article_slug}", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def get_help_article(
    request: Request,
    service: Annotated[HelpCenterService, Depends()],
    slug: SlugPath,
    article_slug: Annotated[str, Path(max_length=255)],
) -> HelpArticleOut:
    return await service.article(slug, article_slug)
