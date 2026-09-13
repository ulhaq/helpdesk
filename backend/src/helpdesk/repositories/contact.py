from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from src.helpdesk.models.contact import Contact
from src.platform.repositories.base import OrganizationScopedRepository


class ContactRepository(OrganizationScopedRepository[Contact]):
    search_fields: ClassVar[list[str]] = ["name", "email"]

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Contact, db)

    async def get_by_email(self, email: str) -> Contact | None:
        return await self._get_by_field("email", email.lower())
