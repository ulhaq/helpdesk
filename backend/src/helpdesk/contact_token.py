"""Signed access tokens for customers (contacts), who have no platform account.

A token names a contact and its organization, optionally narrowed to a single
ticket. The scope follows what the holder has proven:

- a token returned to the browser that just submitted a ticket opens that
  ticket only - anyone can type any email address into the widget;
- a token delivered by email (confirmation, agent reply, access link) opens
  all of the contact's conversations, because receiving it proves the holder
  owns the address.
"""

from dataclasses import dataclass

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.helpdesk.config import settings
from src.helpdesk.models.contact import Contact
from src.platform.core.config import settings as platform_settings
from src.platform.core.exceptions import NotAuthenticatedException
from src.platform.enums import ErrorCode

_SALT = "helpdesk-contact-access"


@dataclass(frozen=True)
class ContactAccess:
    contact_id: int
    organization_id: int
    # Set when the token opens one ticket rather than all of the contact's.
    ticket_id: int | None = None


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=platform_settings.app_secret.get_secret_value(), salt=_SALT
    )


def create_contact_token(contact: Contact, *, ticket_id: int | None = None) -> str:
    payload = {"c": contact.id, "o": contact.organization_id}
    if ticket_id is not None:
        payload["t"] = ticket_id
    return _serializer().dumps(payload)


def read_contact_token(token: str) -> ContactAccess:
    try:
        data = _serializer().loads(
            token, max_age=settings.contact_token_max_age_seconds
        )
    except SignatureExpired as exc:
        raise NotAuthenticatedException(
            "Signature expired", error_code=ErrorCode.SIGNATURE_EXPIRED
        ) from exc
    except BadSignature as exc:
        raise NotAuthenticatedException(
            "Signature invalid", error_code=ErrorCode.SIGNATURE_INVALID
        ) from exc

    if (
        not isinstance(data, dict)
        or not isinstance(data.get("c"), int)
        or not isinstance(data.get("o"), int)
        or not isinstance(data.get("t", 0), int)
    ):
        raise NotAuthenticatedException(
            "Signature invalid", error_code=ErrorCode.SIGNATURE_INVALID
        )
    return ContactAccess(
        contact_id=data["c"], organization_id=data["o"], ticket_id=data.get("t")
    )


def conversation_url(slug: str, token: str) -> str:
    """Link that opens the widget full-page, signed in as the token's contact."""
    return f"{platform_settings.frontend_url.rstrip('/')}/widget/{slug}?token={token}"
