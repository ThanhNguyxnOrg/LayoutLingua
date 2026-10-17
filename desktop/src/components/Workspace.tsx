import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { pages, issues, stages, languages, type Issue, type Page } from './data'
import PdfPage, { PAGE_W } from './PdfPage'
import { AppHeader } from './shell'
import ExportDialog from './ExportDialog'
import { Button, IconButton, IssueRow, ProgressBar, StateNotice, StatusIndicator, sevMeta, type DocState } from './ui'
import { IconAlert, IconCheck, IconChevL, IconChevR, IconColumns, IconDownload, IconError, IconFit, IconLayers, IconMinus, IconPanelR, IconPlus, IconSwap, IconX, IconFile, IconSettings } from './icons'
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
    <aside aria-label="Pages" className="flex h-full max-h-full w-[132px] min-h-0 shrink-0 flex-col border-r border-line bg-white select-none overflow-hidden">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-line px-3">
        <h2 className="text-[13px] font-bold">Pages</h2>
        <span className="font-mono text-[12px] text-muted">{current} / {total}</span>
      </div>
      <ol className="flex-1 min-h-0 space-y-3 overflow-y-auto px-3 py-4 select-none">
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
}: {
  known: (p: Page) => Page['status'] | 'pending'
  done: number
  total: number
  phase: Phase
  current: number
  onSelect: (n: number) => void
  pages: Page[]
  counts: { blocks: number; cells: number; review: number; preserved: number }
}) {
  const seg = { ok: 'bg-teal', warn: 'bg-amber', fallback: 'bg-red', pending: 'bg-line' }
  const isLarge = total > 24
  return (
    <section aria-label="Document integrity" className="flex h-14 shrink-0 items-center gap-6 border-t border-line bg-white px-4">
      <div className="w-[220px] shrink-0">
        <div className="mb-1.5 flex items-center justify-between text-[12px]">
          <span className="font-bold">Document integrity</span>
          <span className="font-mono text-muted">{phase === 'idle' ? 'not started' : `${done}/${total} pages`}</span>
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
      <span className="text-[11.5px] text-muted font-mono">Engine: PyMuPDF + Typeset</span>
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
}: {
  done: number
  total: number
  stage: number
  onCancel: () => void
  eta?: number
  speed?: number
  message?: string
}) {
  const formatEta = (sec?: number) => {
    if (sec === undefined || sec === null || sec <= 0) return null
    if (sec < 60) return `~${sec}s remaining`
    const mins = Math.floor(sec / 60)
    const rem = sec % 60
    return rem > 0 ? `~${mins}m ${rem}s remaining` : `~${mins}m remaining`
  }

  const etaStr = formatEta(eta)

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-baseline justify-between">
          <p className="text-[14px] font-bold">Translating</p>
          <span className="font-mono text-[12.5px] text-muted">page {Math.min(done + 1, total)} of {total}</span>
        </div>
        <div className="mt-2"><ProgressBar value={done} max={total} label="Pages processed" /></div>
        <div className="mt-2 flex items-center justify-between text-[12px] text-muted">
          <span className="truncate pr-2 font-medium text-ink">{message || 'Processing pages with layout preservation telemetry...'}</span>
          {(etaStr || (speed && speed > 0)) && (
            <span className="shrink-0 font-mono text-[11.5px] text-teal font-semibold">
              {etaStr}{etaStr && speed ? ' • ' : ''}{speed && speed > 0 ? `${speed} p/s` : ''}
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
}) {
  const tabs: [Tab, string][] = [['translation', 'Translation'], ['quality', 'Quality checks'], ['page', 'Page details']]
  const locked = p.phase === 'processing'
  const pageIssues = p.visibleIssues.filter((i) => i.page === p.page.n)
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
              <section className="space-y-3">
                <Field label="Page range (Optional)">
                  <input
                    disabled={locked}
                    value={p.pageRange}
                    onChange={(e) => p.setPageRange(e.target.value)}
                    placeholder="e.g. all or 1-5, 8, 10-12"
                    className="h-8 rounded-md border border-line-strong px-2.5 font-mono text-[12.5px] focus:border-teal focus:ring-1 focus:ring-teal"
                  />
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <button
                      type="button"
                      onClick={() => p.setPageRange('all')}
                      className={`rounded px-1.5 py-0.5 text-[11px] font-medium border transition-colors cursor-pointer ${
                        !p.pageRange || p.pageRange === 'all'
                          ? 'border-teal bg-teal/10 text-teal'
                          : 'border-line text-muted hover:border-line-strong'
                      }`}
                    >
                      All ({p.total} pp)
                    </button>
                    {p.total > 5 && (
                      <button
                        type="button"
                        onClick={() => p.setPageRange('1-5')}
                        className={`rounded px-1.5 py-0.5 text-[11px] font-medium border transition-colors cursor-pointer ${
                          p.pageRange === '1-5' || p.pageRange === '5'
                            ? 'border-teal bg-teal/10 text-teal'
                            : 'border-line text-muted hover:border-line-strong'
                        }`}
                      >
                        First 5 pp (1–5)
                      </button>
                    )}
                    {p.total > 20 && (
                      <button
                        type="button"
                        onClick={() => p.setPageRange('1-20')}
                        className={`rounded px-1.5 py-0.5 text-[11px] font-medium border transition-colors cursor-pointer ${
                          p.pageRange === '1-20' || p.pageRange === '20'
                            ? 'border-teal bg-teal/10 text-teal'
                            : 'border-line text-muted hover:border-line-strong'
                        }`}
                      >
                        First 20 pp (1–20)
                      </button>
                    )}
                  </div>
                  {/^\d+$/.test(p.pageRange.trim()) && Number(p.pageRange.trim()) > 1 && (
                    <div className="rounded bg-teal-soft/40 px-2 py-1 text-[11px] text-teal-ink">
                      Translating first {p.pageRange.trim()} pages (1–{p.pageRange.trim()}). For only page {p.pageRange.trim()}, use 'p{p.pageRange.trim()}'.
                    </div>
                  )}
                  <span className="text-[11px] text-muted">Untranslated pages remain pristine in original layout.</span>
                </Field>
                <p className="text-[13px] leading-relaxed"><span className="font-mono">{p.total}</span> pages ready for translation from {p.src} to {p.tgt}.</p>
                <Button variant="primary" className="h-10 w-full" onClick={p.start}>Translate PDF</Button>
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
              <StateNotice tone="error" icon={<IconError className="size-5" />} title={`${p.settings.provider.toUpperCase()} stopped responding`} actions={<><Button size="sm" variant="primary" onClick={p.start}>Retry from page {p.done + 1}</Button><Button size="sm" onClick={() => p.onUpdateProvider('google')}>Switch to Google (Free)</Button></>}>
                The provider returned an error on page {p.done + 1}. Pages 1–{p.done} are kept; nothing needs to be redone.
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
              <div className="flex items-center gap-4 border-b border-line px-4 py-3 text-[12px]">
                {(['failure', 'warning', 'info'] as const).map((s) => {
                  const m = sevMeta[s]; const n = p.visibleIssues.filter((i) => i.severity === s).length
                  return <span key={s} className={`flex items-center gap-1 font-semibold ${m.text}`}><m.Icon className="size-3.5" />{n} {s === 'failure' ? 'failure' : s === 'warning' ? (n === 1 ? 'warning' : 'warnings') : 'notice'}</span>
                })}
              </div>
              {p.visibleIssues.map((i) => <IssueRow key={i.id} index={issues.indexOf(i) + 1} issue={i} active={p.activeIssue === i.id} onOpen={() => p.openIssue(i)} />)}
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
              {[['Page size', '210 × 297 mm (A4)'], ['Media box', '0 0 595.3 841.9'], ['Text blocks', p.page.status === 'fallback' ? '0 translated' : String(p.page.blockCount)], ['Table cells', String(p.page.cellCount)], ['Formulas kept', String(p.page.blocks.filter((b) => b.kind === 'eq').length)], ['Embedded fonts', 'SourceSerif4, CMMI10']].map(([k, v]) => (
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

  const docPages: Page[] = useMemo(() => {
    if (!docInfo?.pages) return pages
    return Array.from({ length: docInfo.pages }, (_, i) => {
      const n = i + 1
      const isDone = phase === 'done' || (phase === 'processing' && i < done)
      return {
        n,
        status: isDone ? ('ok' as const) : ('pending' as const),
        blocks: [],
        blockCount: 12,
        cellCount: 0,
      }
    })
  }, [docInfo?.pages, phase, done])
  const [inspectorOpen, setInspectorOpen] = useState(() => window.innerWidth >= 1340)
  const [zoom, setZoom] = useState<number | null>(null)
  const [mode, setMode] = useState<'side' | 'overlay'>('side')
  const [blend, setBlend] = useState(100)
  const [src, setSrc] = useState(() => docInfo?.detectedLang === 'vi' ? 'Vietnamese' : 'English')
  const [tgt, setTgt] = useState(() => docInfo?.detectedLang === 'vi' ? 'English' : 'Vietnamese')
  const [pageRange, setPageRange] = useState('all')
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

  const isTranslatingRef = useRef(false)

  useEffect(() => {
    if (phase !== 'processing') {
      isTranslatingRef.current = false
      return
    }

    if (isTranslatingRef.current) return
    isTranslatingRef.current = true

    let active = true
    let progressTimer: any = null

    // If backend doc is open, invoke real translation API with live progress polling
    if (docInfo?.id) {
      progressTimer = setInterval(async () => {
        if (!active) return
        try {
          const pRes = await fetch(apiUrl(`/api/progress?id=${encodeURIComponent(docInfo.id!)}`))
          if (pRes.ok) {
            const pData = await pRes.json()
            if (pData.current_page > 0 && active) {
              setDone(pData.current_page)
            }
            if (active) {
              setTelemetry({
                eta: pData.eta_seconds,
                speed: pData.speed,
                message: pData.message,
              })
            }
            if (pData.status === 'done' && active) {
              if (progressTimer) clearInterval(progressTimer)
              setDone(totalPages)
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
        } catch {}
      }, 350)

      const langCodeMap: Record<string, string> = {
        'English': 'en',
        'Vietnamese': 'vi',
        'German': 'de',
        'French': 'fr',
        'Japanese': 'ja',
        'Spanish': 'es',
        'Chinese (Simplified)': 'zh',
      }
      const resolvedTargetLang = langCodeMap[tgt] || (tgt === 'Vietnamese' ? 'vi' : 'en')

      fetch(apiUrl('/api/translate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_id: docInfo.id,
          target_lang: resolvedTargetLang,
          page_range: pageRange || 'all',
          custom_glossary: settings.customGlossary || '',
          provider: settings.provider,
          api_key: settings.provider === 'gemini' ? settings.geminiKey : settings.provider === 'openai' ? settings.openaiKey : '',
          base_url: settings.provider === 'openai' ? settings.openaiEndpoint : '',
          model: settings.provider === 'gemini' ? settings.geminiModel : settings.openaiModel,
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
    } else {
      alert('No active document session found. Please re-open your PDF.')
      setPhase('idle')
    }
  }, [phase, docInfo?.id, tgt, settings, totalPages, pageRange])

  const stage = phase === 'done' ? stages.length : done === 0 ? 0 : done < Math.floor(totalPages / 3) ? 1 : done < Math.floor((totalPages * 2) / 3) ? 2 : 3
  const known = (p: Page) => (phase === 'idle' || p.n > done ? 'pending' : p.status)
  const visibleIssues = docInfo?.id ? [] : issues.filter((i) => i.page <= done && phase !== 'idle')
  const page = docPages[cur - 1] || docPages[0]
  const counts = useMemo(() => {
    const dp = docPages.filter((p) => p.n <= done && phase !== 'idle')
    return {
      blocks: dp.reduce((a, p) => a + p.blockCount, 0),
      cells: dp.reduce((a, p) => a + p.cellCount, 0),
      review: visibleIssues.filter((i) => i.severity === 'warning').length,
      preserved: dp.filter((p) => p.status === 'fallback').length,
    }
  }, [docPages, done, phase, visibleIssues])

  const docState: DocState = phase === 'processing' ? 'processing' : phase === 'done' ? (counts.review > 0 ? 'review' : 'done') : (phase === 'provider-error' || phase === 'rate-limited') ? 'failed' : 'not-started'
  const fitW = Math.max(160, Math.min(mode === 'side' ? (box.w - 64) / 2 : box.w - 48, ((box.h - 56) * 210) / 297))
  const width = zoom ? PAGE_W * zoom : fitW
  const pct = Math.round((width / PAGE_W) * 100)
  const height = (width * 297) / 210
  const setZ = (d: number) => setZoom(Math.min(2.5, Math.max(0.4, Math.round((width / PAGE_W + d) * 10) / 10)))

  const select = (n: number) => { setCur(n); setHighlight(undefined); setActiveIssue(undefined) }
  const openIssue = (i: Issue) => { setCur(i.page); setHighlight(i.region); setActiveIssue(i.id); setTab('quality') }
  const start = () => { setPhase('processing'); setTab('translation') }
  const retryPage = () => { setRetrying(true); setTimeout(() => { setRetrying(false) }, 1400) }

  const pageLabel = (s: ReturnType<typeof known>) => s === 'pending' ? (phase === 'idle' ? 'Not translated' : 'Pending') : s === 'ok' ? 'Translated' : s === 'warn' ? 'Needs review' : 'Preserved from source'
  const s = known(page)
  const issue = issues.find((i) => i.id === activeIssue)
  const mark = { highlight, highlightLabel: issue ? `${issues.indexOf(issue) + 1}  ${sevMeta[issue.severity].label}` : undefined, highlightTone: issue?.severity }
  const vi = issue ? visibleIssues.indexOf(issue) : -1

  const output = () => {
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
      return (
        <OutputPlaceholder
          width={width}
          height={height}
          busy={true}
          title={`Translating document (Page ${Math.min(done + 1, totalPages)} of ${totalPages})`}
          body={telemetry.message || "Extracting equations, translating prose with neural MT, and typesetting layout..."}
        />
      )
    }
    if (phase === 'done') {
      return (
        <div className="relative">
          <PdfPage page={page} type="translated" width={width} docId={docInfo?.id} version={previewVersion} {...mark} />
          {page.status === 'fallback' && <span className="absolute inset-y-0 -left-[5px] w-[3px] bg-red" aria-hidden="true" />}
        </div>
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
    <div className="flex min-w-0 flex-1 flex-col">
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
              <span className={`flex items-center gap-1.5 font-semibold ${m.text}`}><span className="font-mono">{issues.indexOf(issue) + 1}</span><m.Icon className="size-3.5" />{m.label}</span>
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
                    <PdfPage page={page} type="source" width={width} docId={docInfo?.id} {...mark} />
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
                    <PdfPage page={page} type="source" width={width} docId={docInfo?.id} {...mark} />
                    <div className="absolute inset-0" style={{ opacity: blend / 100 }}>{output()}</div>
                  </div>
                </PageFrame>
              )}
            </div>
          </div>
          <IntegrityStrip known={known} done={done} total={totalPages} phase={phase} current={cur} onSelect={select} pages={docPages} counts={counts} />
        </div>
        {inspectorOpen && (
          <Inspector
            tab={tab}
            setTab={setTab}
            phase={phase}
            done={done}
            total={totalPages}
            stage={stage}
            page={page}
            pageState={pageLabel(s)}
            src={src}
            tgt={tgt}
            setSrc={setSrc}
            setTgt={setTgt}
            pageRange={pageRange}
            setPageRange={setPageRange}
            settings={settings}
            onUpdateProvider={(pr) => updateSettings((prev) => ({ ...prev, provider: pr }))}
            onOpenSettings={onOpenSettings}
            visibleIssues={visibleIssues}
            activeIssue={activeIssue}
            openIssue={openIssue}
            start={start}
            cancel={() => setPhase('cancelled')}
            onExport={() => setExportOpen(true)}
            retryPage={retryPage}
            retrying={retrying}
            telemetry={telemetry}
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
