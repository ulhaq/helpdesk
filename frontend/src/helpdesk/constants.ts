import type { TicketPriority, TicketStatus } from '@/helpdesk/types/ticket'

/** Plan setting keys the helpdesk enforces (mirrors `HelpdeskUsageMetric`). */
export const HelpdeskUsageMetric = {
  TICKETS_PER_MONTH: 'tickets_per_month',
} as const

export const TICKET_STATUSES: TicketStatus[] = ['open', 'pending', 'resolved', 'closed']

export const TICKET_PRIORITIES: TicketPriority[] = ['low', 'normal', 'high', 'urgent']
