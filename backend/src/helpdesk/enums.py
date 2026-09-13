"""Helpdesk product enums.

Everything in this module belongs to the helpdesk product. The platform enums
(roles, core permissions, billing, audit) live in `src.platform.enums`; this
module contributes the product additions, which the composition root
(`src.bootstrap`) merges into the seeded permission/role sets.
"""

from enum import StrEnum

from src.platform.enums import ErrorCodeEnum


class HelpdeskPermission(StrEnum):
    READ_TICKET = "read:ticket"
    CREATE_TICKET = "create:ticket"
    UPDATE_TICKET = "update:ticket"
    ASSIGN_TICKET = "assign:ticket"
    REPLY_TICKET = "reply:ticket"
    DELETE_TICKET = "delete:ticket"
    READ_CONTACT = "read:contact"
    MANAGE_CONTACT = "manage:contact"
    MANAGE_HELPDESK = "manage:helpdesk"
    MANAGE_KB = "manage:kb"
    READ_REPORT = "read:report"


class TicketStatus(StrEnum):
    # Waiting on the team.
    OPEN = "open"
    # Waiting on the customer.
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketChannel(StrEnum):
    AGENT = "agent"
    WIDGET = "widget"


class MessageAuthorType(StrEnum):
    AGENT = "agent"
    CONTACT = "contact"


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    # Visible on the public help center and in the widget.
    PUBLISHED = "published"


class HelpdeskAuditAction(StrEnum):
    TICKET_CREATE = "ticket.create"
    TICKET_UPDATE = "ticket.update"
    TICKET_ASSIGN = "ticket.assign"
    TICKET_DELETE = "ticket.delete"
    CONTACT_CREATE = "contact.create"
    CONTACT_UPDATE = "contact.update"
    CONTACT_DELETE = "contact.delete"
    SUPPORT_SITE_UPDATE = "support_site.update"
    KB_CATEGORY_CREATE = "kb_category.create"
    KB_CATEGORY_UPDATE = "kb_category.update"
    KB_CATEGORY_DELETE = "kb_category.delete"
    KB_ARTICLE_CREATE = "kb_article.create"
    KB_ARTICLE_UPDATE = "kb_article.update"
    KB_ARTICLE_DELETE = "kb_article.delete"


class HelpdeskUsageMetric(StrEnum):
    # Plan setting key capping how many tickets an organization may open per
    # billing period.
    TICKETS_PER_MONTH = "tickets_per_month"
    # Plan setting key capping how many knowledge base articles may exist.
    KB_ARTICLES = "kb_articles"


class HelpdeskNotificationType(StrEnum):
    TICKET_ASSIGNED = "ticket_assigned"
    # Customer activity from the widget, sent to the assignee or - while the
    # ticket is unassigned - to everyone who can reply to tickets.
    TICKET_CREATED = "ticket_created"
    TICKET_CUSTOMER_REPLIED = "ticket_customer_replied"


class HelpdeskErrorCode(ErrorCodeEnum):
    CONTACT_EMAIL_TAKEN = (
        "contact_email_taken",
        "A contact with this email already exists",
    )
    ASSIGNEE_NOT_MEMBER = (
        "assignee_not_member",
        "The assignee is not a member of this organization",
    )
    TICKET_CLOSED = (
        "ticket_closed",
        "A closed ticket cannot receive public replies",
    )
    SUPPORT_SLUG_TAKEN = (
        "support_slug_taken",
        "This support address is already in use",
    )
    KB_SLUG_TAKEN = (
        "kb_slug_taken",
        "This URL is already used by another article or category",
    )


HELPDESK_PERMISSION_DESCRIPTIONS: dict[HelpdeskPermission, str] = {
    HelpdeskPermission.READ_TICKET: "Allows the user to read tickets.",
    HelpdeskPermission.CREATE_TICKET: "Allows the user to create tickets.",
    HelpdeskPermission.UPDATE_TICKET: (
        "Allows the user to change a ticket's subject, status and priority."
    ),
    HelpdeskPermission.ASSIGN_TICKET: "Allows the user to assign tickets.",
    HelpdeskPermission.REPLY_TICKET: (
        "Allows the user to reply to tickets and add internal notes."
    ),
    HelpdeskPermission.DELETE_TICKET: "Allows the user to delete tickets.",
    HelpdeskPermission.READ_CONTACT: "Allows the user to read contacts.",
    HelpdeskPermission.MANAGE_CONTACT: (
        "Allows the user to create, update and delete contacts."
    ),
    HelpdeskPermission.MANAGE_HELPDESK: (
        "Allows the user to configure the support widget and help center."
    ),
    HelpdeskPermission.MANAGE_KB: (
        "Allows the user to write and publish knowledge base articles."
    ),
    HelpdeskPermission.READ_REPORT: "Allows the user to read support reports.",
}

# Product-specific copy for the default roles, merged over the generic
# platform descriptions by the composition root. New organizations are seeded
# with only the Owner role, so there are no non-owner default roles to extend.
HELPDESK_DEFAULT_ROLE_DESCRIPTIONS: dict[str, str] = {}

# Per-role product permission grants, merged into the platform DEFAULT_ROLES by
# the composition root.
HELPDESK_DEFAULT_ROLE_PERMISSIONS: dict[str, list[HelpdeskPermission]] = {}
