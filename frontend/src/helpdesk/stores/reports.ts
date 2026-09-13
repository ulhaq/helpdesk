import { ref } from 'vue'
import { defineStore } from 'pinia'
import { reportsApi } from '@/helpdesk/api/reports'
import type { ReportSummary } from '@/helpdesk/types/reports'

// Gateway store for support reports. The last summary is kept so a period
// change can hold the previous render while the next one loads.
export const useReportsStore = defineStore('reports', () => {
  const summary = ref<ReportSummary | null>(null)

  async function load(days: number): Promise<ReportSummary> {
    const { data } = await reportsApi.summary(days)
    summary.value = data
    return data
  }

  return { summary, load }
})
