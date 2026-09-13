import type { ContactIn, ContactSummary } from '@/helpdesk/types/contact'

export type TicketStatus = 'open' | 'pending' | 'resolved' | 'closed'
export type TicketPriority = 'low' | 'normal' | 'high' | 'urgent'
export type TicketChannel = 'agent' | 'widget'

export interface UserSummary {
  id: number
  name: string
}

export interface TicketOut {
  id: number
  organization_id: number
  number: number
  subject: string
  status: TicketStatus
  priority: TicketPriority
  channel: TicketChannel
  contact: ContactSummary
  assignee: UserSummary | null
  first_response_at: string | null
  resolved_at: string | null
  closed_at: string | null
  last_message_at: string
  created_at: string
  updated_at: string
}

export interface TicketMessageOut {
  id: number
  ticket_id: number
  author_type: 'agent' | 'contact'
  author_user_id: number | null
  author_contact_id: number | null
  author_name: string | null
  body: string
  is_internal: boolean
  created_at: string
}

export interface TicketDetailOut extends TicketOut {
  messages: TicketMessageOut[]
}

export interface TicketIn {
  subject: string
  body: string
  priority?: TicketPriority
  /** Exactly one of `contact_id` or `contact` (matched by email, created when new). */
  contact_id?: number
  contact?: ContactIn
  assignee_id?: number | null
}

export interface TicketPatch {
  subject?: string
  status?: TicketStatus
  priority?: TicketPriority
}

export interface TicketMessageIn {
  body: string
  is_internal?: boolean
}
