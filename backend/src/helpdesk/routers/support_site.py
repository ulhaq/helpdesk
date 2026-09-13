from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.helpdesk.enums import HelpdeskPermission
from src.helpdesk.schemas.support_site import SupportSiteOut, SupportSitePatch
from src.helpdesk.services.support_site import SupportSiteService
from src.platform.core.dependencies import require_permission
from src.platform.core.security import Auth

router = APIRouter(prefix="/helpdesk/support-site")


@router.get("", status_code=status.HTTP_200_OK)
async def get_the_support_site(
    service: Annotated[SupportSiteService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.MANAGE_HELPDESK))],
) -> SupportSiteOut:
    return await service.get_site()


@router.patch("", status_code=status.HTTP_200_OK)
async def patch_the_support_site(
    service: Annotated[SupportSiteService, Depends()],
    _: Annotated[Auth, Depends(require_permission(HelpdeskPermission.MANAGE_HELPDESK))],
    site_in: SupportSitePatch,
) -> SupportSiteOut:
    return await service.patch_site(site_in)
