from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.platform.enums import Locale
from src.platform.schemas.common import Timestamp
from src.platform.schemas.types import ConstrainedEmail

ContactName = Annotated[str, Field(min_length=1, max_length=255)]


class ContactIn(BaseModel):
    name: ContactName
    email: ConstrainedEmail
    locale: Locale | None = None
    notes: str | None = None


class ContactPatch(BaseModel):
    name: ContactName | None = None
    email: ConstrainedEmail | None = None
    locale: Locale | None = None
    notes: str | None = None


class ContactSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class ContactOut(ContactSummary, Timestamp):
    organization_id: int
    locale: str | None
    notes: str | None
