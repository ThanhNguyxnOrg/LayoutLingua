import type { ReactNode, ButtonHTMLAttributes } from 'react'
import type { Issue, Severity } from './data'
import { IconAlert, IconCheck, IconError, IconInfo, IconChevR } from './icons'

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md' }
export function Button({ variant = 'secondary', size = 'md', className = '', ...rest }: BtnProps) {
  const v = {
    primary: 'bg-teal text-white hover:bg-[#0F6A6D] disabled:bg-line-strong disabled:text-white',
    secondary: 'bg-white text-ink border border-line-strong hover:bg-canvas',
    ghost: 'text-ink hover:bg-ink/5',
    danger: 'bg-red text-white hover:bg-[#9C3F3F]',
  }[variant]
  const s = size === 'sm' ? 'h-8 px-3 text-[13px] gap-1.5' : 'h-9 px-4 text-sm gap-2'
  return <button className={`inline-flex items-center justify-center rounded-md font-semibold transition-colors disabled:cursor-not-allowed ${v} ${s} ${className}`} {...rest} />
}

export function IconButton({ label, children, active, className = '', ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; active?: boolean }) {
  return (
    <button aria-label={label} title={label} aria-pressed={active} className={`inline-flex size-8 items-center justify-center rounded-md transition-colors ${active ? 'bg-teal-soft text-teal' : 'text-muted hover:bg-ink/5 hover:text-ink'} ${className}`} {...rest}>
      {children}
    </button>
  )
}

export const sevMeta: Record<Severity, { label: string; text: string; bg: string; Icon: (p: { className?: string }) => ReactNode }> = {
  info: { label: 'Notice', text: 'text-info', bg: 'bg-info-soft', Icon: IconInfo },
  warning: { label: 'Needs review', text: 'text-amber-ink', bg: 'bg-amber-soft', Icon: IconAlert },
  failure: { label: 'Preserved from source', text: 'text-red', bg: 'bg-red-soft', Icon: IconError },
}

export type DocState = 'not-started' | 'processing' | 'review' | 'done' | 'failed'
export function StatusIndicator({ state }: { state: DocState }) {
  const m = {
    'not-started': { t: 'Not translated', c: 'text-muted', dot: 'border border-faint' },
    processing: { t: 'Translating', c: 'text-teal', dot: 'bg-teal ll-pulse' },
    review: { t: 'Needs review', c: 'text-amber-ink', dot: 'bg-amber' },
    done: { t: 'Translated', c: 'text-teal', dot: 'bg-teal' },
    failed: { t: 'Failed', c: 'text-red', dot: 'bg-red' },
  }[state]
  return (
    <span className={`inline-flex items-center gap-1.5 text-[13px] font-semibold ${m.c}`}>
      <span className={`size-2 rounded-full ${m.dot}`} aria-hidden="true" />
      {m.t}
    </span>
  )
}

export function ProgressBar({ value, max, label }: { value: number; max: number; label: string }) {
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} className="h-1.5 w-full overflow-hidden rounded-full bg-line">
      <div className="h-full rounded-full bg-teal transition-[width] duration-500" style={{ width: `${(value / max) * 100}%` }} />
    </div>
  )
}

export function IssueRow({ issue, index, active, onOpen }: { issue: Issue; index: number; active?: boolean; onOpen: () => void }) {
  const m = sevMeta[issue.severity]
  return (
    <button onClick={onOpen} className={`group relative w-full border-b border-line px-4 py-3 text-left transition-colors ${active ? 'bg-canvas' : 'hover:bg-canvas/70'}`}>
      {active && <span className="absolute inset-y-0 left-0 w-[3px] bg-teal" aria-hidden="true" />}
      <div className="flex items-start gap-3">
        <span className={`mt-px w-4 shrink-0 text-center font-mono text-[12px] font-medium ${m.text}`}>{index}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-[12px]">
            <m.Icon className={`size-3.5 ${m.text}`} /><span className={`font-semibold ${m.text}`}>{m.label}</span>
            <span className="text-faint">·</span>
            <span className="font-mono text-muted">p.{issue.page}</span>
          </div>
          <p className="mt-0.5 text-[13.5px] leading-snug font-semibold text-ink">{issue.title}</p>
          {active ? <>
            <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{issue.detail}</p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink"><span className="font-semibold">Next: </span>{issue.next}</p>
          </> : <span className="mt-1 inline-flex items-center gap-1 text-[12.5px] font-semibold text-teal group-hover:underline">{issue.action}<IconChevR className="size-3.5" /></span>}
        </div>
      </div>
    </button>
  )
}

export function StateNotice({ tone, icon, title, children, actions }: { tone: 'neutral' | 'warning' | 'error' | 'success'; icon: ReactNode; title: string; children: ReactNode; actions?: ReactNode }) {
  const c = { neutral: 'bg-canvas text-muted', warning: 'bg-amber-soft text-amber-ink', error: 'bg-red-soft text-red', success: 'bg-teal-soft text-teal' }[tone]
  return (
    <div className="flex gap-3">
      <span className={`flex size-9 shrink-0 items-center justify-center rounded-md ${c}`}>{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-[15px] font-bold text-ink">{title}</p>
        <div className="mt-1 text-[13.5px] leading-relaxed text-muted">{children}</div>
        {actions && <div className="mt-3 flex flex-wrap gap-2">{actions}</div>}
      </div>
    </div>
  )
}



export { IconCheck }
