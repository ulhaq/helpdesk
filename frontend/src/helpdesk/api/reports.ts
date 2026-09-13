import { apiClient } from '@/platform/api/client'
import type { ReportSummary } from '@/helpdesk/types/reports'

export const reportsApi = {
  summary(days: number) {
    return apiClient.get<ReportSummary>('/reports/summary', { params: { days } })
  },
}
