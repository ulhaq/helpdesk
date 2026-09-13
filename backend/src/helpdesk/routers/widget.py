"""Public widget API - no platform authentication.

Customers are identified by the `X-Contact-Token` header (see
`src.helpdesk.contact_token`); every route is rate limited per client IP.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Path, Request, status

from src.helpdesk.contact_token import ContactAccess, read_contact_token
from src.helpdesk.schemas.widget import (
    WidgetAccessLinkIn,
    WidgetConfigOut,
    WidgetMessageIn,
    WidgetMessageOut,
    WidgetTicketCreatedOut,
    WidgetTicketDetailOut,
    WidgetTicketIn,
    WidgetTicketListOut,
)
from src.helpdesk.services.widget import WidgetService
from src.platform.core.exceptions import NotAuthenticatedException
from src.platform.core.limiter import limiter

router = APIRouter(prefix="/widget/{slug}")

SlugPath = Annotated[str, Path(max_length=64)]


async def contact_access(
    token: Annotated[str | None, Header(alias="X-Contact-Token")] = None,
) -> ContactAccess:
    if not token:
        raise NotAuthenticatedException()
    return read_contact_token(token)


@router.get("", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def get_widget_config(
    request: Request,
    service: Annotated[WidgetService, Depends()],
    slug: SlugPath,
) -> WidgetConfigOut:
    return await service.get_config(slug)


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def submit_a_ticket(
    request: Request,
    bg_tasks: BackgroundTasks,
    service: Annotated[WidgetService, Depends()],
    slug: SlugPath,
    ticket_in: WidgetTicketIn,
) -> WidgetTicketCreatedOut:
    return await service.create_ticket(slug, ticket_in, bg_tasks.add_task)


@router.post("/access-link", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
async def request_an_access_link(
    request: Request,
    bg_tasks: BackgroundTasks,
    service: Annotated[WidgetService, Depends()],
    slug: SlugPath,
    link_in: WidgetAccessLinkIn,
) -> None:
    await service.send_access_link(slug, link_in, bg_tasks.add_task)


@router.get("/tickets", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def list_my_tickets(
    request: Request,
    service: Annotated[WidgetService, Depends()],
    access: Annotated[ContactAccess, Depends(contact_access)],
    slug: SlugPath,
) -> WidgetTicketListOut:
    return await service.list_tickets(slug, access)


@router.get("/tickets/{ticket_id}", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def get_my_ticket(
    request: Request,
    service: Annotated[WidgetService, Depends()],
    access: Annotated[ContactAccess, Depends(contact_access)],
    slug: SlugPath,
    ticket_id: Annotated[int, Path()],
) -> WidgetTicketDetailOut:
    return await service.get_ticket(slug, access, ticket_id)


@router.post("/tickets/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def reply_to_my_ticket(
    request: Request,
    service: Annotated[WidgetService, Depends()],
    access: Annotated[ContactAccess, Depends(contact_access)],
    slug: SlugPath,
    ticket_id: Annotated[int, Path()],
    message_in: WidgetMessageIn,
) -> WidgetMessageOut:
    return await service.reply(slug, access, ticket_id, message_in)
