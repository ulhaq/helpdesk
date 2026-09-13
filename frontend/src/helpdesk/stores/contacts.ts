import { defineStore } from 'pinia'
import { contactsApi } from '@/helpdesk/api/contacts'
import type { PaginatedResponse } from '@/platform/types'
import type { ContactIn, ContactOut, ContactPatch } from '@/helpdesk/types/contact'

type ListParams = Record<string, string | number | undefined>

// Gateway store for contacts: components never import `@/helpdesk/api/contacts`
// directly. List state lives in `useDataTable`, so this store holds no cache.
export const useContactsStore = defineStore('contacts', () => {
  async function list(params: ListParams = {}): Promise<PaginatedResponse<ContactOut>> {
    const { data: contacts } = await contactsApi.list(params)
    return contacts
  }

  async function get(id: number): Promise<ContactOut> {
    const { data: contact } = await contactsApi.get(id)
    return contact
  }

  async function create(data: ContactIn): Promise<ContactOut> {
    const { data: contact } = await contactsApi.create(data)
    return contact
  }

  async function patch(id: number, data: ContactPatch): Promise<ContactOut> {
    const { data: contact } = await contactsApi.patch(id, data)
    return contact
  }

  async function remove(id: number): Promise<void> {
    await contactsApi.remove(id)
  }

  return { list, get, create, patch, remove }
})
