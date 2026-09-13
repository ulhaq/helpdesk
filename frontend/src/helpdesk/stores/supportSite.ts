import { ref } from 'vue'
import { defineStore } from 'pinia'
import { supportSiteApi } from '@/helpdesk/api/supportSite'
import type { SupportSite, SupportSitePatch } from '@/helpdesk/types/supportSite'

// Gateway store for the organization's support site (widget settings).
export const useSupportSiteStore = defineStore('supportSite', () => {
  const site = ref<SupportSite | null>(null)

  async function load(): Promise<SupportSite> {
    const { data } = await supportSiteApi.get()
    site.value = data
    return data
  }

  async function patch(data: SupportSitePatch): Promise<SupportSite> {
    const { data: updated } = await supportSiteApi.patch(data)
    site.value = updated
    return updated
  }

  return { site, load, patch }
})
