from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from src.helpdesk.enums import HelpdeskPermission
from src.helpdesk.schemas.contact import ContactIn, ContactOut, ContactPatch
from src.helpdesk.services.contact import ContactService
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

router = APIRouter(prefix="/contacts")


@router.get("", status_code=status.HTTP_200_OK)
async def list_contacts(
    *,
    service: Annotated[ContactService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.READ_CONTACT))],
    sort: Annotated[list[str], Depends(sort_query(["email"]))],
    filters: Annotated[list[FilterItem], Depends(filters_query(["email"]))],
    q: SearchQuery,
    page_size: PageSizeQuery = 20,
    page_number: PageNumberQuery = 1,
) -> PaginatedResponse[ContactOut]:
    return await service.paginate(
        ContactOut,
        PageQueryParams(
            sort=sort,
            filters=filters,
            page_size=page_size,
            page_number=page_number,
            search=q,
        ),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_a_contact(
    service: Annotated[ContactService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.MANAGE_CONTACT))],
    contact_in: ContactIn,
) -> ContactOut:
    return await service.create_contact(contact_in)


@router.get("/{contact_id}", status_code=status.HTTP_200_OK)
async def get_a_contact(
    service: Annotated[ContactService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.READ_CONTACT))],
    contact_id: Annotated[int, Path()],
) -> ContactOut:
    return ContactOut.model_validate(await service.get(contact_id))


@router.patch("/{contact_id}", status_code=status.HTTP_200_OK)
async def patch_a_contact(
    service: Annotated[ContactService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.MANAGE_CONTACT))],
    contact_id: Annotated[int, Path()],
    contact_in: ContactPatch,
) -> ContactOut:
    return await service.patch_contact(contact_id, contact_in)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_a_contact(
    service: Annotated[ContactService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.MANAGE_CONTACT))],
    contact_id: Annotated[int, Path()],
) -> None:
    await service.delete_contact(contact_id)
