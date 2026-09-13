import { ref } from 'vue'
import { defineStore } from 'pinia'
import { kbApi } from '@/helpdesk/api/kb'
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

// Gateway store for the knowledge base. Categories are few and shown in
// several places (filters, editor, manager), so they are cached here; article
// lists live in `useDataTable`.
export const useKbStore = defineStore('kb', () => {
  const categories = ref<KbCategory[]>([])

  async function loadCategories(): Promise<KbCategory[]> {
    const { data } = await kbApi.listCategories()
    categories.value = data
    return data
  }

  async function createCategory(data: KbCategoryIn): Promise<KbCategory> {
    const { data: category } = await kbApi.createCategory(data)
    await loadCategories()
    return category
  }

  async function patchCategory(id: number, data: KbCategoryPatch): Promise<KbCategory> {
    const { data: category } = await kbApi.patchCategory(id, data)
    await loadCategories()
    return category
  }

  async function removeCategory(id: number): Promise<void> {
    await kbApi.removeCategory(id)
    categories.value = categories.value.filter((category) => category.id !== id)
  }

  async function listArticles(
    params: ListParams = {},
  ): Promise<PaginatedResponse<KbArticleSummary>> {
    const { data } = await kbApi.listArticles(params)
    return data
  }

  async function getArticle(id: number): Promise<KbArticle> {
    const { data } = await kbApi.getArticle(id)
    return data
  }

  async function createArticle(data: KbArticleIn): Promise<KbArticle> {
    const { data: article } = await kbApi.createArticle(data)
    return article
  }

  async function patchArticle(id: number, data: KbArticlePatch): Promise<KbArticle> {
    const { data: article } = await kbApi.patchArticle(id, data)
    return article
  }

  async function removeArticle(id: number): Promise<void> {
    await kbApi.removeArticle(id)
  }

  async function preview(body: string): Promise<string> {
    const { data } = await kbApi.preview(body)
    return data.html
  }

  return {
    categories,
    loadCategories,
    createCategory,
    patchCategory,
    removeCategory,
    listArticles,
    getArticle,
    createArticle,
    patchArticle,
    removeArticle,
    preview,
  }
})
