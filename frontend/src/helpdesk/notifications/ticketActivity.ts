import { registerNotificationPresenter } from '@/platform/composables/useNotificationPresenter'

/** Payload written by `notify_agents` on the backend for customer activity. */
interface TicketActivityPayload {
  ticket_id: number
  number: number
  subject: string
  contact_name: string
}

const asPayload = (payload: unknown) => payload as TicketActivityPayload

for (const [type, titleKey] of [
  ['ticket_created', 'notifications.ticketCreated.title'],
  ['ticket_customer_replied', 'notifications.ticketCustomerReplied.title'],
] as const) {
  registerNotificationPresenter(type, {
    getTitle: (payload, t) => {
      const { number, contact_name } = asPayload(payload)
      return t(titleKey, { number, contactName: contact_name })
    },
    getDescription: (payload) => asPayload(payload).subject,
    getRoute: (payload) => `/tickets/${asPayload(payload).ticket_id}`,
    getAvatarSeed: (payload) => asPayload(payload).contact_name,
  })
}
