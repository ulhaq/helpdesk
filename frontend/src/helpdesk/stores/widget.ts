import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { isAxiosError } from 'axios'
import { widgetApi } from '@/helpdesk/api/widget'
import type { SupportedLocale } from '@/plugins/i18n'
import type {
  WidgetConfig,
  WidgetTicket,
  WidgetTicketDetail,
  WidgetTicketIn,
} from '@/helpdesk/types/widget'

interface StoredAccess {
  /** From an emailed link: opens all of the contact's conversations. */
  contactToken: string | null
  /** From tickets submitted in this browser: each opens one ticket. */
  ticketTokens: Record<string, string>
}

const storageKey = (slug: string) => `helpdesk-widget:${slug}`

function readStoredAccess(slug: string): StoredAccess {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey(slug)) ?? 'null')
    if (parsed && typeof parsed === 'object') {
      return {
        contactToken: typeof parsed.contactToken === 'string' ? parsed.contactToken : null,
        ticketTokens:
          parsed.ticketTokens && typeof parsed.ticketTokens === 'object' ? parsed.ticketTokens : {},
      }
    }
  } catch {
    // Storage can be unavailable in an embedded frame (blocked third-party
    // storage); the widget then works for the current visit only.
  }
  return { contactToken: null, ticketTokens: {} }
}

const isUnauthorized = (err: unknown) => isAxiosError(err) && err.response?.status === 401

// Gateway store for the customer-facing widget. Customers have no account:
// access comes from contact tokens issued by the API, remembered per support
// site in localStorage.
export const useWidgetStore = defineStore('widget', () => {
  const slug = ref('')
  const config = ref<WidgetConfig | null>(null)
  const contactToken = ref<string | null>(null)
  const ticketTokens = ref<Record<string, string>>({})
  const tickets = ref<WidgetTicket[]>([])
  const current = ref<WidgetTicketDetail | null>(null)

  const canFindConversations = computed(() => contactToken.value === null)

  function persist(): void {
    try {
      localStorage.setItem(
        storageKey(slug.value),
        JSON.stringify({ contactToken: contactToken.value, ticketTokens: ticketTokens.value }),
      )
    } catch {
      // See readStoredAccess.
    }
  }

  function tokenFor(ticketId: number): string | null {
    return contactToken.value ?? ticketTokens.value[String(ticketId)] ?? null
  }

  function forget(token: string): void {
    if (contactToken.value === token) contactToken.value = null
    ticketTokens.value = Object.fromEntries(
      Object.entries(ticketTokens.value).filter(([, value]) => value !== token),
    )
    persist()
  }

  async function init(siteSlug: string): Promise<WidgetConfig> {
    slug.value = siteSlug
    const stored = readStoredAccess(siteSlug)
    contactToken.value = stored.contactToken
    ticketTokens.value = stored.ticketTokens
    const { data } = await widgetApi.config(siteSlug)
    config.value = data
    return data
  }

  function acceptContactToken(token: string): void {
    contactToken.value = token
    persist()
  }

  async function loadTickets(): Promise<void> {
    const tokens = contactToken.value
      ? [contactToken.value]
      : [...new Set(Object.values(ticketTokens.value))]
    const found = new Map<number, WidgetTicket>()
    for (const token of tokens) {
      try {
        const { data } = await widgetApi.listTickets(slug.value, token)
        for (const ticket of data.tickets) found.set(ticket.id, ticket)
      } catch (err: unknown) {
        // Expired or revoked (e.g. the contact was deleted): drop it quietly.
        if (!isUnauthorized(err)) throw err
        forget(token)
      }
    }
    tickets.value = [...found.values()].sort((a, b) =>
      b.last_message_at.localeCompare(a.last_message_at),
    )
  }

  async function openTicket(id: number): Promise<WidgetTicketDetail> {
    const token = tokenFor(id)
    if (!token) throw new Error(`No access to ticket ${id}`)
    const { data } = await widgetApi.getTicket(slug.value, token, id)
    current.value = data
    return data
  }

  async function createTicket(payload: WidgetTicketIn): Promise<WidgetTicketDetail> {
    const { data } = await widgetApi.createTicket(slug.value, payload)
    ticketTokens.value = { ...ticketTokens.value, [String(data.ticket.id)]: data.access_token }
    persist()
    current.value = data.ticket
    return data.ticket
  }

  async function reply(body: string): Promise<void> {
    const ticket = current.value
    const token = ticket ? tokenFor(ticket.id) : null
    if (!ticket || !token) return
    await widgetApi.reply(slug.value, token, ticket.id, body)
    // Replying can reopen the ticket server-side, so reload it.
    await openTicket(ticket.id)
  }

  async function requestAccessLink(email: string, locale?: SupportedLocale): Promise<void> {
    await widgetApi.requestAccessLink(slug.value, { email, locale })
  }

  return {
    config,
    tickets,
    current,
    canFindConversations,
    init,
    acceptContactToken,
    loadTickets,
    openTicket,
    createTicket,
    reply,
    requestAccessLink,
  }
})
