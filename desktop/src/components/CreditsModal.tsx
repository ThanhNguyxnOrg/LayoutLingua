import { useEffect } from 'react'
import { IconX, IconGitHub, IconBug, IconHeart } from './icons'

const REPO = 'ThanhNguyxnOrg/LayoutLingua'
const REPO_URL = `https://github.com/${REPO}`
const APP_VERSION = '2.0.0'

export default function CreditsModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const platform = typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown'
  const engine = '__TAURI_INTERNALS__' in window ? 'desktop app (Tauri · Python engine :8765)' : 'browser dev preview (Python engine :8765)'
  // Prefills match the field ids in .github/ISSUE_TEMPLATE/bug_report.yml
  const issueUrl =
    `https://github.com/${REPO}/issues/new?template=bug_report.yml` +
    `&app_version=${encodeURIComponent(APP_VERSION)}` +
    `&description=${encodeURIComponent(`Engine: ${engine}\nPlatform: ${platform}\n\nWhat happened:\n`)}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-xs p-6 select-none animate-in fade-in duration-150">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="credits-title"
        className="w-[520px] max-w-full rounded-xl border border-line bg-white shadow-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4 bg-canvas/40">
          <div className="flex items-center gap-2.5">
            <IconHeart className="size-4 text-teal" />
            <h2 id="credits-title" className="text-[16px] font-bold text-ink">
              Credits &amp; Source
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

        <div className="p-6 space-y-5">
          <div className="flex items-center gap-3 rounded-lg border border-line bg-canvas/30 px-4 py-3.5">
            <img src="/logo.png" alt="LayoutLingua Logo" className="size-10 rounded-lg object-contain shadow-2xs ring-1 ring-line-strong/40" />
            <div className="min-w-0 flex-1">
              <p className="text-[14.5px] font-extrabold text-ink">
                LayoutLingua <span className="font-mono text-[11.5px] font-bold text-muted">v{APP_VERSION}</span>
              </p>
              <p className="text-[12px] text-muted">Layout-aware academic PDF translation · MIT License</p>
            </div>
          </div>

          <div className="rounded-lg border border-teal/30 bg-teal-soft/40 p-4">
            <h4 className="mb-1 flex items-center gap-1.5 font-bold text-teal">
              <IconGitHub className="size-4" /> Open Source
            </h4>
            <p className="mb-3 text-[12.5px] leading-relaxed text-muted">
              LayoutLingua is free, open-source software. Star the repo, read the source, or file an
              issue — every report ships with your app version and platform pre-filled.
            </p>
            <div className="flex flex-wrap gap-2">
              <a
                href={REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-white px-3.5 py-2 text-[13px] font-bold text-ink shadow-2xs transition-colors hover:border-teal hover:text-teal"
              >
                <IconGitHub className="size-4" /> Source repository
              </a>
              <a
                href={issueUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-teal px-3.5 py-2 text-[13px] font-bold text-white shadow-2xs transition-colors hover:bg-teal-600"
              >
                <IconBug className="size-4" /> Report an Issue
              </a>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-line bg-canvas/20 px-6 py-3.5">
          <span className="text-[11.5px] text-faint">
            © 2026 LayoutLingua Contributors · MIT
          </span>
          <button
            onClick={onClose}
            className="rounded-md border border-line-strong bg-white px-3.5 py-1.5 text-[13px] font-bold text-ink shadow-2xs transition-colors hover:border-teal hover:text-teal cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
