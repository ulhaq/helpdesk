from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from src.helpdesk.enums import HelpdeskPermission
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
from src.helpdesk.services.kb import KbService
from src.platform.core.dependencies import require_permission
from src.platform.core.security import Auth
from src.platform.routers.query_options import (
    PageNumberQuery,
    PageSizeQuery,
    SearchQuery,
    filters_query,
    sort_query,
)
from src.platform.schemas.common import FilterItem, PageQueryParams, PaginatedResponse

router = APIRouter(prefix="/kb")

ManageKb = Annotated[Auth, Depends(require_permission(HelpdeskPermission.MANAGE_KB))]


@router.get("/categories", status_code=status.HTTP_200_OK)
async def list_kb_categories(
    service: Annotated[KbService, Depends()], _: ManageKb
) -> list[KbCategoryOut]:
    return await service.list_categories()


@router.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_a_kb_category(
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    category_in: KbCategoryIn,
) -> KbCategoryOut:
    return await service.create_category(category_in)


@router.patch("/categories/{category_id}", status_code=status.HTTP_200_OK)
async def patch_a_kb_category(
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    category_id: Annotated[int, Path()],
    category_in: KbCategoryPatch,
) -> KbCategoryOut:
    return await service.patch_category(category_id, category_in)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_a_kb_category(
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    category_id: Annotated[int, Path()],
) -> None:
    await service.delete_category(category_id)


@router.get("/articles", status_code=status.HTTP_200_OK)
async def list_kb_articles(
    *,
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    sort: Annotated[
        list[str], Depends(sort_query(["title", "status", "published_at"]))
    ],
    filters: Annotated[
        list[FilterItem], Depends(filters_query(["title", "status", "category_id"]))
    ],
    q: SearchQuery,
    page_size: PageSizeQuery = 20,
    page_number: PageNumberQuery = 1,
) -> PaginatedResponse[KbArticleSummaryOut]:
    return await service.paginate_articles(
        PageQueryParams(
            sort=sort,
            filters=filters,
            page_size=page_size,
            page_number=page_number,
            search=q,
        )
    )


@router.post("/articles", status_code=status.HTTP_201_CREATED)
async def create_a_kb_article(
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    article_in: KbArticleIn,
) -> KbArticleOut:
    return await service.create_article(article_in)


@router.post("/articles/preview", status_code=status.HTTP_200_OK)
async def preview_a_kb_article(
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    preview_in: MarkdownPreviewIn,
) -> MarkdownPreviewOut:
    return service.preview(preview_in)


@router.get("/articles/{article_id}", status_code=status.HTTP_200_OK)
async def get_a_kb_article(
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    article_id: Annotated[int, Path()],
) -> KbArticleOut:
    return await service.get_article(article_id)


@router.patch("/articles/{article_id}", status_code=status.HTTP_200_OK)
async def patch_a_kb_article(
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    article_id: Annotated[int, Path()],
    article_in: KbArticlePatch,
) -> KbArticleOut:
    return await service.patch_article(article_id, article_in)


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_a_kb_article(
    service: Annotated[KbService, Depends()],
    _: ManageKb,
    article_id: Annotated[int, Path()],
) -> None:
    await service.delete_article(article_id)
