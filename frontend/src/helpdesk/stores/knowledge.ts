import { defineStore } from 'pinia'
import { knowledgeApi } from '@/helpdesk/api/knowledge'
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

// Gateway store for internal knowledge documents - team-only context for AI
// reply drafts. Lists live in `useDataTable`, so nothing is cached here.
export const useKnowledgeStore = defineStore('knowledge', () => {
  async function listDocuments(
    params: ListParams = {},
  ): Promise<PaginatedResponse<KnowledgeDocumentSummary>> {
    const { data } = await knowledgeApi.listDocuments(params)
    return data
  }

  async function getDocument(id: number): Promise<KnowledgeDocument> {
    const { data } = await knowledgeApi.getDocument(id)
    return data
  }

  async function createDocument(input: KnowledgeDocumentIn): Promise<KnowledgeDocument> {
    const { data } = await knowledgeApi.createDocument(input)
    return data
  }

  async function uploadDocument(file: File, title?: string): Promise<KnowledgeDocument> {
    const { data } = await knowledgeApi.uploadDocument(file, title)
    return data
  }

  async function patchDocument(
    id: number,
    input: KnowledgeDocumentPatch,
  ): Promise<KnowledgeDocument> {
    const { data } = await knowledgeApi.patchDocument(id, input)
    return data
  }

  async function removeDocument(id: number): Promise<void> {
    await knowledgeApi.removeDocument(id)
  }

  async function search(input: KnowledgeSearchIn): Promise<KnowledgeSearchOut> {
    const { data } = await knowledgeApi.search(input)
    return data
  }

  return {
    listDocuments,
    getDocument,
    createDocument,
    uploadDocument,
    patchDocument,
    removeDocument,
    search,
  }
})
