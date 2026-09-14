from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.helpdesk.enums import MessageAuthorType, TicketStatus
from src.helpdesk.schemas.contact import ContactName
from src.helpdesk.schemas.ticket import MessageBody, TicketSubject
from src.platform.enums import Locale
from src.platform.schemas.types import ConstrainedEmail


class WidgetConfigOut(BaseModel):
    organization_name: str
    brand_color: str
    greeting: str | None
    # The widget offers article search when the help center is on.
    help_center_enabled: bool
    # Questions typed into article search also get a cited AI answer.
    ai_answers_enabled: bool


class WidgetTicketIn(BaseModel):
    name: ContactName
    email: ConstrainedEmail
    subject: TicketSubject
    body: MessageBody
    locale: Locale | None = None


class WidgetMessageIn(BaseModel):
    body: MessageBody


class WidgetAccessLinkIn(BaseModel):
    email: ConstrainedEmail
    locale: Locale | None = None


class WidgetMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_type: MessageAuthorType
    author_name: str | None
    body: str
    created_at: datetime


class WidgetTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    subject: str
    status: TicketStatus
    created_at: datetime
    last_message_at: datetime


class WidgetTicketDetailOut(WidgetTicketOut):
    messages: list[WidgetMessageOut]


class WidgetTicketListOut(BaseModel):
    contact_name: str
    tickets: list[WidgetTicketOut]


class WidgetTicketCreatedOut(BaseModel):
    ticket: WidgetTicketDetailOut
    # Opens this ticket only; see `src.helpdesk.contact_token`.
    access_token: str
