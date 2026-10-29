import { useEffect } from 'react'
import { IconX } from './icons'
import { Button } from './ui'

export default function HelpModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const shortcuts = [
    { key: 'Ctrl + O', desc: 'Open PDF document from disk' },
    { key: 'Ctrl + Enter', desc: 'Start document translation' },
    { key: 'Ctrl + S', desc: 'Export translated PDF document' },
    { key: '← / →', desc: 'Navigate to previous / next page' },
    { key: '+ / -', desc: 'Zoom in / zoom out document canvas' },
    { key: '0', desc: 'Fit document to page view' },
    { key: 'Tab', desc: 'Switch between Inspector tabs' },
    { key: 'Esc', desc: 'Close dialogs or cancel active modal' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-xs p-6 select-none animate-in fade-in duration-150">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-title"
        className="w-[580px] max-w-full rounded-xl border border-line bg-white shadow-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4 bg-canvas/40">
          <div className="flex items-center gap-2.5">
            <h2 id="help-title" className="text-[16px] font-bold text-ink">
              Keyboard Shortcuts & Help
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1.5 text-muted hover:bg-canvas hover:text-ink transition-colors"
          >
            <IconX className="size-4" />
          </button>
        </div>

        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          <div>
            <h3 className="text-[13px] font-bold tracking-wider uppercase text-muted mb-3">
              Essential Shortcuts
            </h3>
            <div className="grid grid-cols-1 gap-2">
              {shortcuts.map((sc) => (
                <div
                  key={sc.key}
                  className="flex items-center justify-between rounded-lg border border-line/60 bg-canvas/30 px-3.5 py-2 text-[13px]"
                >
                  <span className="text-ink font-medium">{sc.desc}</span>
                  <kbd className="rounded border border-line-strong bg-white px-2 py-0.5 font-mono text-[11.5px] font-bold text-ink shadow-2xs">
                    {sc.key}
                  </kbd>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-teal/30 bg-teal-soft/40 p-4 text-[13px] text-ink">
            <h4 className="font-bold text-teal mb-1">Layout Preservation Guarantee</h4>
            <p className="text-muted leading-relaxed text-[12.5px]">
              LayoutLingua extracts visual vector structures, table lines, equations, and typography
              metrics into a Decoupled IR before translation. Text is dynamically fitted into original
              bounds with strict ink floors to prevent diacritic overlaps.
            </p>
          </div>
        </div>

        <div className="flex justify-end border-t border-line bg-canvas/20 px-6 py-3.5">
          <Button variant="primary" size="sm" onClick={onClose}>
            Got it
          </Button>
        </div>
      </div>
    </div>
  )
}
