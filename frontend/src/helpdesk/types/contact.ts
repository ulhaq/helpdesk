import type { SupportedLocale } from '@/plugins/i18n'

export interface ContactSummary {
  id: number
  name: string
  email: string
}

export interface ContactOut extends ContactSummary {
  organization_id: number
  locale: SupportedLocale | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ContactIn {
  name: string
  email: string
  locale?: SupportedLocale | null
  notes?: string | null
}

export type ContactPatch = Partial<ContactIn>
