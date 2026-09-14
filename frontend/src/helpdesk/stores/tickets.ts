import { ref } from 'vue'
import { defineStore } from 'pinia'
import { ticketsApi } from '@/helpdesk/api/tickets'
import type { PaginatedResponse } from '@/platform/types'
import type {
  ReplySuggestion,
  TicketDetailOut,
  TicketIn,
  TicketMessageIn,
  TicketMessageOut,
  TicketOut,
  TicketPatch,
} from '@/helpdesk/types/ticket'

type ListParams = Record<string, string | number | undefined>

// Gateway store for tickets: components never import `@/helpdesk/api/tickets`
// directly. List state lives in `useDataTable`; `current` is the ticket open in
// the detail view, kept in sync by every action that changes it.
export const useTicketsStore = defineStore('tickets', () => {
  const current = ref<TicketDetailOut | null>(null)

  async function list(params: ListParams = {}): Promise<PaginatedResponse<TicketOut>> {
    const { data: tickets } = await ticketsApi.list(params)
    return tickets
  }

  async function load(id: number): Promise<TicketDetailOut> {
    if (current.value?.id !== id) current.value = null
    const { data: ticket } = await ticketsApi.get(id)
    current.value = ticket
    return ticket
  }

  async function create(data: TicketIn): Promise<TicketDetailOut> {
    const { data: ticket } = await ticketsApi.create(data)
    current.value = ticket
    return ticket
  }

  function mergeIntoCurrent(ticket: TicketOut): void {
    if (current.value?.id === ticket.id) {
      current.value = { ...current.value, ...ticket }
    }
  }

  async function patch(id: number, data: TicketPatch): Promise<TicketOut> {
    const { data: ticket } = await ticketsApi.patch(id, data)
    mergeIntoCurrent(ticket)
    return ticket
  }

  async function assign(id: number, assigneeId: number | null): Promise<TicketOut> {
    const { data: ticket } = await ticketsApi.assign(id, assigneeId)
    mergeIntoCurrent(ticket)
    return ticket
  }

  async function reply(id: number, data: TicketMessageIn): Promise<TicketMessageOut> {
    const { data: message } = await ticketsApi.reply(id, data)
    // A public reply also moves the status and response timestamps server-side,
    // so reload the whole ticket rather than only appending the message.
    if (current.value?.id === id) await load(id)
    return message
  }

  // Whether the backend has Claude configured for reply drafts.
  const assistantEnabled = ref(false)

  async function loadAssistantStatus(): Promise<boolean> {
    const { data } = await ticketsApi.assistantStatus()
    assistantEnabled.value = data.enabled
    return data.enabled
  }

  async function suggestReply(id: number): Promise<ReplySuggestion> {
    const { data } = await ticketsApi.suggestReply(id)
    return data
  }

  async function remove(id: number): Promise<void> {
    await ticketsApi.remove(id)
    if (current.value?.id === id) current.value = null
  }

  return {
    current,
    assistantEnabled,
    list,
    load,
    create,
    patch,
    assign,
    reply,
    loadAssistantStatus,
    suggestReply,
    remove,
  }
})
