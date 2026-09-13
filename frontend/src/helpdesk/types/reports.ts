export interface CountByKey {
  key: string
  count: number
}

export interface DurationStats {
  median_seconds: number | null
  average_seconds: number | null
  sample_size: number
}

export interface DailyVolume {
  /** ISO date (YYYY-MM-DD), UTC. */
  day: string
  created: number
  resolved: number
}

export interface AgentWorkload {
  user_id: number
  name: string
  open: number
  resolved: number
}

export interface ReportSummary {
  period_days: number
  since: string
  created: number
  resolved: number
  backlog: number
  unassigned_backlog: number
  first_response: DurationStats
  resolution: DurationStats
  by_status: CountByKey[]
  by_channel: CountByKey[]
  by_priority: CountByKey[]
  daily: DailyVolume[]
  agents: AgentWorkload[]
}
