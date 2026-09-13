import { publicClient } from '@/helpdesk/api/publicClient'
import type { HelpArticle, HelpCenter, HelpSearch } from '@/helpdesk/types/kb'

const sitePath = (slug: string) => `/help/${encodeURIComponent(slug)}`

export const helpCenterApi = {
  home(slug: string) {
    return publicClient.get<HelpCenter>(sitePath(slug))
  },

  search(slug: string, params: { q?: string; category?: string }) {
    return publicClient.get<HelpSearch>(`${sitePath(slug)}/articles`, { params })
  },

  article(slug: string, articleSlug: string) {
    return publicClient.get<HelpArticle>(
      `${sitePath(slug)}/articles/${encodeURIComponent(articleSlug)}`,
    )
  },
}
