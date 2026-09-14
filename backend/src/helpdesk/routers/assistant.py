from typing import Annotated

from anthropic import AsyncAnthropic
from fastapi import APIRouter, Depends, Path, Request, status

from src.helpdesk.assistant import get_ai_client
from src.helpdesk.enums import HelpdeskPermission
from src.helpdesk.schemas.assistant import AssistantStatusOut, ReplySuggestionOut
from src.helpdesk.services.assistant import ReplySuggestionService
from src.platform.core.dependencies import authenticate, require_permission
from src.platform.core.limiter import limiter
from src.platform.core.security import Auth

router = APIRouter()


@router.get("/helpdesk/assistant", status_code=status.HTTP_200_OK)
async def get_assistant_status(
    _: Annotated[Auth, Depends(authenticate)],
    client: Annotated[AsyncAnthropic | None, Depends(get_ai_client)],
) -> AssistantStatusOut:
    return AssistantStatusOut(enabled=client is not None)


@router.post("/tickets/{ticket_id}/reply-suggestion", status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def suggest_a_reply(
    request: Request,
    service: Annotated[ReplySuggestionService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.REPLY_TICKET))],
    ticket_id: Annotated[int, Path()],
) -> ReplySuggestionOut:
    return await service.suggest(ticket_id)
