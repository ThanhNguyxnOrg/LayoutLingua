/**
 * Document & Translation Domain Types for LayoutLingua Desktop
 */

export type PageStatus = 'original' | 'translated' | 'review' | 'failed' | 'pending'
export type Severity = 'low' | 'med' | 'high'
export type Phase = 'idle' | 'processing' | 'done' | 'provider-error' | 'cancelled'
export type StageId = 'extract' | 'layout' | 'translate' | 'typeset' | 'verify'

export interface Page {
  n: number
  status: PageStatus
  issues: number
  words: number
  engine: string
}

export interface Issue {
  id: string
  page: number
  title: string
  sub: string
  sev: Severity
  bbox: [number, number, number, number] // [x0, y0, x1, y1]
  code: string
  context?: string
}

export interface Stage {
  id: StageId
  label: string
  desc: string
}

export interface LanguageOption {
  code: string
  label: string
  tier: string
}

export interface DocumentInfo {
  name: string
  size: number
  pageCount: number
  wordCount: number
  detectedLang: string
  isEncrypted: boolean
}

export interface TranslationProgress {
  phase: Phase
  currentPage: number
  totalPages: number
  percent: number
  currentStage: StageId
  pageStatusMap: Record<number, PageStatus>
  message?: string
}

export interface TranslationOptions {
  sourceLang: string
  targetLang: string
  provider: 'auto' | 'google' | 'argos' | 'gemini' | 'openai'
  formulaHandling: 'preserve' | 'translate'
  preserveFormatting: boolean
}

export interface ExportOptions {
  format: 'dual' | 'translated-only' | 'side-by-side'
  includeTelemetry: boolean
  outputPath?: string
}
