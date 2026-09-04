import { useState } from "react";

/* ---------- Icons (inline vector) ---------- */

function RibbonGlyph() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="shrink-0">
      <path
        d="M4 6.5 12 2l8 4.5v5.2L12 16 4 11.7V6.5Z"
        fill="#00F2FE"
        fillOpacity="0.16"
        stroke="#00F2FE"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path
        d="M4 11.7 12 16l8-4.3M8.5 8.7 12 10.6l3.5-1.9"
        stroke="#7DD3FC"
        strokeWidth="1.1"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <path d="M12 16v6M9 19.5 12 22l3-2.5" stroke="#00F2FE" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0">
      <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeWidth="1.2" />
      <path
        d="M8 1.8c1.9 1.5 2.9 3.8 2.9 6.2S9.9 12.7 8 14.2C6.1 12.7 5.1 10.4 5.1 8S6.1 3.3 8 1.8ZM2 8h12"
        stroke="currentColor"
        strokeWidth="1.2"
      />
    </svg>
  );
}

function DocWireframe() {
  return (
    <svg width="88" height="104" viewBox="0 0 88 104" fill="none" className="animate-ll-float drop-shadow-[0_20px_40px_rgba(0,242,254,0.18)]">
      {/* back sheet */}
      <path d="M18 14h34l18 18v58H18V14Z" fill="#0B1220" stroke="#00F2FE" strokeOpacity="0.35" strokeWidth="1.4" />
      <path d="M52 14v18h18" fill="#0F1B2E" stroke="#00F2FE" strokeOpacity="0.5" strokeWidth="1.4" strokeLinejoin="round" />
      {/* text lines */}
      <rect x="26" y="42" width="30" height="3" rx="1.5" fill="#00F2FE" fillOpacity="0.55" />
      <rect x="26" y="50" width="22" height="3" rx="1.5" fill="#3B82F6" fillOpacity="0.5" />
      {/* formula placeholder chip */}
      <rect x="26" y="58" width="36" height="12" rx="2" fill="#00F2FE" fillOpacity="0.1" stroke="#00F2FE" strokeOpacity="0.45" strokeWidth="0.9" />
      <text x="29" y="67" fontFamily="JetBrains Mono, monospace" fontSize="6.5" fill="#7DD3FC">
        &lt;formula&gt;
      </text>
      {/* table grid */}
      <rect x="26" y="75" width="36" height="9" rx="1" stroke="#3B82F6" strokeOpacity="0.5" strokeWidth="0.9" />
      <path d="M38 75v9M50 75v9M26 79.5h36" stroke="#3B82F6" strokeOpacity="0.35" strokeWidth="0.7" />
    </svg>
  );
}

/* ---------- Data ---------- */

const TABS = ["Queue", "Batch History", "Preservation Rules", "Settings"] as const;
type Tab = (typeof TABS)[number];

const QUEUE = [
  {
    name: "Quantum_Electrodynamics_Paper.pdf",
    page: 18,
    total: 64,
    status: "TRANSLATING",
    tone: "cyan" as const,
    lang: "EN → VI",
  },
  {
    name: "Global_Semiconductor_Supply.pdf",
    page: 4,
    total: 12,
    status: "LAYOUT MAPPING",
    tone: "amber" as const,
    lang: "EN → VI",
  },
  {
    name: "Differential_Geometry.pdf",
    page: 120,
    total: 120,
    status: "COMPLETED",
    tone: "emerald" as const,
    lang: "EN → VI",
  },
];

/* ---------- Small components ---------- */

function CaptionButtons() {
  return (
    <div className="flex items-center">
      {["min", "max", "close"].map((k) => (
        <button
          key={k}
          className={`grid h-8 w-11 place-items-center text-slate-400 transition-colors hover:text-white ${
            k === "close" ? "hover:bg-red-500/90" : "hover:bg-white/10"
          }`}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            {k === "min" && <path d="M1 5h8" stroke="currentColor" strokeWidth="1" />}
            {k === "max" && <rect x="1" y="1" width="8" height="8" stroke="currentColor" strokeWidth="1" />}
            {k === "close" && <path d="M1 1l8 8M9 1l-8 8" stroke="currentColor" strokeWidth="1" />}
          </svg>
        </button>
      ))}
    </div>
  );
}

function StatusBadge({ status, tone }: { status: string; tone: "cyan" | "amber" | "emerald" }) {
  const styles = {
    cyan: "bg-cyan-400/10 text-cyan-300 border-cyan-400/25",
    amber: "bg-amber-400/10 text-amber-300 border-amber-400/25",
    emerald: "bg-emerald-400/10 text-emerald-300 border-emerald-400/25",
  }[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold tracking-[0.14em] ${styles}`}
    >
      {tone === "cyan" && <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ll-pulse" />}
      {tone === "amber" && <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />}
      {tone === "emerald" && (
        <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
          <path d="M2 6.5 5 9.5 10 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
      {status}
    </span>
  );
}

function SegmentedProgress({ page, total }: { page: number; total: number }) {
  const segments = 24;
  const filled = Math.round((page / total) * segments);
  return (
    <div className="flex items-center gap-[3px]">
      {Array.from({ length: segments }).map((_, i) => (
        <span
          key={i}
          className={`h-3 flex-1 rounded-[1px] transition-colors ${
            i < filled ? "bg-cyan-400/80" : "bg-white/[0.06]"
          } ${i === filled - 1 ? "shadow-[0_0_8px_rgba(0,242,254,0.6)]" : ""}`}
        />
      ))}
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] font-medium text-slate-300">
      {children}
    </span>
  );
}

/* ---------- App ---------- */

export default function App() {
  const [active, setActive] = useState<Tab>("Queue");

  return (
    <div className="h-full w-full overflow-auto bg-[#04060b] p-6">
      {/* Window frame */}
      <div className="relative mx-auto flex min-h-[900px] w-full max-w-[1440px] flex-col overflow-hidden rounded-xl border border-white/10 bg-[#080C14] shadow-[0_40px_120px_-20px_rgba(0,0,0,0.9)]">
        {/* radial ambient glow */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 80% at 30% -10%, rgba(0,242,254,0.04), transparent 60%), radial-gradient(90% 70% at 100% 110%, rgba(59,130,246,0.05), transparent 55%)",
          }}
        />

        {/* Title / caption bar */}
        <div className="relative flex items-center justify-between border-b border-white/[0.06] pl-4">
          <span className="font-mono text-[11px] tracking-[0.18em] text-slate-500">LAYOUTLINGUA — DESKTOP</span>
          <CaptionButtons />
        </div>

        {/* Top navigation */}
        <header className="relative flex items-center gap-6 px-6 py-3.5">
          <div className="flex items-center gap-2.5">
            <img src="/logo.png" alt="LayoutLingua Logo" className="h-6 w-6 rounded-md object-contain shadow-[0_0_12px_rgba(0,242,254,0.35)]" />
            <span className="font-display text-[17px] font-semibold tracking-tight text-white">
              Layout<span className="text-cyan-400">Lingua</span>
            </span>
          </div>

          <nav className="flex items-center gap-1.5">
            {TABS.map((tab) => {
              const isActive = tab === active;
              return (
                <button
                  key={tab}
                  onClick={() => setActive(tab)}
                  className={`relative overflow-hidden rounded-lg px-3.5 py-2 text-[13px] font-medium transition-colors ${
                    isActive ? "bg-[#1E293B] text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {isActive && <span className="absolute inset-x-0 top-0 h-px bg-cyan-400 shadow-[0_0_8px_rgba(0,242,254,0.8)]" />}
                  {tab}
                  {tab === "Queue" && (
                    <span className="ml-1.5 rounded-full bg-cyan-400/15 px-1.5 py-0.5 font-mono text-[10px] text-cyan-300">
                      3
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-2 font-mono text-[11px] text-slate-500">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            SYNCED
          </div>
        </header>

        {/* Main bento grid */}
        <main className="relative grid flex-1 grid-cols-1 gap-4 px-6 pb-28 pt-2 lg:grid-cols-12">
          {/* Left stage — Ingestion */}
          <section className="lg:col-span-7">
            <div className="h-full rounded-2xl border border-white/10 bg-white/[0.02] p-2">
              <div className="flex min-h-[460px] flex-col justify-between rounded-[calc(1rem-2px)] bg-[#0F172A] p-8">
                {/* top metadata */}
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/[0.06] px-3 py-1.5 text-[10px] font-semibold tracking-[0.2em] text-cyan-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ll-pulse" />
                    ENGINE STATUS: LOCAL YOLOV8 ONLINE
                  </span>
                  <span className="font-mono text-[10px] tracking-[0.15em] text-slate-500">v3.2.1</span>
                </div>

                {/* center drop target */}
                <div className="flex flex-col items-center py-6 text-center">
                  <div className="relative grid place-items-center rounded-full border-2 border-dashed border-cyan-400/30 p-6">
                    <div className="grid h-40 w-40 place-items-center rounded-full border border-white/10 bg-gradient-to-b from-[#0B1220] to-[#0F172A] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                      <DocWireframe />
                    </div>
                  </div>
                  <h1 className="font-display mt-7 text-[28px] font-semibold tracking-tight text-white">
                    Drop Technical PDFs Here
                  </h1>
                  <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-slate-400">
                    Preserves formulas, tables, vector charts, and Vietnamese tone marks.
                  </p>
                </div>

                {/* bottom pill bar */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <button className="rounded-full border border-white/15 bg-white/[0.04] px-5 py-2.5 text-[13px] font-semibold text-white transition-colors hover:border-cyan-400/40 hover:bg-white/[0.07]">
                    Browse files
                  </button>
                  <div className="flex flex-wrap items-center gap-2">
                    <Tag>Max 500 Pages</Tag>
                    <Tag>Latin + Vietnamese</Tag>
                    <Tag>OCR Fallback Ready</Tag>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Right stage — Telemetry deck */}
          <section className="lg:col-span-5">
            <div className="flex h-full flex-col gap-3">
              <div className="flex items-center justify-between px-1">
                <h2 className="font-display text-[15px] font-semibold text-white">Live Translation Telemetry</h2>
                <span className="font-mono text-[10px] tracking-[0.15em] text-slate-500">3 ACTIVE</span>
              </div>

              {QUEUE.map((item) => (
                <article
                  key={item.name}
                  className="group rounded-2xl border border-white/[0.08] bg-[#0F172A] p-4 transition-colors hover:border-white/15"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-mono truncate text-[12.5px] font-medium text-slate-200">{item.name}</p>
                      <p className="font-mono mt-1 text-[11px] text-slate-500">
                        Page {item.page}/{item.total}
                      </p>
                    </div>
                    <StatusBadge status={item.status} tone={item.tone} />
                  </div>

                  <div className="mt-4">
                    <SegmentedProgress page={item.page} total={item.total} />
                  </div>

                  <div className="mt-3 flex items-center justify-between">
                    <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 font-mono text-[10px] tracking-wide text-slate-300">
                      {item.lang}
                    </span>
                    {item.tone === "emerald" ? (
                      <button className="inline-flex items-center gap-1.5 rounded-md bg-emerald-400/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-400/20">
                        Open Output
                        <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                          <path d="M3 9 9 3M4.5 3H9v4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </button>
                    ) : (
                      <span className="font-mono text-[10px] text-slate-500">
                        {Math.round((item.page / item.total) * 100)}%
                      </span>
                    )}
                  </div>
                </article>
              ))}

              <div className="mt-auto rounded-2xl border border-dashed border-white/10 bg-white/[0.01] p-4 text-center">
                <p className="font-mono text-[11px] text-slate-500">Idle throughput 42 pg/min · GPU 61%</p>
              </div>
            </div>
          </section>
        </main>

        {/* Bottom floating command island */}
        <div className="pointer-events-none absolute inset-x-0 bottom-6 flex justify-center px-6">
          <div className="pointer-events-auto flex items-center gap-4 rounded-full border border-white/15 bg-[#0F172A]/90 px-6 py-3.5 backdrop-blur-xl shadow-[0_20px_50px_-10px_rgba(0,0,0,0.8)]">
            <button className="flex items-center gap-2.5 rounded-full px-2 py-1 text-[13px] font-medium text-slate-200 transition-colors hover:text-white">
              <span className="text-cyan-400">
                <GlobeIcon />
              </span>
              <span>
                Target: <span className="font-semibold text-white">Tiếng Việt</span>{" "}
                <span className="font-mono text-[11px] text-slate-400">(vi)</span>
              </span>
              <span className="rounded-full bg-white/[0.06] px-2 py-0.5 font-mono text-[10px] text-slate-400">
                36 languages
              </span>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-slate-500">
                <path d="M3 4.5 6 7.5 9 4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            <div className="h-6 w-px bg-white/10" />

            <button className="group flex items-center gap-2.5 rounded-full bg-gradient-to-r from-[#00F2FE] to-[#3B82F6] py-2.5 pl-6 pr-2.5 font-semibold text-black shadow-[0_8px_24px_-4px_rgba(0,242,254,0.5)] transition-transform hover:scale-[1.02]">
              <span className="text-[14px]">Translate All</span>
              <span className="grid h-7 w-7 place-items-center rounded-full bg-black/85 text-cyan-300 transition-transform group-hover:translate-x-0.5">
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <path d="M2.5 7h8M7 3l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
