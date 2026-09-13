export interface SupportSite {
  slug: string
  brand_color: string
  greeting: string | null
  widget_enabled: boolean
  help_center_enabled: boolean
  updated_at: string
}

export interface SupportSitePatch {
  slug?: string
  brand_color?: string
  /** null clears the greeting. */
  greeting?: string | null
  widget_enabled?: boolean
  help_center_enabled?: boolean
}
