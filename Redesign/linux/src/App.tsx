import { useState } from "react"

/* ---------- Symbolic-style icons (16px, currentColor) ---------- */

function IconDocumentEdit({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}>
      <path
        d="M9 1.5H4A1.5 1.5 0 0 0 2.5 3v10A1.5 1.5 0 0 0 4 14.5h6A1.5 1.5 0 0 0 11.5 13V6"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M11.4 1.9a1.2 1.2 0 0 1 1.7 1.7l-4 4-2.2.5.5-2.2 4-4Z"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconMinimize({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}>
      <path d="M4 8.5h8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

function IconClose({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}>
      <path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

function IconPlus({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}>
      <path d="M8 3.5v9M3.5 8h9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function IconChevron({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}>
      <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function IconCheck({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}>
      <path d="M3.5 8.5l3 3 6-7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} style={{ animation: "adw-spin 0.9s linear infinite" }}>
      <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeOpacity="0.22" strokeWidth="1.6" />
      <path d="M8 1.8a6.2 6.2 0 0 1 6.2 6.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

/* ---------- App ---------- */

const VIEWS = ["Documents", "Active Batches", "Preferences"] as const
const LANGUAGES = [
  "Spanish (Español)",
  "French (Français)",
  "German (Deutsch)",
  "Japanese (日本語)",
  "Portuguese (Português)",
]

export default function App() {
  const [view, setView] = useState<(typeof VIEWS)[number]>("Documents")
  const [overwrite, setOverwrite] = useState(false)
  const [language, setLanguage] = useState(LANGUAGES[0])
  const [comboOpen, setComboOpen] = useState(false)

  return (
    <div className="size-full flex items-center justify-center bg-black/60 p-4 text-adw-fg">
      {/* Window */}
      <div className="flex h-[840px] w-[1280px] flex-col overflow-hidden rounded-xl border border-adw-border bg-adw-window shadow-[0_28px_80px_-12px_rgba(0,0,0,0.75)]">
        {/* HeaderBar */}
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-adw-border bg-adw-headerbar px-3">
          {/* Left: view switcher */}
          <div className="flex items-center gap-0.5 rounded-full bg-white/[0.05] p-0.5">
            {VIEWS.map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-full px-4 py-1.5 text-[13px] font-medium transition-colors ${
                  view === v
                    ? "bg-white/[0.13] text-adw-fg shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]"
                    : "text-adw-dim hover:bg-white/[0.06] hover:text-adw-fg"
                }`}
              >
                {v}
              </button>
            ))}
          </div>

          {/* Center: window title */}
          <div className="flex flex-1 items-center justify-center gap-2">
            <img src="/logo.png" alt="LayoutLingua Logo" className="h-5 w-5 rounded object-contain shadow-[0_0_8px_rgba(53,132,228,0.5)]" />
            <div className="flex flex-col items-center justify-center leading-tight">
              <span className="text-[14px] font-bold">LayoutLingua</span>
              <span className="text-[11px] text-adw-dim">Precision PDF Translation</span>
            </div>
          </div>

          {/* Right: primary + window controls */}
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 rounded-lg bg-adw-accent px-3 py-1.5 text-[13px] font-bold text-white shadow-[0_1px_0_rgba(255,255,255,0.14)_inset] transition-colors hover:bg-adw-accent-hover active:brightness-95">
              <IconPlus className="h-4 w-4" />
              Add Document…
            </button>
            <div className="flex items-center gap-1">
              <button className="flex h-6 w-6 items-center justify-center rounded-full bg-white/[0.08] text-adw-fg/80 transition-colors hover:bg-white/[0.14]">
                <IconMinimize className="h-4 w-4" />
              </button>
              <button className="flex h-6 w-6 items-center justify-center rounded-full bg-white/[0.08] text-adw-fg/80 transition-colors hover:bg-[#c01c28] hover:text-white">
                <IconClose className="h-4 w-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Content — Clamp pattern */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-[900px] flex-col gap-8 px-6 py-10">
            {/* 1. Ingestion box */}
            <section className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-[#3584e4]/40 bg-adw-card px-6 py-12 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#3584e4]/12 text-adw-accent">
                <IconDocumentEdit className="h-8 w-8" />
              </div>
              <div className="flex flex-col gap-1">
                <h2 className="text-[19px] font-bold">Drop PDF Files Here</h2>
                <p className="text-[13px] text-adw-dim">
                  Layout, tables, and figures are preserved during translation.
                </p>
              </div>
              <button className="mt-1 rounded-lg bg-white/[0.08] px-4 py-2 text-[13px] font-medium text-adw-fg shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)] transition-colors hover:bg-white/[0.13]">
                Select Files from Disk
              </button>
            </section>

            {/* 2. Preferences group — queue */}
            <section className="flex flex-col gap-2.5">
              <h3 className="px-1 text-[13px] font-bold text-adw-dim">Translation Queue</h3>
              <div className="overflow-hidden rounded-xl border border-adw-border bg-adw-card">
                {/* Row 1 — in progress */}
                <div className="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-adw-card-hover">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-medium">Machine_Learning_Foundations.pdf</p>
                    <p className="mt-0.5 text-[12.5px] text-adw-dim">65% · Typesetting page 24 of 38</p>
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-white/[0.08]">
                      <div className="h-full rounded-full bg-adw-accent" style={{ width: "65%" }} />
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <Spinner className="h-4 w-4 text-adw-accent" />
                    <button className="rounded-lg bg-white/[0.08] px-3 py-1.5 text-[12.5px] font-medium text-adw-fg transition-colors hover:bg-white/[0.13]">
                      Cancel
                    </button>
                  </div>
                </div>

                <div className="mx-4 h-px bg-adw-border" />

                {/* Row 2 — pending */}
                <div className="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-adw-card-hover">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-medium">Microbiology_Lab_Manual.pdf</p>
                    <p className="mt-0.5 text-[12.5px] text-adw-dim">Pending in queue</p>
                  </div>
                  <button className="shrink-0 rounded-lg bg-white/[0.08] px-3 py-1.5 text-[12.5px] font-medium text-adw-fg transition-colors hover:bg-[#c01c28]">
                    Remove
                  </button>
                </div>
              </div>
            </section>

            {/* Settings group */}
            <section className="flex flex-col gap-2.5">
              <h3 className="px-1 text-[13px] font-bold text-adw-dim">Output Settings</h3>
              <div className="overflow-hidden rounded-xl border border-adw-border bg-adw-card">
                {/* Combo row */}
                <div className="relative">
                  <button
                    onClick={() => setComboOpen((o) => !o)}
                    className="flex w-full items-center gap-4 px-4 py-3.5 text-left transition-colors hover:bg-adw-card-hover"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-[14px] font-medium">Target Language</p>
                      <p className="mt-0.5 text-[12.5px] text-adw-dim">Applied to every document in the batch</p>
                    </div>
                    <span className="text-[13px] text-adw-dim">{language}</span>
                    <IconChevron className={`h-4 w-4 text-adw-dim transition-transform ${comboOpen ? "rotate-90" : ""}`} />
                  </button>
                  {comboOpen && (
                    <div className="absolute right-4 top-[calc(100%-6px)] z-10 w-64 overflow-hidden rounded-xl border border-adw-border bg-adw-headerbar py-1 shadow-[0_16px_40px_-8px_rgba(0,0,0,0.6)]">
                      {LANGUAGES.map((l) => (
                        <button
                          key={l}
                          onClick={() => {
                            setLanguage(l)
                            setComboOpen(false)
                          }}
                          className="flex w-full items-center justify-between px-4 py-2 text-left text-[13px] transition-colors hover:bg-white/[0.07]"
                        >
                          {l}
                          {language === l && <IconCheck className="h-4 w-4 text-adw-accent" />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="mx-4 h-px bg-adw-border" />

                {/* Toggle row */}
                <div className="flex items-center gap-4 px-4 py-3.5">
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-medium">Overwrite Original Files</p>
                    <p className="mt-0.5 text-[12.5px] text-adw-dim">Replace source PDFs instead of creating copies</p>
                  </div>
                  <button
                    role="switch"
                    aria-checked={overwrite}
                    onClick={() => setOverwrite((o) => !o)}
                    className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                      overwrite ? "bg-adw-accent" : "bg-white/[0.14]"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                        overwrite ? "translate-x-[22px]" : "translate-x-0.5"
                      }`}
                    />
                  </button>
                </div>
              </div>
            </section>
          </div>
        </div>

        {/* Bottom action bar */}
        <div className="shrink-0 border-t border-adw-border bg-adw-headerbar px-6 py-4">
          <div className="mx-auto max-w-[900px]">
            <button className="w-full rounded-lg bg-adw-accent py-2.5 text-[14px] font-bold text-white shadow-[0_1px_0_rgba(255,255,255,0.14)_inset] transition-colors hover:bg-adw-accent-hover active:brightness-95">
              Execute Translation
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
