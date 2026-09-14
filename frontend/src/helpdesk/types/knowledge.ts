export type KnowledgeDocumentSource = 'text' | 'file'
/** How the text is split for the AI assistant: at headings, or in windows. */
export type TextFormat = 'markdown' | 'plain'

export interface KnowledgeDocumentSummary {
  id: number
  title: string
  source: KnowledgeDocumentSource
  filename: string | null
  size_bytes: number | null
  format: TextFormat
  created_at: string
  updated_at: string
}

export interface KnowledgeDocument extends KnowledgeDocumentSummary {
  author_id: number | null
  content_type: string | null
  /** Pasted text, or the text extracted from the uploaded file. */
  text: string
}

export interface KnowledgeDocumentIn {
  title: string
  text: string
}

export type KnowledgeDocumentPatch = Partial<KnowledgeDocumentIn>

export interface KnowledgeSearchIn {
  query: string
  /** False searches what widget answers may use: published articles only. */
  include_internal: boolean
}

/** `off`: no embedding model configured; `unavailable`: it failed just now. */
export type SemanticSearchStatus = 'off' | 'ok' | 'unavailable'

export interface KnowledgeSearchResult {
  chunk_id: number
  source_type: 'article' | 'document'
  source_id: number
  title: string
  slug: string | null
  heading: string
  excerpt: string
  score: number
  keyword_rank: number | null
  semantic_rank: number | null
  /** Cosine distance to the question: 0 identical, 2 opposite. */
  distance: number | null
  /** Whether a searched AI request would pass this section on to the AI. */
  selected: boolean
}

export interface KnowledgeSearchOut {
  terms: string[]
  /** The knowledge base is small enough that AI requests receive all of it. */
  sends_everything: boolean
  semantic: SemanticSearchStatus
  max_distance: number
  pending_embeddings: number
  results: KnowledgeSearchResult[]
}

/** File types the upload endpoint accepts. */
export const KNOWLEDGE_FILE_TYPES = '.txt,.md,.markdown,.pdf,.docx'
