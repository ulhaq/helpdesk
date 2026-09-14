from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Path,
    Request,
    UploadFile,
    status,
)

from src.helpdesk.enums import HelpdeskPermission
from src.helpdesk.schemas.knowledge import (
    KnowledgeDocumentIn,
    KnowledgeDocumentOut,
    KnowledgeDocumentPatch,
    KnowledgeDocumentSummaryOut,
    KnowledgeSearchIn,
    KnowledgeSearchOut,
)
from src.helpdesk.services.knowledge import KnowledgeService
from src.platform.core.dependencies import require_permission
from src.platform.core.limiter import limiter
from src.platform.core.security import Auth
from src.platform.routers.query_options import (
    PageNumberQuery,
    PageSizeQuery,
    SearchQuery,
    filters_query,
    sort_query,
)
from src.platform.schemas.common import FilterItem, PageQueryParams, PaginatedResponse

router = APIRouter(prefix="/knowledge")

ManageKb = Annotated[Auth, Depends(require_permission(HelpdeskPermission.MANAGE_KB))]


@router.get("/documents", status_code=status.HTTP_200_OK)
async def list_knowledge_documents(
    *,
    service: Annotated[KnowledgeService, Depends()],
    _: ManageKb,
    sort: Annotated[
        list[str], Depends(sort_query(["title", "created_at", "updated_at"]))
    ],
    filters: Annotated[list[FilterItem], Depends(filters_query(["title", "source"]))],
    q: SearchQuery,
    page_size: PageSizeQuery = 20,
    page_number: PageNumberQuery = 1,
) -> PaginatedResponse[KnowledgeDocumentSummaryOut]:
    return await service.paginate_documents(
        PageQueryParams(
            sort=sort,
            filters=filters,
            page_size=page_size,
            page_number=page_number,
            search=q,
        )
    )


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def create_a_knowledge_document(
    service: Annotated[KnowledgeService, Depends()],
    _: ManageKb,
    document_in: KnowledgeDocumentIn,
) -> KnowledgeDocumentOut:
    return await service.create_text_document(document_in)


@router.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_a_knowledge_document(
    service: Annotated[KnowledgeService, Depends()],
    _: ManageKb,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=255)] = None,
) -> KnowledgeDocumentOut:
    return await service.upload_document(file, title)


@router.get("/documents/{document_id}", status_code=status.HTTP_200_OK)
async def get_a_knowledge_document(
    service: Annotated[KnowledgeService, Depends()],
    _: ManageKb,
    document_id: Annotated[int, Path()],
) -> KnowledgeDocumentOut:
    return await service.get_document(document_id)


@router.patch("/documents/{document_id}", status_code=status.HTTP_200_OK)
async def patch_a_knowledge_document(
    service: Annotated[KnowledgeService, Depends()],
    _: ManageKb,
    document_id: Annotated[int, Path()],
    document_in: KnowledgeDocumentPatch,
) -> KnowledgeDocumentOut:
    return await service.patch_document(document_id, document_in)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_a_knowledge_document(
    service: Annotated[KnowledgeService, Depends()],
    _: ManageKb,
    document_id: Annotated[int, Path()],
) -> None:
    await service.delete_document(document_id)


@router.post("/search", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def search_knowledge(
    request: Request,
    service: Annotated[KnowledgeService, Depends()],
    _: ManageKb,
    search_in: KnowledgeSearchIn,
) -> KnowledgeSearchOut:
    """Rank knowledge sections for a question the way AI retrieval does,
    without calling Claude."""
    return await service.search(search_in)
