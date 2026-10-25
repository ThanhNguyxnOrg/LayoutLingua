import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { pages, issues, stages, languages, type Issue, type Page } from './data'
import PdfPage, { PAGE_W } from './PdfPage'
import { AppHeader } from './shell'
import ExportDialog from './ExportDialog'
import { Button, IconButton, IssueRow, ProgressBar, StateNotice, StatusIndicator, sevMeta, type DocState } from './ui'
import { IconAlert, IconCheck, IconChevL, IconChevR, IconColumns, IconDownload, IconError, IconFit, IconLayers, IconMinus, IconPanelR, IconPlus, IconSwap, IconX, IconFile, IconSettings, IconCopy } from './icons'
import { useSettings, type AppSettings, type ProviderType } from '../services/settings'
import { apiUrl } from '../services/api'
import { updateHistoryStatus } from '../services/history'

type Phase = 'idle' | 'processing' | 'done' | 'provider-error' | 'rate-limited' | 'cancelled'
type Tab = 'translation' | 'quality' | 'page'

/* ---------- Document navigator ---------- */
function PageNavigator({
  current,
  onSelect,
  known,
  pages: pageList,
  total,
  docId,
}: {
  current: number
  onSelect: (n: number) => void
  known: (p: Page) => Page['status'] | 'pending'
  pages: Page[]
  total: number
  docId?: string
}) {
  const itemRefs = useRef<Record<number, HTMLLIElement | null>>({})

  useEffect(() => {
    itemRefs.current[current]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [current])

  return (
    <aside aria-label="Pages" className="flex h-full max-h-full w-[138px] min-h-0 shrink-0 flex-col border-r border-line bg-white select-none overflow-hidden">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-line px-3 bg-canvas/30">
        <h2 className="text-[13px] font-bold">Pages</h2>
        <span className="font-mono text-[12px] text-muted">{current} / {total}</span>
      </div>
      <ol className="flex-1 min-h-0 space-y-3 px-2 py-4 select-none custom-scrollbar">
        {pageList.map((p) => {
          const s = known(p)
          const active = p.n === current
          return (
            <li key={p.n} ref={(el) => { itemRefs.current[p.n] = el }}>
              <button onClick={() => onSelect(p.n)} aria-current={active ? 'page' : undefined} aria-label={`Page ${p.n}${s === 'warn' ? ', needs review' : s === 'fallback' ? ', preserved from source' : ''}`} className="group flex w-full flex-col items-center gap-1.5 cursor-pointer">
                <span className={`relative block rounded-[2px] ring-offset-2 transition ${active ? 'ring-2 ring-teal' : 'ring-1 ring-line-strong group-hover:ring-faint'}`}>
                  <PdfPage page={p} type="source" width={92} showMarks={false} docId={docId} />
                </span>
                <span className={`flex items-center gap-1 font-mono text-[11.5px] ${active ? 'font-medium text-ink' : 'text-muted'}`}>
                  {p.n}
                  {s === 'warn' && <IconAlert className="size-3 text-amber" />}
                  {s === 'fallback' && <IconError className="size-3 text-red" />}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </aside>
  )
}

/* ---------- Comparison toolbar ---------- */
function ComparisonToolbar(props: {
  total: number
  page: number
  setPage: (n: number) => void
  zoomPct: number
  zoomIn: () => void
  zoomOut: () => void
  fit: () => void
  isFit: boolean
  mode: 'side' | 'overlay'
  setMode: (m: 'side' | 'overlay') => void
  inspectorOpen: boolean
  toggleInspector: () => void
}) {
  const { page, setPage, total, mode, setMode } = props
  return (
    <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-white px-3 overflow-x-auto min-w-0">
      <div className="flex shrink-0 items-center gap-0.5">
        <IconButton label="Previous page" disabled={page === 1} onClick={() => setPage(page - 1)} className="disabled:opacity-40"><IconChevL /></IconButton>
        <span className="min-w-[64px] text-center font-mono text-[12.5px]">{page} / {total}</span>
        <IconButton label="Next page" disabled={page === total} onClick={() => setPage(page + 1)} className="disabled:opacity-40"><IconChevR /></IconButton>
      </div>
      <span className="mx-1 h-5 w-px shrink-0 bg-line" />
      <div className="flex shrink-0 items-center gap-0.5">
        <IconButton label="Zoom out" onClick={props.zoomOut}><IconMinus /></IconButton>
        <span className="w-12 text-center font-mono text-[12.5px]">{props.zoomPct}%</span>
        <IconButton label="Zoom in" onClick={props.zoomIn}><IconPlus /></IconButton>
        <IconButton label="Fit to page" active={props.isFit} onClick={props.fit}><IconFit /></IconButton>
      </div>
      <span className="mx-1 h-5 w-px shrink-0 bg-line" />
      <div role="radiogroup" aria-label="Comparison mode" className="flex shrink-0 rounded-md border border-line p-0.5">
        {([['side', 'Side by side', IconColumns], ['overlay', 'Overlay', IconLayers]] as const).map(([m, l, I]) => (
          <button key={m} role="radio" aria-checked={mode === m} onClick={() => setMode(m)} className={`flex h-7 items-center gap-1.5 rounded px-2.5 text-[12.5px] font-semibold whitespace-nowrap ${mode === m ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}><I className="size-3.5 shrink-0" />{l}</button>
        ))}
      </div>
      <div className="ml-auto shrink-0">
        <IconButton label={props.inspectorOpen ? 'Collapse inspector' : 'Expand inspector'} active={props.inspectorOpen} onClick={props.toggleInspector}><IconPanelR /></IconButton>
      </div>
    </div>
  )
}

/* ---------- Page frame ---------- */
function PageFrame({ label, sub, width, children }: { label: string; sub: React.ReactNode; width: number; children: React.ReactNode }) {
  return (
    <figure className="flex flex-col gap-1.5">
      <figcaption className="flex h-5 items-center justify-between gap-2 text-[12.5px]" style={{ width }}>
        <span className="font-bold">{label}</span>
        <span className="flex min-w-0 items-center gap-1.5 truncate text-muted">{sub}</span>
      </figcaption>
      <div className="relative shadow-[0_0_0_1px_rgba(32,51,61,0.10),0_1px_3px_rgba(32,51,61,0.08)]">{children}</div>
    </figure>
  )
}

const stateMeta = {
  pending: { t: 'Pending', c: 'text-muted', I: null },
  ok: { t: 'Translated', c: 'text-teal', I: IconCheck },
  warn: { t: 'Needs review', c: 'text-amber-ink', I: IconAlert },
  fallback: { t: 'Preserved from source', c: 'text-red', I: IconError },
} as const
function PageState({ s, idle }: { s: keyof typeof stateMeta; idle?: boolean }) {
  const m = stateMeta[s]
  return <span className={`inline-flex items-center gap-1 font-semibold ${m.c}`}>{m.I && <m.I className="size-3.5" />}{s === 'pending' && idle ? 'Not translated' : m.t}</span>
}

function OutputPlaceholder({ width, height, title, body, busy }: { width: number; height: number; title: string; body: string; busy?: boolean }) {
  return (
    <div style={{ width, height }} className="flex flex-col items-center justify-center gap-2 bg-white px-8 text-center">
      <span className={`size-2 rounded-full ${busy ? 'bg-teal ll-pulse' : 'bg-line-strong'}`} />
      <p className="text-[14px] font-semibold">{title}</p>
      <p className="max-w-[240px] text-[12.5px] leading-relaxed text-muted">{body}</p>
    </div>
  )
}

/* ---------- Integrity strip ---------- */
function IntegrityStrip({
  known,
  done,
  total,
  phase,
  current,
  onSelect,
  pages: pageList,
  counts,
  rangeLabel,
}: {
  known: (p: Page) => Page['status'] | 'pending'
  done: number
  total: number
  phase: Phase
  current: number
  onSelect: (n: number) => void
  pages: Page[]
  counts: { blocks: number; cells: number; review: number; preserved: number }
  rangeLabel?: string
}) {
  const seg = { ok: 'bg-teal', warn: 'bg-amber', fallback: 'bg-red', pending: 'bg-line' }
  const isLarge = total > 24
  return (
    <section aria-label="Document integrity" className="flex h-14 shrink-0 items-center gap-6 border-t border-line bg-white px-4">
      <div className="w-[220px] shrink-0">
        <div className="mb-1.5 flex items-center justify-between text-[12px]">
          <span className="font-bold">Document integrity</span>
          <span className="font-mono text-muted">
            {phase === 'idle'
              ? 'not started'
              : rangeLabel
              ? `${done}/${total} verified (${rangeLabel})`
              : `${done}/${total} verified`}
          </span>
        </div>
        {isLarge ? (
          <div className="h-2.5 w-full overflow-hidden rounded-[2px] bg-line flex">
            <div className="h-full bg-teal transition-all duration-300" style={{ width: `${(done / total) * 100}%` }} />
          </div>
        ) : (
          <div className="flex gap-[3px]" role="list">
            {pageList.map((p) => {
              const s = known(p)
              return (
                <button key={p.n} role="listitem" onClick={() => onSelect(p.n)} aria-label={`Page ${p.n}: ${s === 'ok' ? 'translated' : s === 'warn' ? 'needs review' : s === 'fallback' ? 'preserved from source' : 'pending'}`} className={`relative h-2.5 flex-1 rounded-[2px] ${seg[s]} ${p.n === current ? 'outline-2 outline-offset-1 outline-ink' : ''}`}>
                  {s === 'warn' && <span className="absolute inset-0 rounded-[2px] bg-[repeating-linear-gradient(135deg,transparent_0_3px,rgba(255,255,255,.45)_3px_5px)]" />}
                </button>
              )
            })}
          </div>
        )}
      </div>
      <dl className="flex flex-1 items-center gap-6 text-[12.5px]">
        {[
          ['Translated', counts.blocks ? `${counts.blocks} blocks` : '—', <IconCheck key="c" className="size-3.5 text-teal" />],
          ['Needs review', String(counts.review), <IconAlert key="a" className="size-3.5 text-amber" />],
          ['Preserved from source', counts.preserved ? `${counts.preserved} page` : '0', <IconError key="e" className="size-3.5 text-red" />],
          ['Pending', `${Math.max(0, total - done)} pages`, <span key="p" className="size-2.5 rounded-[2px] bg-line" />],
        ].map(([l, v, i]) => (
          <div key={l as string} className="flex items-center gap-1.5">
            {i}<dt className="text-muted">{l}</dt><dd className="font-mono font-medium text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <span className="text-[11.5px] text-muted font-mono" title="Pipeline: PyMuPDF Document IR → TypesetEngine v2.0.0">Engine: PyMuPDF + TypesetEngine v2.0.0</span>
    </section>
  )
}

/* ---------- Inspector ---------- */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold">{label}{children}</label>
}
const selectCls = 'h-9 rounded-md border border-line-strong bg-white px-2.5 text-[13.5px] font-medium disabled:bg-canvas disabled:text-muted'

function ProcessingPanel({
  done,
  total,
  stage,
  onCancel,
  eta,
  speed,
  message,
  overallPct,
  subtitle,
}: {
  done: number
  total: number
  stage: number
  onCancel: () => void
  eta?: number
  speed?: number
  message?: string
  overallPct?: number | null
  subtitle?: string | null
}) {
  const [countdownSec, setCountdownSec] = useState<number | null>(eta ?? null)

  useEffect(() => {
    if (eta != null && eta > 0) {
      setCountdownSec((prev) => {
        if (prev == null) return eta
        // Hysteresis: only update countdownSec if delta > 3 seconds, avoiding jitter from polling
        if (Math.abs(prev - eta) > 3) {
          return Math.round(0.35 * eta + 0.65 * prev)
        }
        return prev
      })
    } else if (eta === 0) {
      setCountdownSec(0)
    }
  }, [eta])

  useEffect(() => {
    if (countdownSec == null || countdownSec <= 0) return
    const timer = setInterval(() => {
      setCountdownSec((prev) => (prev && prev > 1 ? prev - 1 : prev))
    }, 1000)
    return () => clearInterval(timer)
  }, [countdownSec])

  const formatEta = (sec?: number | null) => {
    if (sec === undefined || sec === null || sec <= 0) return null
    if (sec < 60) return `~${sec}s remaining`
    const mins = Math.floor(sec / 60)
    const rem = sec % 60
    return rem > 0 ? `~${mins}m ${rem}s remaining` : `~${mins}m remaining`
  }

  const etaStr = formatEta(countdownSec)

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-baseline justify-between">
          <p className="text-[14px] font-bold">Translating</p>
          <span className="font-mono text-[12.5px] text-muted">
            {subtitle || (overallPct != null ? `${overallPct}%` : `page ${Math.max(1, Math.min(done || 1, total))} of ${total}`)}
          </span>
        </div>
        <div className="mt-2">
          <ProgressBar
            value={overallPct != null ? overallPct : done}
            max={overallPct != null ? 100 : total}
            label="Translation progress"
          />
        </div>
        <div className="mt-2 flex items-center justify-between text-[12px] text-muted">
          <span className="truncate pr-2 font-medium text-ink">{message || 'Processing pages with layout preservation telemetry...'}</span>
          {(etaStr || (speed && speed > 0)) && (
            <span className="shrink-0 font-mono text-[11.5px] text-teal font-semibold flex items-center gap-1.5">
              <span className="size-1.5 rounded-full bg-teal animate-pulse" />
              {etaStr}{etaStr && speed ? ' • ' : ''}{speed && speed > 0 ? `${speed} ${overallPct != null && stage === 2 ? 'seg/s' : 'p/s'}` : ''}
            </span>
          )}
        </div>
      </div>
      <ol className="space-y-0">
        {stages.map((s, i) => {
          const st = i < stage ? 'done' : i === stage ? 'now' : 'todo'
          return (
            <li key={s} className="flex items-center gap-3 py-1.5 text-[13px]">
              <span className={`flex size-5 items-center justify-center rounded-full ${st === 'done' ? 'bg-teal text-white' : st === 'now' ? 'border-2 border-teal' : 'border border-line-strong'}`}>
                {st === 'done' ? <IconCheck className="size-3" /> : st === 'now' ? <span className="size-1.5 rounded-full bg-teal ll-pulse" /> : null}
              </span>
              <span className={st === 'todo' ? 'text-faint' : st === 'now' ? 'font-semibold' : 'text-muted'}>{s}</span>
              {st === 'now' && <span className="sr-only">(current stage)</span>}
            </li>
          )
        })}
      </ol>
      <Button className="w-full" onClick={onCancel}><IconX />Cancel translation</Button>
      <p className="text-[12px] text-muted">Cancelling keeps pages already translated. You can resume later.</p>
    </div>
  )
}

function Inspector(p: {
  tab: Tab; setTab: (t: Tab) => void; phase: Phase; done: number; total: number; stage: number; page: Page; pageState: string
  src: string; tgt: string; setSrc: (s: string) => void; setTgt: (s: string) => void
  pageRange: string; setPageRange: (r: string) => void
  settings: AppSettings; onUpdateProvider: (pr: ProviderType) => void; onOpenSettings?: () => void
  visibleIssues: Issue[]; activeIssue?: string; openIssue: (i: Issue) => void; start: () => void; cancel: () => void
  onExport: () => void; retryPage: () => void; retrying: boolean
  telemetry?: { eta?: number; speed?: number; message?: string }
  overallPct?: number | null
  subtitle?: string | null
}) {
  const tabs: [Tab, string][] = [['translation', 'Translation'], ['quality', 'Quality checks'], ['page', 'Page details']]
  const locked = p.phase === 'processing'
  const pageIssues = p.visibleIssues.filter((i) => i.page === p.page.n)

  // Parse pageRange into numeric bounds [from, to]
  const parseRange = (val: string, maxP: number): [number, number] => {
    if (!val || val === 'all') return [1, maxP]
    const m = val.match(/^(\d+)(?:\s*-\s*(\d+))?$/)
    if (m) {
      const f = parseInt(m[1], 10)
      const t = m[2] ? parseInt(m[2], 10) : f
      return [Math.max(1, Math.min(f, maxP)), Math.max(1, Math.min(t, maxP))]
    }
    return [1, maxP]
  }

  const [initialFrom, initialTo] = parseRange(p.pageRange, p.total)
  const [fromPage, setFromPage] = useState(initialFrom)
  const [toPage, setToPage] = useState(initialTo)

  useEffect(() => {
    const [f, t] = parseRange(p.pageRange, p.total)
    setFromPage(f)
    setToPage(t)
  }, [p.pageRange, p.total])

  const handleFromChange = (newVal: number) => {
    if (isNaN(newVal)) return
    // Auto-clamp: 1 <= from <= to <= total
    const clamped = Math.max(1, Math.min(newVal, toPage, p.total))
    setFromPage(clamped)
    p.setPageRange(clamped === 1 && toPage === p.total ? 'all' : `${clamped}-${toPage}`)
  }

  const handleToChange = (newVal: number) => {
    if (isNaN(newVal)) return
    // Auto-clamp: from <= to <= total
    const clamped = Math.max(1, Math.min(newVal, p.total))
    const finalTo = Math.max(fromPage, clamped)
    setToPage(finalTo)
    p.setPageRange(fromPage === 1 && finalTo === p.total ? 'all' : `${fromPage}-${finalTo}`)
  }

  const setPresetRange = (f: number, t: number) => {
    const validF = Math.max(1, Math.min(f, p.total))
    const validT = Math.max(validF, Math.min(t, p.total))
    setFromPage(validF)
    setToPage(validT)
    p.setPageRange(validF === 1 && validT === p.total ? 'all' : `${validF}-${validT}`)
  }

  const [copiedIssues, setCopiedIssues] = useState(false)
  const handleCopyIssues = () => {
    if (p.visibleIssues.length === 0) return
    const failures = p.visibleIssues.filter((i) => i.severity === 'failure').length
    const warnings = p.visibleIssues.filter((i) => i.severity === 'warning').length
    const notices = p.visibleIssues.filter((i) => i.severity === 'info').length

    const lines: string[] = [
      `=== LayoutLingua Quality Checks Report ===`,
      `Total items: ${p.visibleIssues.length} (${failures} failures, ${warnings} warnings, ${notices} notices)`,
      `Generated at: ${new Date().toLocaleString()}`,
      `------------------------------------------`,
      '',
    ]

    p.visibleIssues.forEach((iss, idx) => {
      lines.push(`#${idx + 1} [Page ${iss.page}] ${iss.severity.toUpperCase()} - ${iss.code || 'ISSUE'}`)
      lines.push(`Title: ${iss.title}`)
      if (iss.detail) lines.push(`Detail: ${iss.detail}`)
      if (iss.region) lines.push(`Region / ID: ${iss.region}`)
      lines.push('')
    })

    navigator.clipboard.writeText(lines.join('\n')).then(() => {
      setCopiedIssues(true)
      setTimeout(() => setCopiedIssues(false), 2500)
    }).catch(() => {})
  }

  const selectedCount = Math.max(1, toPage - fromPage + 1)
  const isAllPages = fromPage === 1 && toPage === p.total
  return (
    <aside aria-label="Inspector" className="flex w-[340px] shrink-0 flex-col border-l border-line bg-white min-h-0 h-full max-h-full overflow-hidden">
      <div role="tablist" className="flex border-b border-line px-2 shrink-0">
        {tabs.map(([t, l]) => (
          <button key={t} role="tab" aria-selected={p.tab === t} onClick={() => p.setTab(t)} className={`relative flex h-12 items-center gap-1.5 px-3 text-[13px] font-semibold ${p.tab === t ? 'text-ink' : 'text-muted hover:text-ink'}`}>
            {l}
            {t === 'quality' && p.visibleIssues.length > 0 && <span className="font-mono text-[12px] font-medium text-amber-ink">{p.visibleIssues.length}</span>}
            {p.tab === t && <span className="absolute inset-x-3 bottom-0 h-0.5 bg-teal" />}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
        {p.tab === 'translation' && (
          <div className="space-y-6 p-5">
            <section className="space-y-3">
              <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-2 min-w-0">
                <div className="min-w-0">
                  <Field label="Source language">
                    <select disabled={locked} value={p.src} onChange={(e) => p.setSrc(e.target.value)} className={`${selectCls} w-full truncate`}>
                      {languages.map((l) => <option key={l}>{l}</option>)}
                    </select>
                  </Field>
                </div>
                <IconButton label="Swap languages" disabled={locked} onClick={() => { p.setSrc(p.tgt); p.setTgt(p.src) }} className="mb-0.5 shrink-0"><IconSwap /></IconButton>
                <div className="min-w-0">
                  <Field label="Target language">
                    <select disabled={locked} value={p.tgt} onChange={(e) => p.setTgt(e.target.value)} className={`${selectCls} w-full truncate`}>
                      {languages.map((l) => <option key={l}>{l}</option>)}
                    </select>
                  </Field>
                </div>
              </div>
              <Field label="Provider">
                <div className="flex items-center gap-1.5">
                  <select
                    disabled={locked}
                    value={p.settings.provider}
                    onChange={(e) => p.onUpdateProvider(e.target.value as ProviderType)}
                    className={`${selectCls} flex-1 truncate`}
                  >
                    <option value="google">Google Translate RPC (Zero Setup)</option>
                    <option value="openai">OpenAI-Compatible ({p.settings.openaiModel || 'Cloud & Local LLM'})</option>
                    <option value="gemini">Google Gemini ({p.settings.geminiModel})</option>
                    <option value="argos">Argos Translate (Offline)</option>
                  </select>
                  <IconButton
                    label="Configure provider, keys and endpoints in Settings"
                    onClick={p.onOpenSettings}
                    className="size-9 shrink-0 border border-line-strong hover:border-ink"
                  >
                    <IconSettings />
                  </IconButton>
                </div>
              </Field>
              <div className="flex items-center justify-between text-[12px] pt-0.5">
                <span className="text-muted leading-relaxed truncate">
                  {p.settings.provider === 'google' && `Zero setup required, ready to translate.`}
                  {p.settings.provider === 'openai' && `OpenAI-Compatible (${p.settings.openaiModel || 'Model'}). ${p.settings.openaiEndpoint || 'https://api.openai.com/v1'}`}
                  {p.settings.provider === 'gemini' && (p.settings.geminiKey ? `Gemini Key OK (${p.settings.geminiModel}).` : `Gemini selected. API key needed in Settings.`)}
                  {p.settings.provider === 'argos' && `Offline CTranslate2 model.`}
                </span>
                <button
                  type="button"
                  onClick={p.onOpenSettings}
                  className="text-teal hover:underline font-semibold shrink-0 cursor-pointer ml-1"
                >
                  📖 Setup guide
                </button>
              </div>
            </section>
            <div className="h-px bg-line" />

            {p.phase === 'idle' && (
              <section className="space-y-3.5">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-[12.5px] font-semibold">
                    <span>Page range</span>
                    <span className="font-mono text-[11.5px] font-semibold text-teal">
                      {isAllPages
                        ? `All (${p.total} pp)`
                        : `${selectedCount} of ${p.total} pp selected`}
                    </span>
                  </div>

                  <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-medium text-muted">From page</label>
                      <input
                        type="number"
                        min={1}
                        max={toPage}
                        value={fromPage}
                        disabled={locked}
                        onChange={(e) => handleFromChange(parseInt(e.target.value, 10))}
                        className="h-8.5 w-full rounded-md border border-line-strong px-2.5 font-mono text-[13px] font-bold text-ink focus:border-teal focus:ring-1 focus:ring-teal"
                      />
                    </div>
                    <span className="mt-4 text-muted font-bold text-[13px]">→</span>
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-medium text-muted">To page</label>
                      <input
                        type="number"
                        min={fromPage}
                        max={p.total}
                        value={toPage}
                        disabled={locked}
                        onChange={(e) => handleToChange(parseInt(e.target.value, 10))}
                        className="h-8.5 w-full rounded-md border border-line-strong px-2.5 font-mono text-[13px] font-bold text-ink focus:border-teal focus:ring-1 focus:ring-teal"
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                    <button
                      type="button"
                      onClick={() => setPresetRange(1, p.total)}
                      className={`rounded px-2 py-0.5 text-[11px] font-semibold border transition-colors cursor-pointer ${
                        isAllPages
                          ? 'border-teal bg-teal/10 text-teal'
                          : 'border-line text-muted hover:border-line-strong'
                      }`}
                    >
                      All (1–{p.total})
                    </button>
                    {p.total > 5 && (
                      <button
                        type="button"
                        onClick={() => setPresetRange(1, Math.min(5, p.total))}
                        className={`rounded px-2 py-0.5 text-[11px] font-semibold border transition-colors cursor-pointer ${
                          fromPage === 1 && toPage === Math.min(5, p.total)
                            ? 'border-teal bg-teal/10 text-teal'
                            : 'border-line text-muted hover:border-line-strong'
                        }`}
                      >
                        First 5 (1–{Math.min(5, p.total)})
                      </button>
                    )}
                    {p.total > 20 && (
                      <button
                        type="button"
                        onClick={() => setPresetRange(1, Math.min(20, p.total))}
                        className={`rounded px-2 py-0.5 text-[11px] font-semibold border transition-colors cursor-pointer ${
                          fromPage === 1 && toPage === Math.min(20, p.total)
                            ? 'border-teal bg-teal/10 text-teal'
                            : 'border-line text-muted hover:border-line-strong'
                        }`}
                      >
                        First 20 (1–{Math.min(20, p.total)})
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setPresetRange(p.page.n, p.page.n)}
                      className={`rounded px-2 py-0.5 text-[11px] font-semibold border transition-colors cursor-pointer ${
                        fromPage === p.page.n && toPage === p.page.n
                          ? 'border-teal bg-teal/10 text-teal'
                          : 'border-line text-muted hover:border-line-strong'
                      }`}
                    >
                      Current (p.{p.page.n})
                    </button>
                  </div>

                  <p className="text-[11px] text-muted leading-relaxed">
                    {isAllPages
                      ? `Translating all ${p.total} pages with full layout preservation.`
                      : `Translating pages ${fromPage} to ${toPage} (${selectedCount} pp). Other pages remain pristine from original PDF.`}
                  </p>
                </div>

                <Button variant="primary" className="h-10 w-full" onClick={p.start}>
                  {isAllPages
                    ? 'Translate full document'
                    : `Translate pages ${fromPage}–${toPage} (${selectedCount} pp)`}
                </Button>
              </section>
            )}
            {p.phase === 'processing' && (
              <ProcessingPanel
                done={p.done}
                total={p.total}
                stage={p.stage}
                onCancel={p.cancel}
                eta={p.telemetry?.eta}
                speed={p.telemetry?.speed}
                message={p.telemetry?.message}
                overallPct={p.overallPct}
                subtitle={p.subtitle}
              />
            )}
            {p.phase === 'cancelled' && (
              <StateNotice tone="neutral" icon={<IconX className="size-5" />} title="Translation cancelled" actions={<Button size="sm" variant="primary" onClick={p.start}>Resume from page {p.done + 1}</Button>}>
                <span className="font-mono">{p.done}</span> of {p.total} pages were translated and kept.
              </StateNotice>
            )}
            {p.phase === 'rate-limited' && (
              <StateNotice
                tone="warning"
                icon={<IconAlert className="size-5 text-amber-ink" />}
                title="Google Free Quota Blocked (Rate Limit)"
                actions={
                  <div className="flex flex-col gap-2 w-full pt-1">
                    <Button variant="primary" className="w-full text-[13px]" onClick={p.onOpenSettings}>
                      <IconSettings /> Open Settings to switch provider
                    </Button>
                    <div className="grid grid-cols-2 gap-2">
                      <Button size="sm" onClick={() => { p.onUpdateProvider('openai'); p.start() }}>
                        Use OpenAI / LLM
                      </Button>
                      <Button size="sm" onClick={() => { p.onUpdateProvider('gemini'); p.start() }}>
                        Use Gemini API
                      </Button>
                    </div>
                    <Button size="sm" className="w-full text-muted hover:text-ink" onClick={p.start}>
                      Retry with Google
                    </Button>
                  </div>
                }
              >
                Google Translate public RPC temporarily rate-limited your IP (HTTP 429) because this document is large (<span className="font-mono">{p.total}</span> pages).
                <br /><br />
                <strong>Pages 1–{p.done} are safely saved.</strong> Free endpoints have strict quotas; please switch to an API provider (Gemini 2.0 Flash, DeepSeek, or Groq) in Settings to finish translating without interruption.
              </StateNotice>
            )}
            {p.phase === 'provider-error' && (
              <StateNotice
                tone="error"
                icon={<IconError className="size-5" />}
                title={`${p.settings.provider.toUpperCase()} stopped responding`}
                actions={
                  <>
                    <Button size="sm" variant="primary" onClick={p.start}>
                      Retry from page {p.done + 1}
                    </Button>
                    <Button size="sm" onClick={() => p.onUpdateProvider('google')}>
                      Switch to Google (Free)
                    </Button>
                  </>
                }
              >
                {p.telemetry?.message ? (
                  <p className="font-medium text-red-600 dark:text-red-400 mb-1.5">{p.telemetry.message}</p>
                ) : (
                  <p>The provider returned an error on page {p.done + 1}.</p>
                )}
                <span className="text-[12px] text-muted">Pages 1–{p.done} are kept; nothing needs to be redone. Check your API key or model in Settings.</span>
              </StateNotice>
            )}
            {p.phase === 'done' && (
              <section className="space-y-3">
                {p.visibleIssues.length > 0 ? (
                  <StateNotice tone="warning" icon={<IconAlert className="size-5" />} title="Translated with items to review">
                    {p.total} pages translated. {p.visibleIssues.length} items need your attention before export.
                  </StateNotice>
                ) : (
                  <StateNotice tone="success" icon={<IconCheck className="size-5" />} title="Document translation complete">
                    All {p.total} pages translated with layout and typography preserved.
                  </StateNotice>
                )}
                <div className="flex gap-2">
                  {p.visibleIssues.length > 0 && <Button className="flex-1" onClick={() => p.setTab('quality')}>Review warnings</Button>}
                  <Button variant="primary" className="flex-1" onClick={p.onExport}><IconDownload />Export PDF</Button>
                </div>
                <Button size="sm" className="w-full" onClick={p.start}>
                  Re-translate document ({p.src} → {p.tgt})
                </Button>
              </section>
            )}

          </div>
        )}

        {p.tab === 'quality' && (
          p.visibleIssues.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <IconCheck className="mx-auto size-7 text-faint" />
              <p className="mt-3 text-[14px] font-semibold">{p.phase === 'idle' ? 'No checks yet' : 'No issues reported'}</p>
              <p className="mt-1 text-[13px] leading-relaxed text-muted">{p.phase === 'idle' ? 'Quality checks run while the document is translated.' : 'All visual integrity and layout checks passed.'}</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b border-line px-4 py-2.5 text-[12px]">
                <div className="flex items-center gap-3">
                  {(['failure', 'warning', 'info'] as const).map((s) => {
                    const m = sevMeta[s]; const n = p.visibleIssues.filter((i) => i.severity === s).length
                    return <span key={s} className={`flex items-center gap-1 font-semibold ${m.text}`}><m.Icon className="size-3.5" />{n} {s === 'failure' ? 'failure' : s === 'warning' ? (n === 1 ? 'warning' : 'warnings') : 'notice'}</span>
                  })}
                </div>
                <button
                  onClick={handleCopyIssues}
                  className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold text-ink bg-white hover:bg-canvas border border-line-strong rounded-md transition-colors shadow-2xs"
                  title="Copy full issues report to clipboard"
                >
                  {copiedIssues ? <IconCheck className="size-3.5 text-teal" /> : <IconCopy className="size-3.5 text-muted" />}
                  <span>{copiedIssues ? 'Copied log!' : 'Copy log'}</span>
                </button>
              </div>
              {p.visibleIssues.map((i, idx) => <IssueRow key={i.id} index={idx + 1} issue={i} active={p.activeIssue === i.id} onOpen={() => p.openIssue(i)} />)}
              <p className="px-4 py-3 text-[12px] text-faint">Items stay listed until the underlying page changes. Opening an item does not resolve it.</p>
            </>
          )
        )}

        {p.tab === 'page' && (
          <div className="p-5">
            <div className="flex items-baseline justify-between">
              <h3 className="text-[17px] font-bold">Page {p.page.n}</h3>
              <span className="text-[13px] font-semibold text-muted">{p.pageState}</span>
            </div>
            <dl className="mt-4 divide-y divide-line border-y border-line text-[13px]">
              {[['Page size', '210 × 297 mm (A4)'], ['Media box', '0 0 595.3 841.9'], ['Text blocks', p.page.status === 'fallback' ? '0 translated' : String(p.page.blockCount)], ['Table cells', String(p.page.cellCount)], ['Formulas kept', String(p.page.blocks.filter((b) => b.kind === 'eq').length)], ['Embedded fonts', 'DejaVuSerif, DejaVuSans, DroidSansCJK']].map(([k, v]) => (
                <div key={k} className="flex justify-between py-2.5"><dt className="text-muted">{k}</dt><dd className="font-mono text-[12.5px]">{v}</dd></div>
              ))}
            </dl>
            <h4 className="mt-5 text-[13px] font-bold">Issues on this page</h4>
            {pageIssues.length === 0 ? <p className="mt-1 text-[13px] text-muted">None reported.</p> : (
              <ul className="mt-2 space-y-2">
                {pageIssues.map((i) => { const m = sevMeta[i.severity]; return (
                  <li key={i.id}><button onClick={() => p.openIssue(i)} className="flex w-full items-start gap-2 rounded-md border border-line px-3 py-2 text-left text-[13px] hover:bg-canvas"><m.Icon className={`mt-0.5 size-4 shrink-0 ${m.text}`} /><span>{i.title}</span></button></li>
                )})}
              </ul>
            )}
            {p.page.status === 'fallback' && p.done >= 5 && (
              <div className="mt-5 rounded-md border border-red/30 bg-red-soft p-3 text-[13px]">
                <p className="font-bold text-red">Preserved from source</p>
                <p className="mt-1 text-ink">This page is copied unchanged into the output.</p>
                <Button size="sm" className="mt-2" disabled={p.retrying || p.phase !== 'done'} onClick={p.retryPage}>{p.retrying ? 'Retrying page…' : 'Retry this page'}</Button>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}

import type { SelectedDocument } from './OpenScreen'

/* ---------- Workspace ---------- */
export default function Workspace({
  onClose,
  rail,
  docInfo,
  onHelp,
  onOpenSettings,
}: {
  onClose: () => void
  rail: React.ReactNode
  docInfo?: SelectedDocument
  onHelp?: () => void
  onOpenSettings?: () => void
}) {
  const [settings, updateSettings] = useSettings()
  const totalPages = docInfo?.pages || pages.length

  const [phase, setPhase] = useState<Phase>('idle')
  const [done, setDone] = useState(0)
  const [cur, setCur] = useState(1)
  const [highlight, setHighlight] = useState<string>()
  const [activeIssue, setActiveIssue] = useState<string>()
  const [tab, setTab] = useState<Tab>('translation')
  const [telemetry, setTelemetry] = useState<{ eta?: number; speed?: number; message?: string }>({})
  const [previewVersion, setPreviewVersion] = useState(0)
  const [backendStage, setBackendStage] = useState<number | null>(null)
  const [overallPct, setOverallPct] = useState<number | null>(null)
  const [progressSubtitle, setProgressSubtitle] = useState<string | null>(null)
  const [integrity, setIntegrity] = useState<any>(null)

  const [runId, setRunId] = useState(0)

  const docPages: Page[] = useMemo(() => {
    if (!docInfo?.pages) return pages
    const isDemoPaper = !docInfo.id || docInfo.id === 'demo-research-paper'
    return Array.from({ length: docInfo.pages }, (_, i) => {
      const n = i + 1
      const isDone = phase === 'done' || (phase === 'processing' && i < done)
      const realStatus = integrity?.page_statuses?.[n] || (isDemoPaper && pages[i] ? pages[i].status : isDone ? 'ok' : 'pending')
      const realBlockCount = integrity?.page_block_counts?.[n] ?? (isDemoPaper && pages[i] ? pages[i].blockCount : 12)
      const realMathCount = integrity?.page_math_counts?.[n] ?? (isDemoPaper && pages[i] ? pages[i].blocks.filter((b) => b.kind === 'eq').length : 14)
      const syntheticMathBlocks = Array.from({ length: realMathCount }, (_, mIdx) => ({
        kind: 'eq' as const,
        id: `m${mIdx + 1}`,
        tex: '',
        no: `(${mIdx + 1})`,
      }))
      return {
        n,
        status: realStatus as any,
        blocks: isDemoPaper && pages[i] ? pages[i].blocks : syntheticMathBlocks,
        blockCount: realBlockCount,
        cellCount: isDemoPaper && pages[i] ? pages[i].cellCount : 0,
      }
    })
  }, [docInfo?.id, docInfo?.pages, phase, done, integrity])
  const [inspectorOpen, setInspectorOpen] = useState(() => window.innerWidth >= 1340)
  const [zoom, setZoom] = useState<number | null>(null)
  const [mode, setMode] = useState<'side' | 'overlay'>('side')
  const [blend, setBlend] = useState(100)
  const isoToLabelMap: Record<string, string> = {
    en: 'English',
    vi: 'Vietnamese',
    zh: 'Chinese (Simplified)',
    'zh-tw': 'Chinese (Traditional)',
    ja: 'Japanese',
    ko: 'Korean',
    fr: 'French',
    de: 'German',
    es: 'Spanish',
    ru: 'Russian',
    it: 'Italian',
    pt: 'Portuguese',
    id: 'Indonesian',
    nl: 'Dutch',
    pl: 'Polish',
    tr: 'Turkish',
    uk: 'Ukrainian',
  }
  const [src, setSrc] = useState(() => isoToLabelMap[docInfo?.detectedLang || 'en'] || 'English')
  const [tgt, setTgt] = useState(() => (docInfo?.detectedLang === 'vi' ? 'English' : 'Vietnamese'))
  const [pageRange, setPageRange] = useState('all')

  const [rangeFrom, rangeTo] = useMemo(() => {
    if (!pageRange || pageRange === 'all') return [1, totalPages]
    const m = pageRange.match(/^(\d+)(?:\s*-\s*(\d+))?$/)
    if (m) {
      const f = parseInt(m[1], 10)
      const t = m[2] ? parseInt(m[2], 10) : f
      return [Math.max(1, Math.min(f, totalPages)), Math.max(1, Math.min(t, totalPages))]
    }
    return [1, totalPages]
  }, [pageRange, totalPages])

  const isFullDoc = rangeFrom === 1 && rangeTo === totalPages
  const activeSelectedCount = Math.max(1, rangeTo - rangeFrom + 1)

  const [exportOpen, setExportOpen] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const canvasRef = useRef<HTMLDivElement>(null)
  const [box, setBox] = useState({ w: 900, h: 700 })

  useLayoutEffect(() => {
    const el = canvasRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setBox({ w: e.contentRect.width, h: e.contentRect.height }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!docInfo?.id) return
    let active = true
    fetch(apiUrl(`/api/progress?id=${encodeURIComponent(docInfo.id)}`))
      .then((res) => (res.ok ? res.json() : null))
      .then((pData) => {
        if (!active || !pData) return
        if (pData.status === 'done') {
          setDone(isFullDoc ? totalPages : activeSelectedCount)
          setOverallPct(100)
          setBackendStage(stages.length)
          setPhase('done')
          setPreviewVersion(Date.now())
        }
        if (pData.integrity && active) {
          setIntegrity(pData.integrity)
        }
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [docInfo?.id, totalPages])

  useEffect(() => {
    if (phase !== 'processing') {
      return
    }

    let active = true
    let progressTimer: any = null
    let consecutiveFails = 0

    const activeDocId = docInfo?.id || 'sample_academic'
    if (activeDocId) {
      progressTimer = setInterval(async () => {
        if (!active) return
        try {
          const pRes = await fetch(apiUrl(`/api/progress?id=${encodeURIComponent(activeDocId)}`))
          if (pRes.ok) {
            const pData = await pRes.json()
            if (pData.current_page != null && active) {
              setDone(pData.current_page)
            }
            if (pData.stage_index != null && active) {
              setBackendStage(pData.stage_index)
            }
            if (pData.overall_pct != null && active) {
              setOverallPct(pData.overall_pct)
            }
            if (active) {
              if (pData.integrity) {
                setIntegrity(pData.integrity)
              }
              if (pData.subtitle) {
                setProgressSubtitle(pData.subtitle)
              } else if (pData.stage_index === 2 && pData.segments_total) {
                setProgressSubtitle(`segment ${pData.segments_done || 0} of ${pData.segments_total}`)
              } else if (pData.current_page > 0) {
                setProgressSubtitle(`page ${pData.current_page} of ${pData.total_pages}`)
              }
              setTelemetry({
                eta: pData.eta_seconds,
                speed: pData.speed,
                message: pData.message,
              })
            }
            if (pData.status === 'idle' && active) {
              if (progressTimer) clearInterval(progressTimer)
              setPhase('idle')
              return
            }
            if (pData.status === 'done' && active) {
              if (progressTimer) clearInterval(progressTimer)
              setDone(isFullDoc ? totalPages : activeSelectedCount)
              setOverallPct(100)
              setBackendStage(stages.length)
              setPhase('done')
              setPreviewVersion(Date.now())
              if (docInfo?.id || docInfo?.name) {
                updateHistoryStatus(docInfo.id || docInfo.name, 'translated')
              }
              return
            }
            if (pData.status === 'rate-limited' && active) {
              if (progressTimer) clearInterval(progressTimer)
              setPhase('rate-limited')
              if (docInfo?.id || docInfo?.name) {
                updateHistoryStatus(docInfo.id || docInfo.name, 'failed')
              }
              return
            }
            if (pData.status === 'error' && active) {
              if (progressTimer) clearInterval(progressTimer)
              setPhase('provider-error')
              if (docInfo?.id || docInfo?.name) {
                updateHistoryStatus(docInfo.id || docInfo.name, 'failed')
              }
              return
            }
          }
        } catch {
          if (active) {
            consecutiveFails++
            if (consecutiveFails > 8) {
              if (progressTimer) clearInterval(progressTimer)
              setPhase('idle')
            }
          }
        }
      }, 350)

      const langCodeMap: Record<string, string> = {
        'English': 'en',
        'Vietnamese': 'vi',
        'Chinese (Simplified)': 'zh',
        'Chinese (Traditional)': 'zh-tw',
        'Japanese': 'ja',
        'Korean': 'ko',
        'French': 'fr',
        'German': 'de',
        'Spanish': 'es',
        'Russian': 'ru',
        'Italian': 'it',
        'Portuguese': 'pt',
        'Indonesian': 'id',
        'Dutch': 'nl',
        'Polish': 'pl',
        'Turkish': 'tr',
        'Ukrainian': 'uk',
      }
      const resolvedTargetLang = langCodeMap[tgt] || (tgt === 'Vietnamese' ? 'vi' : 'en')
      const resolvedSourceLang = langCodeMap[src] || (src === 'Vietnamese' ? 'vi' : 'auto')

      fetch(apiUrl('/api/translate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_id: activeDocId,
          source_lang: resolvedSourceLang,
          target_lang: resolvedTargetLang,
          page_range: pageRange || 'all',
          custom_glossary: settings.customGlossary || '',
          provider: settings.provider,
          gemini_key: settings.geminiKey,
          gemini_model: settings.geminiModel,
          openai_key: settings.openaiKey,
          openai_endpoint: settings.openaiEndpoint,
          openai_model: settings.openaiModel,
          min_font_shrink: settings.minFontShrink,
        }),
      })
        .then(async (res) => {
          if (!active) return
          if (res.status === 429) {
            if (progressTimer) clearInterval(progressTimer)
            setPhase('rate-limited')
            if (docInfo?.id || docInfo?.name) {
              updateHistoryStatus(docInfo.id || docInfo.name, 'failed')
            }
          } else if (!res.ok) {
            if (progressTimer) clearInterval(progressTimer)
            const errData = await res.json().catch(() => ({}))
            setTelemetry({ message: errData.error || errData.message || undefined })
            setPhase('provider-error')
            if (docInfo?.id || docInfo?.name) {
              updateHistoryStatus(docInfo.id || docInfo.name, 'failed')
            }
          }
        })
        .catch(() => {
          if (!active) return
          if (progressTimer) clearInterval(progressTimer)
          setPhase('provider-error')
          if (docInfo?.id || docInfo?.name) {
            updateHistoryStatus(docInfo.id || docInfo.name, 'failed')
          }
        })

      return () => {
        active = false
        if (progressTimer) clearInterval(progressTimer)
      }
    }
  }, [phase, runId, docInfo?.id])

  const stage = backendStage != null
    ? (phase === 'done' ? stages.length : backendStage)
    : (phase === 'done' ? stages.length : done === 0 ? 0 : done < Math.floor(totalPages / 3) ? 1 : done < Math.floor((totalPages * 2) / 3) ? 2 : 3)
  const known = (p: Page) => {
    if (phase === 'idle') return 'pending'
    const inRange = isFullDoc || (p.n >= rangeFrom && p.n <= rangeTo)
    if (!inRange) {
      // Pages outside the active range are pristine from source
      return 'ok'
    }
    if (phase === 'processing') {
      const pageIndexInRange = p.n - rangeFrom + 1
      if (pageIndexInRange > done) return 'pending'
    }
    return integrity?.page_statuses?.[p.n] || (p.status || 'ok')
  }

  const backendIssues: Issue[] = useMemo(() => {
    if (integrity?.issues && Array.isArray(integrity.issues)) {
      return integrity.issues.map((iss: any) => ({
        id: iss.id,
        severity: (iss.severity || 'warning') as any,
        page: iss.page,
        code: iss.code,
        title: iss.title,
        detail: iss.detail,
        region: iss.region,
        next: iss.next || 'Inspect the highlighted region or add a shorter term in Glossary.',
        action: iss.action || `Inspect region on page ${iss.page}`,
      }))
    }
    return []
  }, [integrity])

  const visibleIssues = docInfo?.id
    ? backendIssues.filter((i) => (isFullDoc ? i.page <= done : i.page >= rangeFrom && i.page <= rangeTo) && phase !== 'idle')
    : issues.filter((i) => i.page <= done && phase !== 'idle')

  const page = docPages[cur - 1] || docPages[0]
  const counts = useMemo(() => {
    if (integrity && integrity.blocks_translated != null) {
      return {
        blocks: integrity.blocks_translated ?? 0,
        cells: 0,
        review: integrity.needs_review ?? 0,
        preserved: integrity.preserved_pages ?? 0,
      }
    }
    const dp = docPages.filter((p) => {
      if (phase === 'idle') return false
      if (isFullDoc) return p.n <= done
      return p.n >= rangeFrom && p.n <= rangeTo && (p.n - rangeFrom + 1) <= done
    })
    return {
      blocks: dp.reduce((a, p) => a + p.blockCount, 0),
      cells: dp.reduce((a, p) => a + p.cellCount, 0),
      review: visibleIssues.filter((i) => i.severity === 'warning').length,
      preserved: dp.filter((p) => p.status === 'fallback').length,
    }
  }, [docPages, done, phase, visibleIssues, integrity, isFullDoc, rangeFrom, rangeTo])

  const docState: DocState = phase === 'processing' ? 'processing' : phase === 'done' ? (counts.review > 0 ? 'review' : 'done') : (phase === 'provider-error' || phase === 'rate-limited') ? 'failed' : 'not-started'
  const fitW = Math.max(160, Math.min(mode === 'side' ? (box.w - 64) / 2 : box.w - 48, ((box.h - 56) * 210) / 297))
  const width = zoom ? PAGE_W * zoom : fitW
  const pct = Math.round((width / PAGE_W) * 100)
  const height = (width * 297) / 210
  const setZ = (d: number) => setZoom(Math.min(2.5, Math.max(0.4, Math.round((width / PAGE_W + d) * 10) / 10)))

  const select = (n: number) => { setCur(n); setHighlight(undefined); setActiveIssue(undefined) }
  const openIssue = (i: Issue) => { setCur(i.page); setHighlight(i.region); setActiveIssue(i.id); setTab('quality') }
  const start = () => {
    setDone(0)
    setOverallPct(4)
    setBackendStage(0)
    setRunId((r) => r + 1)
    setPhase('processing')
    setTab('translation')
  }
  const retryPage = () => {
    setRetrying(true)
    start()
    setTimeout(() => { setRetrying(false) }, 900)
  }

  const handleSetSrc = (newSrc: string) => {
    if (newSrc === tgt) {
      setTgt(src)
    }
    setSrc(newSrc)
    if (phase === 'done' || phase === 'cancelled' || phase === 'provider-error' || phase === 'rate-limited') {
      setPhase('idle')
    }
  }

  const handleSetTgt = (newTgt: string) => {
    if (newTgt === src) {
      setSrc(tgt)
    }
    setTgt(newTgt)
    if (phase === 'done' || phase === 'cancelled' || phase === 'provider-error' || phase === 'rate-limited') {
      setPhase('idle')
    }
  }

  const handleSetPageRange = (newRange: string) => {
    setPageRange(newRange)
    if (phase === 'done' || phase === 'cancelled' || phase === 'provider-error' || phase === 'rate-limited') {
      setPhase('idle')
    }
  }

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable)) {
        return
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        if (phase !== 'processing') start()
        return
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
        e.preventDefault()
        if (phase === 'done') setExportOpen(true)
        return
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'o' || e.key === 'O')) {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key === 'ArrowLeft') {
        setCur((c) => Math.max(1, c - 1))
      } else if (e.key === 'ArrowRight') {
        setCur((c) => Math.min(totalPages, c + 1))
      } else if (e.key === '+' || e.key === '=') {
        setZ(0.1)
      } else if (e.key === '-') {
        setZ(-0.1)
      } else if (e.key === '0') {
        setZoom(null)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [phase, totalPages, width])

  const pageLabel = (s: ReturnType<typeof known>) => s === 'pending' ? (phase === 'idle' ? 'Not translated' : 'Pending') : s === 'ok' ? 'Translated' : s === 'warn' ? 'Needs review' : 'Preserved from source'
  const s = known(page)
  const issue = visibleIssues.find((i) => i.id === activeIssue)
  const vi = issue ? visibleIssues.indexOf(issue) : -1
  const mark = { highlight, highlightLabel: issue ? `${vi + 1}  ${sevMeta[issue.severity].label}` : undefined, highlightTone: issue?.severity }

  const isCurrentPageInSelectedRange = isFullDoc || (page.n >= rangeFrom && page.n <= rangeTo)
  const isCurrentPageTranslated =
    phase === 'done' ||
    (phase !== 'idle' &&
      isCurrentPageInSelectedRange &&
      (Boolean(integrity?.completed_pages?.[page.n]) ||
        Boolean(integrity?.page_block_counts?.[page.n] > 0) ||
        page.n - rangeFrom + 1 <= done))

  const output = () => {
    if (isCurrentPageTranslated) {
      return (
        <div className="relative">
          <PdfPage
            key={`trans-${docInfo?.id}-${page.n}-${runId}-${tgt}`}
            page={page}
            type="translated"
            width={width}
            docId={docInfo?.id}
            version={runId}
            onNavigatePage={select}
            {...mark}
          />
          {page.status === 'fallback' && <span className="absolute inset-y-0 -left-[5px] w-[3px] bg-red" aria-hidden="true" />}
        </div>
      )
    }
    if (phase === 'idle') {
      return (
        <OutputPlaceholder
          width={width}
          height={height}
          title="Not translated yet"
          body="Choose languages in the inspector and select Translate PDF."
        />
      )
    }
    if (phase === 'processing') {
      const placeholderTitle = progressSubtitle
        ? `Translating document (${progressSubtitle})`
        : `Translating document (${overallPct != null ? `${overallPct}%` : `Page ${Math.max(1, Math.min(done || 1, totalPages))} of ${totalPages}`})`
      return (
        <OutputPlaceholder
          width={width}
          height={height}
          busy={true}
          title={placeholderTitle}
          body={telemetry.message || "Extracting equations, translating prose with neural MT, and typesetting layout..."}
        />
      )
    }
    if (phase === 'rate-limited') {
      return (
        <OutputPlaceholder
          width={width}
          height={height}
          busy={false}
          title="Google Translate Rate Limit (HTTP 429)"
          body="Google temporarily rate-limited public requests due to volume. Open Settings or Inspector to select Gemini or an OpenAI-compatible provider (DeepSeek / Groq) to continue."
        />
      )
    }
    if (phase === 'provider-error') {
      return (
        <OutputPlaceholder
          width={width}
          height={height}
          busy={false}
          title="Translation encountered an error"
          body="Please check provider settings or network connection and retry."
        />
      )
    }
    return (
      <OutputPlaceholder
        width={width}
        height={height}
        title="Translation paused"
        body="You can resume from where you left off."
      />
    )
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <AppHeader
        center={<div className="flex min-w-0 items-center gap-3 overflow-hidden">
          <IconFile className="size-4 shrink-0 text-teal" />
          <span className="truncate max-w-[200px] text-[14px] font-bold">{docInfo?.name || 'Research-Paper.pdf'}</span>
          <span className="shrink-0 font-mono text-[12px] text-muted">{totalPages} pp</span>
          <span className="h-4 w-px shrink-0 bg-line" />
          <StatusIndicator state={docState} />
          <span className="hidden sm:inline shrink-0 text-[12.5px] text-muted font-medium">{src} → {tgt}</span>
        </div>}
        right={<>
          <Button variant="ghost" size="sm" onClick={onClose}>Close document</Button>
          {phase === 'done' && <Button variant="primary" size="sm" onClick={() => setExportOpen(true)}><IconDownload />Export PDF</Button>}
        </>}
        onHelp={onHelp}
      />
      <div className="flex min-h-0 flex-1">
        {rail}
        <PageNavigator current={cur} onSelect={select} known={known} pages={docPages} total={totalPages} docId={docInfo?.id} />
        <div className="flex min-w-0 flex-1 flex-col">
          <ComparisonToolbar page={cur} setPage={select} total={totalPages} zoomPct={pct} zoomIn={() => setZ(0.1)} zoomOut={() => setZ(-0.1)} fit={() => setZoom(null)} isFit={zoom === null} mode={mode} setMode={setMode} inspectorOpen={inspectorOpen} toggleInspector={() => setInspectorOpen((o) => !o)} />
          {docInfo?.isScanned && (
            <div role="alert" className="flex items-center gap-2.5 border-b border-amber-200 bg-amber-50 px-4 py-2 text-[12.5px] text-amber-900">
              <IconAlert className="size-4 shrink-0 text-amber-600" />
              <span className="font-medium">
                {docInfo.scanWarning || 'Scanned document detected: Pages appear to contain image-only scans without selectable text layers. LayoutLingua specializes in digital vector typography; an OCR pre-processing step is recommended.'}
              </span>
            </div>
          )}
          {issue && (() => { const m = sevMeta[issue.severity]; return (
            <div role="status" className="flex h-10 shrink-0 items-center gap-3 border-b border-line bg-white px-4 text-[12.5px]">
              <span className={`flex items-center gap-1.5 font-semibold ${m.text}`}><span className="font-mono">{vi + 1}</span><m.Icon className="size-3.5" />{m.label}</span>
              <span className="truncate font-semibold">{issue.title}</span>
              <span className="truncate text-muted">Next: {issue.next}</span>
              <span className="ml-auto flex shrink-0 items-center gap-0.5">
                <span className="mr-1 font-mono text-muted">{vi + 1} of {visibleIssues.length}</span>
                <IconButton label="Previous issue" disabled={vi <= 0} onClick={() => openIssue(visibleIssues[vi - 1])} className="size-7 disabled:opacity-40"><IconChevL /></IconButton>
                <IconButton label="Next issue" disabled={vi >= visibleIssues.length - 1} onClick={() => openIssue(visibleIssues[vi + 1])} className="size-7 disabled:opacity-40"><IconChevR /></IconButton>
                <IconButton label="Close issue" onClick={() => { setActiveIssue(undefined); setHighlight(undefined) }} className="size-7"><IconX /></IconButton>
              </span>
            </div>
          ) })()}
          <div ref={canvasRef} className="min-h-0 flex-1 overflow-auto bg-canvas">
            <div className="flex min-h-full min-w-fit items-start justify-center gap-4 px-6 py-4">
              {mode === 'side' ? (
                <>
                  <PageFrame label="Source" sub={<>{src} · <span className="font-mono">p.{page.n}</span></>} width={width}>
                    <PdfPage page={page} type="source" width={width} docId={docInfo?.id} onNavigatePage={select} {...mark} />
                  </PageFrame>
                  <PageFrame label="Translated" sub={<>{tgt} · <PageState s={s} idle={phase === 'idle'} /></>} width={width}>
                    {output()}
                  </PageFrame>
                </>
              ) : (
                <PageFrame label="Overlay" width={width} sub={
                  <span className="flex items-center gap-2">
                    <button className={`font-semibold ${blend === 0 ? 'text-teal' : 'hover:text-ink'}`} onClick={() => setBlend(0)}>View source page</button>
                    <input type="range" min={0} max={100} value={blend} onChange={(e) => setBlend(+e.target.value)} aria-label="Blend between source and translated page" className="w-20 accent-teal" />
                    <button className={`font-semibold ${blend === 100 ? 'text-teal' : 'hover:text-ink'}`} onClick={() => setBlend(100)}>View translated page</button>
                  </span>
                }>
                  <div className="relative">
                    <PdfPage page={page} type="source" width={width} docId={docInfo?.id} onNavigatePage={select} {...mark} />
                    <div className="absolute inset-0" style={{ opacity: blend / 100 }}>{output()}</div>
                  </div>
                </PageFrame>
              )}
            </div>
          </div>
          <IntegrityStrip
            known={known}
            done={isFullDoc ? done : Math.min(activeSelectedCount, done)}
            total={isFullDoc ? totalPages : activeSelectedCount}
            phase={phase}
            current={cur}
            onSelect={select}
            pages={docPages}
            counts={counts}
            rangeLabel={isFullDoc ? undefined : `pp. ${rangeFrom}–${rangeTo}`}
          />
        </div>
        {inspectorOpen && (
          <Inspector
            tab={tab}
            setTab={setTab}
            phase={phase}
            done={isFullDoc ? done : Math.min(activeSelectedCount, done)}
            total={isFullDoc ? totalPages : activeSelectedCount}
            stage={stage}
            page={page}
            pageState={pageLabel(s)}
            src={src}
            tgt={tgt}
            setSrc={handleSetSrc}
            setTgt={handleSetTgt}
            pageRange={pageRange}
            setPageRange={handleSetPageRange}
            settings={settings}
            onUpdateProvider={(pr) => updateSettings((prev) => ({ ...prev, provider: pr }))}
            onOpenSettings={onOpenSettings}
            visibleIssues={visibleIssues}
            activeIssue={activeIssue}
            openIssue={openIssue}
            start={start}
            cancel={() => {
              fetch(apiUrl('/api/cancel'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ doc_id: docInfo?.id || 'sample_academic' }),
              }).catch(() => {})
              setPhase('cancelled')
            }}
            onExport={() => setExportOpen(true)}
            retryPage={retryPage}
            retrying={retrying}
            telemetry={telemetry}
            overallPct={overallPct}
            subtitle={progressSubtitle}
          />
        )}
      </div>
      {exportOpen && (
        <ExportDialog
          initialDocName={docInfo?.name}
          docId={docInfo?.id}
          totalPages={totalPages}
          targetLang={tgt}
          translatedCount={done}
          onClose={() => setExportOpen(false)}
          needsReview={counts.review}
          preserved={docPages.filter((p) => p.n <= done && p.status === 'fallback').map((p) => p.n)}
        />
      )}
    </div>
  )
}
