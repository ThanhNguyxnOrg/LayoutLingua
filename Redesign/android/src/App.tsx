import { useState } from "react";

/* ---------- Material Symbols (inline, rounded style) ---------- */

type IconProps = { className?: string; size?: number };

function Icon({ path, className = "", size = 24 }: IconProps & { path: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

const P = {
  menu: "M3 6h18v2H3V6zm0 5h18v2H3v-2zm0 5h18v2H3v-2z",
  stream:
    "M4 6h16v2H4V6zm0 5h10v2H4v-2zm0 5h16v2H4v-2zM16.5 11l3.5 2-3.5 2v-4z",
  info: "M11 7h2v2h-2V7zm0 4h2v6h-2v-6zm1-9a10 10 0 100 20 10 10 0 000-20zm0 18a8 8 0 110-16 8 8 0 010 16z",
  globe:
    "M12 2a10 10 0 100 20 10 10 0 000-20zm6.9 6h-2.5a15.6 15.6 0 00-1.3-3.3A8 8 0 0118.9 8zM12 4c.8 1 1.5 2.4 1.9 4h-3.8C10.5 6.4 11.2 5 12 4zM4.3 14a7.9 7.9 0 010-4h2.9a16.9 16.9 0 000 4H4.3zm.8 2h2.5c.3 1.2.8 2.3 1.3 3.3A8 8 0 015.1 16zm2.5-8H5.1a8 8 0 013.8-3.3A15.6 15.6 0 007.6 8zM12 20c-.8-1-1.5-2.4-1.9-4h3.8c-.4 1.6-1.1 3-1.9 4zm2.3-6H9.7a14.7 14.7 0 010-4h4.6a14.7 14.7 0 010 4zm.4 5.3c.5-1 .9-2.1 1.3-3.3h2.5a8 8 0 01-3.8 3.3zM16.8 14a16.9 16.9 0 000-4h2.9a7.9 7.9 0 010 4h-2.9z",
  chevron: "M8.6 16.6L13.2 12 8.6 7.4 10 6l6 6-6 6-1.4-1.4z",
  chevronDown: "M7.4 8.6L12 13.2l4.6-4.6L18 10l-6 6-6-6 1.4-1.4z",
  cloud:
    "M6 19a5 5 0 01-.6-9.96A6.5 6.5 0 0118.9 11 4.5 4.5 0 0118 19.9V20H6z",
  upload: "M11 15V8.8l-2.6 2.6L7 10l5-5 5 5-1.4 1.4L13 8.8V15h-2z",
  pdf: "M6 2h9l5 5v13a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2zm8 1.5V8h4.5L14 3.5z",
  check: "M9 16.2l-3.5-3.5L4 14.2 9 19 20 8l-1.4-1.5L9 16.2z",
  formula: "M4 4h16v2H4V4zm2 4h8v2H6V8zm0 4h12v2H6v-2zm0 4h8v2H6v-2z",
  grid: "M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 0h8v8h-8v-8z",
  translate:
    "M12.9 15l-2.6-2.6.03-.03A18 18 0 0013.1 8H16V6h-7V4H7v2H0v2h11.5a16 16 0 01-2.5 4.4A16 16 0 017.2 9H5.2a18 18 0 002.6 4.6l-3.3 3.25L6 18.3l3.2-3.2 2 2 .7-2.1zM17.5 10h-2L11 22h2l1.12-3h4.75L20 22h2l-4.5-12zm-2.62 7l1.62-4.33L18.12 17h-3.24z",
  library:
    "M4 6h2v14H4V6zm4 0h2v14H8V6zm5.5-.3l1.9-.5 3.6 13.5-1.9.5L13.5 5.7zM12 6h-1V4h1v2z",
  history:
    "M13 3a9 9 0 00-9 9H1l4 4 4-4H6a7 7 0 117 7 6.9 6.9 0 01-4.9-2l-1.4 1.4A8.9 8.9 0 1013 3zm-1 5v5l4.3 2.5.7-1.2-3.5-2.1V8h-1.5z",
  settings:
    "M19.4 13a7.8 7.8 0 000-2l2.1-1.6-2-3.5-2.5 1a7.6 7.6 0 00-1.7-1l-.4-2.6h-4l-.4 2.6a7.6 7.6 0 00-1.7 1l-2.5-1-2 3.5L4.6 11a7.8 7.8 0 000 2L2.5 14.6l2 3.5 2.5-1c.5.4 1.1.7 1.7 1l.4 2.6h4l.4-2.6c.6-.3 1.2-.6 1.7-1l2.5 1 2-3.5L19.4 13zM12 15.5a3.5 3.5 0 110-7 3.5 3.5 0 010 7z",
  add: "M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5z",
};

/* ---------- Chip ---------- */

function Chip({ label, icon }: { label: string; icon?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-[#43474E] bg-[#1A1C23]/60 px-3 py-1.5 text-[13px] font-medium text-[#C4C7CF]">
      {icon && <Icon path={icon} size={16} className="text-[#80D4FF]" />}
      {label}
    </span>
  );
}

/* ---------- Queue Card ---------- */

function QueueCard({
  name,
  size,
  status,
  progress,
  subtitle,
  page,
}: {
  name: string;
  size?: string;
  status: "active" | "ready";
  progress?: number;
  subtitle?: string;
  page?: string;
}) {
  return (
    <div className="rounded-[20px] bg-[#1D2027] p-4">
      <div className="flex items-start gap-3.5">
        <div className="relative flex size-11 shrink-0 items-center justify-center rounded-xl bg-[#003547] text-[#80D4FF]">
          <Icon path={P.pdf} size={22} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-[15px] font-medium text-[#E3E2E6]">
              {name}
            </p>
            {size && (
              <span className="shrink-0 text-[12px] text-[#8E9199]">{size}</span>
            )}
          </div>

          {status === "active" && (
            <>
              <p className="mt-0.5 truncate text-[13px] text-[#A9ACB4]">
                {subtitle}
              </p>
              <div className="mt-3 flex items-center gap-2.5">
                <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-[#3A3E46]">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-[#80D4FF] to-[#4A9FE0]"
                    style={{ width: `${progress}%` }}
                  />
                  <div
                    className="absolute inset-y-0 w-1/4 bg-white/30 blur-[2px]"
                    style={{ animation: "ll-sweep 1.8s ease-in-out infinite" }}
                  />
                </div>
                <span className="shrink-0 text-[12px] font-semibold tabular-nums text-[#80D4FF]">
                  {page}
                </span>
              </div>
            </>
          )}

          {status === "ready" && (
            <div className="mt-2 flex items-center justify-between">
              <span className="inline-flex items-center gap-1 rounded-full bg-[#0F3D2E] px-2.5 py-1 text-[12px] font-semibold text-[#7FE0A8]">
                <Icon path={P.check} size={14} /> Ready
              </span>
              <button className="rounded-full px-3 py-1 text-[13px] font-semibold text-[#80D4FF] transition-colors hover:bg-[#80D4FF]/10">
                Download
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- App ---------- */

const NAV = [
  { id: "translate", label: "Translate", icon: P.translate },
  { id: "library", label: "Library", icon: P.library },
  { id: "history", label: "History", icon: P.history },
  { id: "settings", label: "Settings", icon: P.settings },
];

export default function App() {
  const [tab, setTab] = useState("translate");

  return (
    <div className="flex min-h-full w-full items-center justify-center bg-[#050608] p-6">
      {/* Phone frame */}
      <div
        className="relative flex flex-col overflow-hidden rounded-[44px] bg-[#111318] shadow-[0_40px_120px_-20px_rgba(0,0,0,0.9)] ring-1 ring-white/5"
        style={{ width: 390, height: 844 }}
      >
        {/* Status bar */}
        <div className="flex items-center justify-between px-6 pt-3 pb-1 text-[13px] font-semibold text-[#E3E2E6]">
          <span>9:41</span>
          <span className="flex items-center gap-1.5">
            <Icon path="M2 22h20V2z" size={15} className="text-[#C4C7CF]" />
            <span className="text-[11px]">5G</span>
            <span className="ml-1 inline-block h-3 w-6 rounded-[3px] border border-[#C4C7CF] p-[1.5px]">
              <span className="block h-full w-4/5 rounded-[1px] bg-[#C4C7CF]" />
            </span>
          </span>
        </div>

        {/* Top App Bar (center-aligned) */}
        <header className="flex items-center justify-between px-3 pt-1.5 pb-2">
          <button className="grid size-11 place-items-center rounded-full text-[#C4C7CF] transition-colors hover:bg-white/5">
            <Icon path={P.menu} />
          </button>
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="LayoutLingua Logo" className="h-6 w-6 rounded-md object-contain shadow-[0_0_10px_rgba(128,212,255,0.4)]" />
            <span
              className="font-display text-[19px] font-semibold tracking-tight text-[#E3E2E6]"
              style={{ fontStretch: "112%" }}
            >
              Layout
            </span>
            <span
              className="font-display text-[19px] font-semibold italic tracking-tight text-[#80D4FF]"
              style={{ fontStretch: "112%" }}
            >
              Lingua
            </span>
          </div>
          <div className="flex">
            <button className="grid size-11 place-items-center rounded-full text-[#C4C7CF] transition-colors hover:bg-white/5">
              <Icon path={P.stream} size={22} />
            </button>
            <button className="grid size-11 place-items-center rounded-full text-[#C4C7CF] transition-colors hover:bg-white/5">
              <Icon path={P.info} size={22} />
            </button>
          </div>
        </header>

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto px-4 pb-40">
          {/* Ingestion Hero — double bezel */}
          <section className="rounded-[28px] bg-[#1A1C23] p-2 ring-1 ring-white/10">
            <div className="rounded-[22px] bg-[#21242D] p-6 text-center">
              {/* Animated cloud + upload graphic */}
              <div className="relative mx-auto mb-5 grid size-28 place-items-center">
                <div
                  className="absolute size-24 rounded-full bg-[#80D4FF]/25 blur-2xl"
                  style={{ animation: "ll-glow 3.5s ease-in-out infinite" }}
                />
                <div
                  className="relative"
                  style={{ animation: "ll-float 4s ease-in-out infinite" }}
                >
                  <Icon path={P.cloud} size={92} className="text-[#2E5C6E]" />
                  <span className="absolute inset-0 grid place-items-center">
                    <Icon
                      path={P.upload}
                      size={44}
                      className="text-[#80D4FF] drop-shadow-[0_0_10px_rgba(128,212,255,0.7)]"
                    />
                  </span>
                </div>
                <span
                  className="absolute bottom-1 grid place-items-center"
                  style={{ animation: "ll-arrow 2s ease-in-out infinite" }}
                >
                  <Icon path={P.upload} size={20} className="text-[#80D4FF]/60" />
                </span>
              </div>

              <h1 className="font-display text-[22px] font-semibold leading-tight text-[#E3E2E6]">
                Translate Documents with Preserved Layout
              </h1>
              <p className="mx-auto mt-2 max-w-[16rem] text-[13px] leading-relaxed text-[#A9ACB4]">
                Drop a PDF and keep every column, table, and equation exactly
                where it belongs.
              </p>

              <div className="mt-5 flex flex-wrap justify-center gap-2">
                <Chip label="Auto-Language" icon={P.globe} />
                <Chip label="Formulas Preserved" icon={P.formula} />
                <Chip label="Table Grid Locked" icon={P.grid} />
              </div>
            </div>
          </section>

          {/* Language Selector */}
          <section className="mt-4 rounded-[20px] bg-[#1D2027] p-4">
            <div className="flex items-center gap-3.5">
              <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-[#003547] text-[#80D4FF]">
                <Icon path={P.globe} size={22} />
              </div>
              <div className="flex-1">
                <p className="text-[12px] uppercase tracking-wide text-[#8E9199]">
                  Target Language
                </p>
                <p className="text-[15px] font-medium text-[#E3E2E6]">
                  Translate output to
                </p>
              </div>
              <button className="inline-flex items-center gap-1.5 rounded-full border border-[#43474E] bg-[#111318] py-2 pl-3.5 pr-2 text-[14px] font-medium text-[#E3E2E6] transition-colors hover:border-[#80D4FF]/50">
                Tiếng Việt (vi)
                <Icon path={P.chevronDown} size={18} className="text-[#80D4FF]" />
              </button>
            </div>
          </section>

          {/* Active Queue */}
          <div className="mt-6 mb-3 flex items-center justify-between px-1">
            <h2 className="text-[14px] font-semibold uppercase tracking-wide text-[#8E9199]">
              Active Queue
            </h2>
            <span className="text-[12px] font-medium text-[#80D4FF]">
              2 documents
            </span>
          </div>

          <div className="space-y-3">
            <QueueCard
              name="Lecture_Notes_Calculus.pdf"
              size="4.1 MB"
              status="active"
              progress={31}
              page="5/16"
              subtitle="Rendering translated font glyphs (Page 5/16)"
            />
            <QueueCard
              name="Thesis_Abstract_Draft.pdf"
              size="0.8 MB"
              status="ready"
            />
          </div>
        </main>

        {/* Extended FAB */}
        <div className="pointer-events-none absolute inset-x-0 bottom-[76px] z-20 flex justify-center">
          <button className="pointer-events-auto inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-[#80D4FF] to-[#59C3F5] py-4 pl-6 pr-3 text-[15px] font-semibold text-[#00344A] shadow-[0_12px_30px_-6px_rgba(128,212,255,0.55)] transition-transform active:scale-95">
            Translate All
            <span className="grid size-8 place-items-center rounded-full bg-[#00344A] text-[#80D4FF]">
              <Icon path={P.translate} size={18} />
            </span>
          </button>
        </div>

        {/* Bottom Navigation */}
        <nav className="relative z-10 flex items-center justify-around border-t border-white/5 bg-[#1A1C23]/95 px-2 pt-2.5 pb-6 backdrop-blur">
          {NAV.map((item) => {
            const active = tab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setTab(item.id)}
                className="flex flex-1 flex-col items-center gap-1"
              >
                <span
                  className={`grid h-8 w-16 place-items-center rounded-full transition-colors ${
                    active ? "bg-[#004D66] text-[#80D4FF]" : "text-[#8E9199]"
                  }`}
                >
                  <Icon path={item.icon} size={22} />
                </span>
                <span
                  className={`text-[12px] transition-colors ${
                    active
                      ? "font-semibold text-[#E3E2E6]"
                      : "font-medium text-[#8E9199]"
                  }`}
                >
                  {item.label}
                </span>
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
