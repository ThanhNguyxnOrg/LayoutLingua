import type { ReactNode } from 'react'
import { IconFile, IconHistory, IconSettings, IconHelp } from './icons'
import { IconButton } from './ui'

export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex size-7 items-center justify-center rounded-md bg-teal text-white font-mono text-xs font-bold shadow-sm">
        LL
      </div>
      <span className="text-[15.5px] font-extrabold tracking-[-0.015em] text-ink">
        Layout<span className="text-teal">Lingua</span>
      </span>
    </div>
  )
}

export function AppHeader({
  center,
  right,
  onHelp,
}: {
  center?: ReactNode
  right?: ReactNode
  onHelp?: () => void
}) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-line bg-white px-4 select-none">
      <div className="w-[196px] shrink-0">
        <Wordmark />
      </div>
      <div className="flex min-w-0 flex-1 items-center gap-3">{center}</div>
      <div className="flex items-center gap-2">
        {right}
        <IconButton label="Help and keyboard shortcuts" onClick={onHelp}>
          <IconHelp className="size-4 text-muted hover:text-ink" />
        </IconButton>
      </div>
    </header>
  )
}

export type RailItem = 'documents' | 'history' | 'settings'

export function NavRail({
  active,
  onChange,
}: {
  active: RailItem
  onChange: (r: RailItem) => void
}) {
  const items: [RailItem, string, typeof IconFile][] = [
    ['documents', 'Documents', IconFile],
    ['history', 'Recent history', IconHistory],
    ['settings', 'Settings', IconSettings],
  ]
  return (
    <nav
      aria-label="Primary"
      className="flex w-14 shrink-0 flex-col items-center gap-1.5 border-r border-line bg-white py-3.5 select-none"
    >
      {items.map(([id, label, I]) => (
        <div key={id} className="group relative">
          <IconButton
            label={label}
            active={active === id}
            onClick={() => onChange(id)}
            className="size-10 rounded-lg transition-all"
          >
            <I className="size-5" />
          </IconButton>
          <span
            role="tooltip"
            className="pointer-events-none absolute top-1/2 left-full z-50 ml-2 -translate-y-1/2 rounded-md bg-ink px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-white opacity-0 shadow-md transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
          >
            {label}
          </span>
        </div>
      ))}
    </nav>
  )
}
