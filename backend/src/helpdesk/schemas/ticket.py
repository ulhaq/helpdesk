from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.helpdesk.enums import (
    MessageAuthorType,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from src.helpdesk.schemas.contact import ContactIn, ContactSummary
from src.platform.schemas.common import Timestamp

TicketSubject = Annotated[str, Field(min_length=1, max_length=255)]
MessageBody = Annotated[str, Field(min_length=1, max_length=20_000)]


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TicketIn(BaseModel):
    subject: TicketSubject
    body: MessageBody
    priority: TicketPriority = TicketPriority.NORMAL
    # Either an existing contact, or the details of the customer who got in
    # touch - matched to an existing contact by email, created when new.
    contact_id: int | None = None
    contact: ContactIn | None = None
    assignee_id: int | None = None

    @model_validator(mode="after")
    def _exactly_one_contact(self) -> Self:
        if (self.contact_id is None) == (self.contact is None):
            raise ValueError("Provide exactly one of contact_id or contact")
        return self


class TicketPatch(BaseModel):
    subject: TicketSubject | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None


class TicketAssigneeIn(BaseModel):
    # null returns the ticket to the unassigned queue.
    assignee_id: int | None


class TicketMessageIn(BaseModel):
    body: MessageBody
    is_internal: bool = False


class TicketMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author_type: MessageAuthorType
    author_user_id: int | None
    author_contact_id: int | None
    author_name: str | None
    body: str
    is_internal: bool
    created_at: datetime


class TicketOut(Timestamp):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    number: int
    subject: str
    status: TicketStatus
    priority: TicketPriority
    channel: TicketChannel
    contact: ContactSummary
    assignee: UserSummary | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    last_message_at: datetime


class TicketDetailOut(TicketOut):
    messages: list[TicketMessageOut]
