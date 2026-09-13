"""Composition root - wires the product domain module into the generic SaaS core.

This is the only place (besides the product package itself) that may import
from `src.helpdesk`. The core never imports domain code; it emits hooks and
consumes the composed permission/role sets defined here.

To swap the product built on this boilerplate:
1. Replace the `src.helpdesk` imports below with your own domain module (or
   remove them entirely to start from the bare platform).
2. Adjust ALL_PERMISSIONS / PERMISSION_DESCRIPTIONS / DEFAULT_ROLES composition.
3. Register your domain's hook handlers, email subjects, and template
   directories in `bootstrap()`.
"""

from enum import StrEnum
from pathlib import Path

from src.helpdesk.email import HELPDESK_EMAIL_SUBJECTS
from src.helpdesk.enums import (
    HELPDESK_DEFAULT_ROLE_DESCRIPTIONS,
    HELPDESK_DEFAULT_ROLE_PERMISSIONS,
    HELPDESK_PERMISSION_DESCRIPTIONS,
    HelpdeskPermission,
)
from src.helpdesk.hooks import register_helpdesk_hooks
from src.platform import enums as core_enums
from src.platform.core import composition
from src.platform.core.template import add_template_directory
from src.platform.services.email_content import register_email_subjects

ALL_PERMISSIONS: list[StrEnum] = [*core_enums.Permission, *HelpdeskPermission]

PERMISSION_DESCRIPTIONS: dict[StrEnum, str] = {
    **core_enums.PERMISSION_DESCRIPTIONS,
    **HELPDESK_PERMISSION_DESCRIPTIONS,
}

DEFAULT_ROLES: list[tuple[str, str, list[StrEnum]]] = [
    (
        name,
        HELPDESK_DEFAULT_ROLE_DESCRIPTIONS.get(name, description),
        [*permissions, *HELPDESK_DEFAULT_ROLE_PERMISSIONS.get(name, [])],
    )
    for name, description, permissions in core_enums.DEFAULT_ROLES
]

_bootstrapped = False


def bootstrap() -> None:
    """Register domain hook handlers, email subjects and templates. Idempotent;
    called at process startup by both the API (`src.main`) and the worker
    (`worker.py`)."""
    global _bootstrapped
    if _bootstrapped:
        return
    composition.configure(ALL_PERMISSIONS, PERMISSION_DESCRIPTIONS, DEFAULT_ROLES)
    register_helpdesk_hooks()
    register_email_subjects(HELPDESK_EMAIL_SUBJECTS)
    add_template_directory(Path(__file__).resolve().parent / "helpdesk" / "templates")
    _bootstrapped = True
