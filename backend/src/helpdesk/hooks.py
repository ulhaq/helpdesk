"""Helpdesk handlers for the platform lifecycle hooks.

Registered by the composition root (`src.bootstrap`). Handlers receive keyword
arguments only, including the platform ``RepositoryManager`` as ``repos``;
wrap its session in ``HelpdeskRepositoryManager(repos.db)`` to reach product
repositories inside the caller's transaction.
"""

from src.helpdesk.repositories.manager import HelpdeskRepositoryManager
from src.platform.core import hooks
from src.platform.core.hooks import HookEvent
from src.platform.repositories.repository_manager import RepositoryManager


async def unassign_tickets_of_removed_member(
    *, repos: RepositoryManager, organization_id: int, user_id: int
) -> None:
    """A removed member can no longer work the organization's tickets; return
    them to the unassigned queue instead of leaving nobody watching them."""
    ticket_repo = HelpdeskRepositoryManager(repos.db).ticket
    ticket_repo.set_organization_scope(organization_id)
    await ticket_repo.unassign_user(user_id)


def register_helpdesk_hooks() -> None:
    hooks.register(HookEvent.MEMBER_REMOVED, unassign_tickets_of_removed_member)
