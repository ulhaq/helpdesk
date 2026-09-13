from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.helpdesk.enums import HelpdeskPermission
from src.helpdesk.schemas.reports import ReportSummaryOut
from src.helpdesk.services.reports import ReportService
from src.platform.core.dependencies import require_permission
from src.platform.core.security import Auth

router = APIRouter(prefix="/reports")


@router.get("/summary", status_code=status.HTTP_200_OK)
async def get_report_summary(
    service: Annotated[ReportService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.READ_REPORT))],
    days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> ReportSummaryOut:
    return await service.summary(days)
