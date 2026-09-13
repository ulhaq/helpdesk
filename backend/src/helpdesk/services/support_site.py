from typing import Annotated, Any

from fastapi import Depends

from src.helpdesk.enums import HelpdeskAuditAction, HelpdeskErrorCode
from src.helpdesk.models.support_site import SupportSite
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.schemas.support_site import SupportSiteOut, SupportSitePatch
from src.platform.core.dependencies import authenticate
from src.platform.core.exceptions import AlreadyExistsException
from src.platform.core.security import Auth
from src.platform.services.base import BaseService


class SupportSiteService(BaseService):
    """The current organization's support site, as managed by its team."""

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        current_user: Annotated[Auth, Depends(authenticate)],
    ) -> None:
        super().__init__(repos)
        self.sites = repos.support_site
        self.current_user = current_user

    async def _site(self) -> SupportSite:
        organization = await self.repos.organization.get_one(
            self.current_user.organization_id
        )
        return await self.sites.get_or_create_for_organization(
            organization.id, organization.name
        )

    async def get_site(self) -> SupportSiteOut:
        return SupportSiteOut.model_validate(await self._site())

    async def patch_site(self, schema_in: SupportSitePatch) -> SupportSiteOut:
        site = await self._site()
        # greeting may be cleared with null; the other fields are required.
        changes: dict[str, Any] = {
            key: value
            for key, value in schema_in.model_dump(exclude_unset=True).items()
            if value is not None or key == "greeting"
        }
        new_slug = changes.get("slug")
        if (
            new_slug is not None
            and new_slug != site.slug
            and await self.sites.slug_exists(new_slug)
        ):
            raise AlreadyExistsException(
                f"Support site slug already exists. [slug={new_slug}]",
                error_code=HelpdeskErrorCode.SUPPORT_SLUG_TAKEN,
            )

        site = await self.sites.update(site, **changes)
        await self.log_audit(
            HelpdeskAuditAction.SUPPORT_SITE_UPDATE,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="support_site",
            resource_id=site.id,
            details=changes,
        )
        return SupportSiteOut.model_validate(site)
