// Shared UI types and language/pipeline constants for LayoutLingua.
export type Block =
  | { kind: 'h'; id: string; en?: string; vi?: string }
  | { kind: 'p'; id: string; en?: string; vi?: string }
  | { kind: 'eq'; id: string; tex: string; no: string }
  | { kind: 'table'; id: string; caption: [string, string]; head: [string, string][]; rows: [string, string][][] }
  | { kind: 'fig'; id: string; caption: [string, string] }
  | { kind: 'title'; id: string; en?: string; vi?: string; authors?: string }

export type PageStatus = 'ok' | 'warn' | 'fallback' | 'pending'
export type Page = {
  n: number
  status: PageStatus
  blocks: Block[]
  blockCount: number
  cellCount: number
}

export type Severity = 'info' | 'warning' | 'failure'
export type Issue = {
  id: string
  severity: Severity
  page: number
  region?: string
  title: string
  detail: string
  next: string
  action: string
  code: string
}

export const pages: Page[] = []

export const issues: Issue[] = []

export const stages = [
  'Reading document structure',
  'Detecting tables and formulas',
  'Translating text blocks',
  'Fitting text to layout',
  'Writing output PDF',
]

export const languages = [
  'English',
  'Vietnamese',
  'Chinese (Simplified)',
  'Chinese (Traditional)',
  'Japanese',
  'Korean',
  'French',
  'German',
  'Spanish',
  'Russian',
  'Italian',
  'Portuguese',
  'Indonesian',
  'Dutch',
  'Polish',
  'Turkish',
  'Ukrainian',
]

