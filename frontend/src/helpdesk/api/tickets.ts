import { apiClient } from '@/platform/api/client'
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

export const ticketsApi = {
  list(params: ListParams = {}) {
    return apiClient.get<PaginatedResponse<TicketOut>>('/tickets', { params })
  },

  get(id: number) {
    return apiClient.get<TicketDetailOut>(`/tickets/${id}`)
  },

  create(data: TicketIn) {
    return apiClient.post<TicketDetailOut>('/tickets', data)
  },

  patch(id: number, data: TicketPatch) {
    return apiClient.patch<TicketOut>(`/tickets/${id}`, data)
  },

  assign(id: number, assigneeId: number | null) {
    return apiClient.put<TicketOut>(`/tickets/${id}/assignee`, { assignee_id: assigneeId })
  },

  reply(id: number, data: TicketMessageIn) {
    return apiClient.post<TicketMessageOut>(`/tickets/${id}/messages`, data)
  },

  suggestReply(id: number) {
    return apiClient.post<ReplySuggestion>(`/tickets/${id}/reply-suggestion`)
  },

  assistantStatus() {
    return apiClient.get<{ enabled: boolean }>('/helpdesk/assistant')
  },

  remove(id: number) {
    return apiClient.delete(`/tickets/${id}`)
  },
}
