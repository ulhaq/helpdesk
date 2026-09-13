import { apiClient } from '@/platform/api/client'
import type { PaginatedResponse } from '@/platform/types'
import type {
  KbArticle,
  KbArticleIn,
  KbArticlePatch,
  KbArticleSummary,
  KbCategory,
  KbCategoryIn,
  KbCategoryPatch,
} from '@/helpdesk/types/kb'

type ListParams = Record<string, string | number | undefined>

export const kbApi = {
  listCategories() {
    return apiClient.get<KbCategory[]>('/kb/categories')
  },

  createCategory(data: KbCategoryIn) {
    return apiClient.post<KbCategory>('/kb/categories', data)
  },

  patchCategory(id: number, data: KbCategoryPatch) {
    return apiClient.patch<KbCategory>(`/kb/categories/${id}`, data)
  },

  removeCategory(id: number) {
    return apiClient.delete(`/kb/categories/${id}`)
  },

  listArticles(params: ListParams = {}) {
    return apiClient.get<PaginatedResponse<KbArticleSummary>>('/kb/articles', { params })
  },

  getArticle(id: number) {
    return apiClient.get<KbArticle>(`/kb/articles/${id}`)
  },

  createArticle(data: KbArticleIn) {
    return apiClient.post<KbArticle>('/kb/articles', data)
  },

  patchArticle(id: number, data: KbArticlePatch) {
    return apiClient.patch<KbArticle>(`/kb/articles/${id}`, data)
  },

  removeArticle(id: number) {
    return apiClient.delete(`/kb/articles/${id}`)
  },

  preview(body: string) {
    return apiClient.post<{ html: string }>('/kb/articles/preview', { body })
  },
}
