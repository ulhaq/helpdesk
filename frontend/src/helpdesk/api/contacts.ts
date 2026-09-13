import { apiClient } from '@/platform/api/client'
import type { PaginatedResponse } from '@/platform/types'
import type { ContactIn, ContactOut, ContactPatch } from '@/helpdesk/types/contact'

type ListParams = Record<string, string | number | undefined>

export const contactsApi = {
  list(params: ListParams = {}) {
    return apiClient.get<PaginatedResponse<ContactOut>>('/contacts', { params })
  },

  get(id: number) {
    return apiClient.get<ContactOut>(`/contacts/${id}`)
  },

  create(data: ContactIn) {
    return apiClient.post<ContactOut>('/contacts', data)
  },

  patch(id: number, data: ContactPatch) {
    return apiClient.patch<ContactOut>(`/contacts/${id}`, data)
  },

  remove(id: number) {
    return apiClient.delete(`/contacts/${id}`)
  },
}
