"""Subject lines for helpdesk emails, registered by the composition root.

Keyed [locale][template]; values are `str.format` templates resolved against
the email's `data` dict (see `src.platform.services.email_content`).
"""

HELPDESK_EMAIL_SUBJECTS: dict[str, dict[str, str]] = {
    "en": {
        "ticket-reply": "[#{ticket_number}] {ticket_subject}",
        "ticket-received": "[#{ticket_number}] We received your request",
        "ticket-access": "Your conversations with {organization_name}",
    },
    "da": {
        "ticket-reply": "[#{ticket_number}] {ticket_subject}",
        "ticket-received": "[#{ticket_number}] Vi har modtaget din henvendelse",
        "ticket-access": "Dine samtaler med {organization_name}",
    },
}
