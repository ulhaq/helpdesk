import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.models.support_site import SupportSite
from src.helpdesk.slugs import slugify
from src.platform.models.organization import Organization
from src.platform.repositories.base import SQLResourceRepository


class SupportSiteRepository(SQLResourceRepository[SupportSite]):
    """Support sites are looked up publicly by slug, so this repository is not
    organization-scoped; every organization-specific method takes the
    organization explicitly."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(SupportSite, db)

    async def get_for_organization(self, organization_id: int) -> SupportSite | None:
        rs = await self.db.execute(
            select(SupportSite).where(SupportSite.organization_id == organization_id)
        )
        return rs.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> SupportSite | None:
        rs = await self.db.execute(select(SupportSite).where(SupportSite.slug == slug))
        return rs.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        return await self.get_by_slug(slug) is not None

    async def get_organization_name(self, site: SupportSite) -> str:
        # A column select: the Organization relationship eagerly loads members.
        rs = await self.db.execute(
            select(Organization.name).where(Organization.id == site.organization_id)
        )
        return rs.scalar_one()

    async def get_or_create_for_organization(
        self, organization_id: int, organization_name: str
    ) -> SupportSite:
        site = await self.get_for_organization(organization_id)
        if site is not None:
            return site
        return await self.create(
            organization_id=organization_id,
            slug=await self._unique_slug(organization_name),
        )

    async def _unique_slug(self, organization_name: str) -> str:
        # The random suffix keeps generated slugs from being guessable from the
        # organization name alone; owners can pick a friendlier one later.
        base = slugify(organization_name, max_length=40, fallback="support")
        while True:
            slug = f"{base}-{secrets.token_hex(3)}"
            if not await self.slug_exists(slug):
                return slug
