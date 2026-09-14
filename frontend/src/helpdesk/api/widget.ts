import { publicClient as widgetClient } from '@/helpdesk/api/publicClient'
import type {
  WidgetAccessLinkIn,
  WidgetAnswer,
  WidgetConfig,
  WidgetMessage,
  WidgetTicketCreated,
  WidgetTicketDetail,
  WidgetTicketIn,
  WidgetTicketList,
} from '@/helpdesk/types/widget'

const sitePath = (slug: string) => `/widget/${encodeURIComponent(slug)}`
const asContact = (token: string) => ({ headers: { 'X-Contact-Token': token } })

export const widgetApi = {
  config(slug: string) {
    return widgetClient.get<WidgetConfig>(sitePath(slug))
  },

  createTicket(slug: string, data: WidgetTicketIn) {
    return widgetClient.post<WidgetTicketCreated>(`${sitePath(slug)}/tickets`, data)
  },

  requestAccessLink(slug: string, data: WidgetAccessLinkIn) {
    return widgetClient.post(`${sitePath(slug)}/access-link`, data)
  },

  listTickets(slug: string, token: string) {
    return widgetClient.get<WidgetTicketList>(`${sitePath(slug)}/tickets`, asContact(token))
  },

  getTicket(slug: string, token: string, id: number) {
    return widgetClient.get<WidgetTicketDetail>(`${sitePath(slug)}/tickets/${id}`, asContact(token))
  },

  answer(slug: string, question: string) {
    return widgetClient.post<WidgetAnswer>(`${sitePath(slug)}/answers`, { question })
  },

  reply(slug: string, token: string, id: number, body: string) {
    return widgetClient.post<WidgetMessage>(
      `${sitePath(slug)}/tickets/${id}/messages`,
      { body },
      asContact(token),
    )
  },
}
