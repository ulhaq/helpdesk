from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status

from src.helpdesk.enums import HelpdeskPermission, HelpdeskUsageMetric
from src.helpdesk.schemas.ticket import (
    TicketAssigneeIn,
    TicketDetailOut,
    TicketIn,
    TicketMessageIn,
    TicketMessageOut,
    TicketOut,
    TicketPatch,
)
from src.helpdesk.services.ticket import TicketService
from src.platform.billing.dependencies import require_limit
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

router = APIRouter(prefix="/tickets")

_SORT_FIELDS = ["number", "subject", "status", "priority", "last_message_at"]
_FILTER_FIELDS = [
    "status",
    "priority",
    "channel",
    "assignee_id",
    "contact_id",
    "last_message_at",
]


@router.get("", status_code=status.HTTP_200_OK)
async def list_tickets(
    *,
    service: Annotated[TicketService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.READ_TICKET))],
    sort: Annotated[list[str], Depends(sort_query(_SORT_FIELDS))],
    filters: Annotated[list[FilterItem], Depends(filters_query(_FILTER_FIELDS))],
    q: SearchQuery,
    page_size: PageSizeQuery = 20,
    page_number: PageNumberQuery = 1,
) -> PaginatedResponse[TicketOut]:
    return await service.paginate(
        TicketOut,
        PageQueryParams(
            sort=sort,
            filters=filters,
            page_size=page_size,
            page_number=page_number,
            search=q,
        ),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_a_ticket(
    service: Annotated[TicketService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.CREATE_TICKET))],
    __: Annotated[None, Depends(require_limit(HelpdeskUsageMetric.TICKETS_PER_MONTH))],
    ticket_in: TicketIn,
) -> TicketDetailOut:
    return await service.create_ticket(ticket_in)


@router.get("/{ticket_id}", status_code=status.HTTP_200_OK)
async def get_a_ticket(
    service: Annotated[TicketService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.READ_TICKET))],
    ticket_id: Annotated[int, Path()],
) -> TicketDetailOut:
    return await service.get_ticket(ticket_id)


@router.patch("/{ticket_id}", status_code=status.HTTP_200_OK)
async def patch_a_ticket(
    service: Annotated[TicketService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.UPDATE_TICKET))],
    ticket_id: Annotated[int, Path()],
    ticket_in: TicketPatch,
) -> TicketOut:
    return await service.patch_ticket(ticket_id, ticket_in)


@router.put("/{ticket_id}/assignee", status_code=status.HTTP_200_OK)
async def assign_a_ticket(
    service: Annotated[TicketService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.ASSIGN_TICKET))],
    ticket_id: Annotated[int, Path()],
    assignee_in: TicketAssigneeIn,
) -> TicketOut:
    return await service.assign_ticket(ticket_id, assignee_in)


@router.post("/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
async def reply_to_a_ticket(
    bg_tasks: BackgroundTasks,
    service: Annotated[TicketService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.REPLY_TICKET))],
    ticket_id: Annotated[int, Path()],
    message_in: TicketMessageIn,
) -> TicketMessageOut:
    return await service.reply(ticket_id, message_in, bg_tasks.add_task)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_a_ticket(
    service: Annotated[TicketService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.DELETE_TICKET))],
    ticket_id: Annotated[int, Path()],
) -> None:
    await service.delete_ticket(ticket_id)
