import { registerNotificationPresenter } from '@/platform/composables/useNotificationPresenter'

/** Payload written by `TicketService._notify_assignee` on the backend. */
interface TicketAssignedPayload {
  ticket_id: number
  number: number
  subject: string
  assigned_by: string
}

const asPayload = (payload: unknown) => payload as TicketAssignedPayload

registerNotificationPresenter('ticket_assigned', {
  getTitle: (payload, t) =>
    t('notifications.ticketAssigned.title', { number: asPayload(payload).number }),
  getDescription: (payload, t) => {
    const { assigned_by, subject } = asPayload(payload)
    return t('notifications.ticketAssigned.description', { assignedBy: assigned_by, subject })
  },
  getRoute: (payload) => `/tickets/${asPayload(payload).ticket_id}`,
  getAvatarSeed: (payload) => asPayload(payload).assigned_by,
})
