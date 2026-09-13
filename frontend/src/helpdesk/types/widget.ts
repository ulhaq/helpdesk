import type { TicketStatus } from '@/helpdesk/types/ticket'
import type { SupportedLocale } from '@/plugins/i18n'

export interface WidgetConfig {
  organization_name: string
  brand_color: string
  greeting: string | null
  help_center_enabled: boolean
}

export interface WidgetMessage {
  id: number
  author_type: 'agent' | 'contact'
  author_name: string | null
  body: string
  created_at: string
}

export interface WidgetTicket {
  id: number
  number: number
  subject: string
  status: TicketStatus
  created_at: string
  last_message_at: string
}

export interface WidgetTicketDetail extends WidgetTicket {
  messages: WidgetMessage[]
}

export interface WidgetTicketList {
  contact_name: string
  tickets: WidgetTicket[]
}

export interface WidgetTicketCreated {
  ticket: WidgetTicketDetail
  /** Opens this ticket only - the browser has not proven it owns the email. */
  access_token: string
}

export interface WidgetTicketIn {
  name: string
  email: string
  subject: string
  body: string
  locale?: SupportedLocale
}

export interface WidgetAccessLinkIn {
  email: string
  locale?: SupportedLocale
}
