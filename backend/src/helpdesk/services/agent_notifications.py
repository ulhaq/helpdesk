from src.helpdesk.enums import HelpdeskNotificationType, HelpdeskPermission
from src.helpdesk.models.ticket import Ticket
from src.helpdesk.repositories.manager import HelpdeskRepositoryManager


async def notify_agents(
    repos: HelpdeskRepositoryManager,
    *,
    ticket: Ticket,
    notification_type: HelpdeskNotificationType,
    contact_name: str,
) -> None:
    """Tell the team about customer activity on a ticket: its assignee, or -
    while nobody owns it - everyone who can reply to tickets."""
    if ticket.assignee_id is not None:
        recipients = [ticket.assignee_id]
    else:
        recipients = await repos.agent.user_ids_with_permission(
            ticket.organization_id, HelpdeskPermission.REPLY_TICKET
        )
    for user_id in recipients:
        await repos.notification.create(
            user_id=user_id,
            organization_id=ticket.organization_id,
            type=notification_type,
            payload={
                "ticket_id": ticket.id,
                "number": ticket.number,
                "subject": ticket.subject,
                "contact_name": contact_name,
            },
        )
