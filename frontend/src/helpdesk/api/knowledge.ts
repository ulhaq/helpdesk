import { apiClient } from '@/platform/api/client'
import type { PaginatedResponse } from '@/platform/types'
import type {
  KnowledgeDocument,
  KnowledgeDocumentIn,
  KnowledgeDocumentPatch,
  KnowledgeDocumentSummary,
  KnowledgeSearchIn,
  KnowledgeSearchOut,
} from '@/helpdesk/types/knowledge'

type ListParams = Record<string, string | number | undefined>

export const knowledgeApi = {
  listDocuments(params: ListParams = {}) {
    return apiClient.get<PaginatedResponse<KnowledgeDocumentSummary>>('/knowledge/documents', {
      params,
    })
  },

  getDocument(id: number) {
    return apiClient.get<KnowledgeDocument>(`/knowledge/documents/${id}`)
  },

  createDocument(data: KnowledgeDocumentIn) {
    return apiClient.post<KnowledgeDocument>('/knowledge/documents', data)
  },

  uploadDocument(file: File, title?: string) {
    const form = new FormData()
    form.append('file', file)
    if (title) form.append('title', title)
    return apiClient.post<KnowledgeDocument>('/knowledge/documents/upload', form)
  },

  patchDocument(id: number, data: KnowledgeDocumentPatch) {
    return apiClient.patch<KnowledgeDocument>(`/knowledge/documents/${id}`, data)
  },

  removeDocument(id: number) {
    return apiClient.delete(`/knowledge/documents/${id}`)
  },

  search(data: KnowledgeSearchIn) {
    return apiClient.post<KnowledgeSearchOut>('/knowledge/search', data)
  },
}
