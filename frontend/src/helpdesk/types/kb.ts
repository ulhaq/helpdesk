export type ArticleStatus = 'draft' | 'published'

export interface KbCategory {
  id: number
  name: string
  slug: string
  description: string | null
  position: number
  created_at: string
  updated_at: string
}

export interface KbCategoryIn {
  name: string
  /** Generated from the name when omitted. */
  slug?: string
  description?: string | null
  position?: number
}

export type KbCategoryPatch = Partial<KbCategoryIn>

export interface KbCategoryRef {
  id: number
  name: string
  slug: string
}

export interface KbArticleSummary {
  id: number
  title: string
  slug: string
  status: ArticleStatus
  published_at: string | null
  category: KbCategoryRef | null
  created_at: string
  updated_at: string
}

export interface KbArticle extends KbArticleSummary {
  /** Markdown source. */
  body: string
  category_id: number | null
  author_id: number | null
}

export interface KbArticleIn {
  title: string
  /** Generated from the title when omitted. */
  slug?: string
  body?: string
  category_id?: number | null
  status?: ArticleStatus
}

export type KbArticlePatch = Partial<KbArticleIn>

// --- public help center

export interface HelpCategory {
  name: string
  slug: string
  description: string | null
  article_count: number
}

export interface HelpCategoryRef {
  name: string
  slug: string
}

export interface HelpArticleSummary {
  title: string
  slug: string
  excerpt: string
  category: HelpCategoryRef | null
  updated_at: string
}

export interface HelpArticle {
  title: string
  slug: string
  /** Rendered server-side from Markdown with raw HTML disabled. */
  html: string
  category: HelpCategoryRef | null
  published_at: string | null
  updated_at: string
}

export interface HelpCenter {
  organization_name: string
  brand_color: string
  widget_enabled: boolean
  categories: HelpCategory[]
  recent_articles: HelpArticleSummary[]
}

export interface HelpSearch {
  category: HelpCategoryRef | null
  articles: HelpArticleSummary[]
}
