from typing import Annotated

from fastapi import Depends

from src.helpdesk.enums import HelpdeskAuditAction, HelpdeskErrorCode
from src.helpdesk.models.contact import Contact
from src.helpdesk.repositories.contact import ContactRepository
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.helpdesk.schemas.contact import ContactIn, ContactOut, ContactPatch
from src.platform.core.dependencies import authenticate
from src.platform.core.exceptions import AlreadyExistsException
from src.platform.core.security import Auth
from src.platform.services.base import ResourceService


class ContactService(
    ResourceService[ContactRepository, Contact, ContactIn | ContactPatch, ContactOut]
):
    current_user: Auth

    def __init__(
        self,
        repos: Annotated[HelpdeskRepositoryManager, Depends()],
        current_user: Annotated[Auth, Depends(authenticate)],
    ) -> None:
        self.repo = repos.contact
        self.repo.set_organization_scope(current_user.organization_id)
        self.current_user = current_user
        super().__init__(repos)

    async def _assert_email_available(
        self, email: str, exclude_id: int | None = None
    ) -> None:
        existing = await self.repo.get_by_email(email)
        if existing is not None and existing.id != exclude_id:
            raise AlreadyExistsException(
                f"Contact already exists. [email={email}]",
                error_code=HelpdeskErrorCode.CONTACT_EMAIL_TAKEN,
            )

    async def create_contact(self, schema_in: ContactIn) -> ContactOut:
        async def validate() -> None:
            await self._assert_email_available(schema_in.email)

        contact = await super().create(schema_in, validate)
        await self.log_audit(
            HelpdeskAuditAction.CONTACT_CREATE,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="contact",
            resource_id=contact.id,
            details={"email": contact.email},
        )
        return ContactOut.model_validate(contact)

    async def patch_contact(
        self, identifier: int, schema_in: ContactPatch
    ) -> ContactOut:
        async def validate() -> None:
            if schema_in.email is not None:
                await self._assert_email_available(
                    schema_in.email, exclude_id=identifier
                )

        contact = await super().patch(identifier, schema_in, validate)
        await self.log_audit(
            HelpdeskAuditAction.CONTACT_UPDATE,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="contact",
            resource_id=contact.id,
            details=schema_in.model_dump(mode="json", exclude_unset=True),
        )
        return ContactOut.model_validate(contact)

    async def delete_contact(self, identifier: int) -> None:
        await super().delete(identifier)
        await self.log_audit(
            HelpdeskAuditAction.CONTACT_DELETE,
            organization_id=self.current_user.organization_id,
            user_id=self.current_user.id,
            resource_type="contact",
            resource_id=identifier,
        )
