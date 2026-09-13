import { apiClient } from '@/platform/api/client'
import type { SupportSite, SupportSitePatch } from '@/helpdesk/types/supportSite'

export const supportSiteApi = {
  get() {
    return apiClient.get<SupportSite>('/helpdesk/support-site')
  },

  patch(data: SupportSitePatch) {
    return apiClient.patch<SupportSite>('/helpdesk/support-site', data)
  },
}
