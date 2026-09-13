import { ref } from 'vue'
import { defineStore } from 'pinia'
import { helpCenterApi } from '@/helpdesk/api/helpCenter'
import type { HelpArticle, HelpCenter, HelpSearch } from '@/helpdesk/types/kb'

// Gateway store for the public help center. `center` (name, branding,
// categories) frames every help center page, so it is fetched once per site.
export const useHelpCenterStore = defineStore('helpCenter', () => {
  const center = ref<HelpCenter | null>(null)
  const centerSlug = ref<string | null>(null)

  async function loadHome(slug: string): Promise<HelpCenter> {
    if (centerSlug.value !== slug) {
      center.value = null
      centerSlug.value = null
    }
    const { data } = await helpCenterApi.home(slug)
    center.value = data
    centerSlug.value = slug
    return data
  }

  async function ensureHome(slug: string): Promise<HelpCenter> {
    if (center.value && centerSlug.value === slug) return center.value
    return loadHome(slug)
  }

  async function search(
    slug: string,
    params: { q?: string; category?: string },
  ): Promise<HelpSearch> {
    const { data } = await helpCenterApi.search(slug, params)
    return data
  }

  async function article(slug: string, articleSlug: string): Promise<HelpArticle> {
    const { data } = await helpCenterApi.article(slug, articleSlug)
    return data
  }

  return { center, loadHome, ensureHome, search, article }
})
