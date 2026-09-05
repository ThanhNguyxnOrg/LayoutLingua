import { useState } from "react";

/* ------------------------------------------------------------------ */
/* Icons — minimalist SF Symbols approximations                        */
/* ------------------------------------------------------------------ */

function IconDocViewfinder({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M7 3H5a2 2 0 0 0-2 2v2M17 3h2a2 2 0 0 1 2 2v2M7 21H5a2 2 0 0 1-2-2v-2M17 21h2a2 2 0 0 0 2-2v-2"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <rect x="8" y="8" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10.5 11.5h3M10.5 13.2h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function IconCheckCircleFill({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="9" fill="currentColor" />
      <path d="M8.2 12.3l2.5 2.5 5-5.2" stroke="#0A0E17" strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconGearshape({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="2.6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 3.5v2M12 18.5v2M4.9 7l1.7 1M17.4 16l1.7 1M4.9 17l1.7-1M17.4 8l1.7-1"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="12" cy="12" r="8.2" stroke="currentColor" strokeWidth="1.5" strokeDasharray="1 3.4" />
    </svg>
  );
}

function IconSearch({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="10.5" cy="10.5" r="6" stroke="currentColor" strokeWidth="1.6" />
      <path d="M15.2 15.2L20 20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconArrowInCircle({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="10.5" stroke="currentColor" strokeWidth="1.4" opacity="0.55" />
      <circle cx="12" cy="12" r="7" fill="currentColor" fillOpacity="0.14" />
      <path d="M10 8.5l3.5 3.5-3.5 3.5" stroke="currentColor" strokeWidth="1.7"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Blueprint — fine vector page layout diagram                         */
/* ------------------------------------------------------------------ */

function LayoutBlueprint() {
  const stroke = "rgba(120,160,230,0.55)";
  const faint = "rgba(120,160,230,0.22)";
  return (
    <svg viewBox="0 0 240 300" className="h-[188px] w-auto" fill="none">
      {/* page */}
      <rect x="20" y="14" width="200" height="272" rx="6" stroke={stroke} strokeWidth="1" />
      {/* margin guides */}
      <rect x="34" y="30" width="172" height="240" stroke={faint} strokeWidth="0.75" strokeDasharray="2 3" />
      {/* two-column gutter */}
      <line x1="120" y1="30" x2="120" y2="132" stroke={faint} strokeWidth="0.75" strokeDasharray="2 3" />
      {/* heading block */}
      <rect x="34" y="30" width="120" height="9" rx="2" fill={faint} />
      <line x1="34" y1="48" x2="112" y2="48" stroke={stroke} strokeWidth="1" />
      {/* left column text lines */}
      {[58, 66, 74, 82, 90, 98, 106, 114].map((y) => (
        <line key={"l" + y} x1="34" y1={y} x2="112" y2={y} stroke={faint} strokeWidth="1" />
      ))}
      {/* right column text lines */}
      {[58, 66, 74, 82, 90, 98, 106, 114].map((y) => (
        <line key={"r" + y} x1="128" y1={y} x2="206" y2={y} stroke={faint} strokeWidth="1" />
      ))}
      {/* equation block */}
      <rect x="34" y="140" width="172" height="30" rx="3" stroke={stroke} strokeWidth="1" />
      <path d="M44 155h12M50 149v12M62 155l6-6M62 149l6 6M78 155h10l3 5M100 152h14M100 158h20"
        stroke={stroke} strokeWidth="1" strokeLinecap="round" />
      <text x="170" y="159" fill={faint} fontSize="8" fontFamily="monospace">(1.2)</text>
      {/* table */}
      <rect x="34" y="182" width="172" height="58" rx="3" stroke={stroke} strokeWidth="1" />
      <line x1="34" y1="196" x2="206" y2="196" stroke={stroke} strokeWidth="1" />
      <line x1="90" y1="182" x2="90" y2="240" stroke={faint} strokeWidth="0.75" />
      <line x1="148" y1="182" x2="148" y2="240" stroke={faint} strokeWidth="0.75" />
      <line x1="34" y1="210" x2="206" y2="210" stroke={faint} strokeWidth="0.6" />
      <line x1="34" y1="224" x2="206" y2="224" stroke={faint} strokeWidth="0.6" />
      {/* baseline caption */}
      <line x1="34" y1="252" x2="150" y2="252" stroke={faint} strokeWidth="1" />
      <line x1="34" y1="260" x2="120" y2="260" stroke={faint} strokeWidth="1" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Data                                                                */
/* ------------------------------------------------------------------ */

const TABS = ["Ingest", "Queue (3)", "Inspector", "Terminal Logs"] as const;
type Tab = (typeof TABS)[number];

const queueItems = [
  {
    name: "phan_van_luan_thesis_ch4.pdf",
    size: "4.8 MB",
    status: "translating",
    detail: "Reflowing Vietnamese diacritics · pass 2 of 3",
    progress: 0.62,
  },
  {
    name: "annals_of_mathematics_v198.pdf",
    size: "12.1 MB",
    status: "queued",
    detail: "Awaiting layout engine · equation-heavy",
    progress: 0.0,
  },
  {
    name: "nguyen_du_kieu_annotated.pdf",
    size: "2.3 MB",
    status: "done",
    detail: "Completed · 1.24 line-height verified",
    progress: 1.0,
  },
] as const;

/* ------------------------------------------------------------------ */
/* App                                                                 */
/* ------------------------------------------------------------------ */

export default function App() {
  const [tab, setTab] = useState<Tab>("Ingest");
  const [handoff, setHandoff] = useState(true);
  const [activeRepo, setActiveRepo] = useState("Active Queue");
  const [activePreset, setActivePreset] = useState("Vietnamese - Scholarly");
  const [dragging, setDragging] = useState(false);

  return (
    <div
      className="size-full flex items-center justify-center overflow-auto p-6"
      style={{
        background:
          "radial-gradient(120% 90% at 15% 0%, #131d33 0%, #0a0e17 46%, #05070d 100%)",
      }}
    >
      {/* Window */}
      <div
        className="relative flex flex-col overflow-hidden rounded-[13px] ring-1 ring-white/10"
        style={{
          width: 1400,
          height: 880,
          backgroundColor: "#0A0E17",
          boxShadow:
            "0 40px 120px -20px rgba(0,0,0,0.75), 0 0 0 0.5px rgba(255,255,255,0.06)",
        }}
      >
        {/* ---------------- Unified Toolbar ---------------- */}
        <header
          className="relative z-20 flex h-[52px] shrink-0 items-center gap-4 border-b border-white/[0.06] px-4"
          style={{
            background:
              "linear-gradient(180deg, rgba(30,40,62,0.72) 0%, rgba(16,22,38,0.72) 100%)",
            backdropFilter: "blur(24px) saturate(180%)",
          }}
        >
          {/* Traffic lights */}
          <div className="group flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-[#ff5f57] ring-1 ring-black/20" />
            <span className="h-3 w-3 rounded-full bg-[#febc2e] ring-1 ring-black/20" />
            <span className="h-3 w-3 rounded-full bg-[#28c840] ring-1 ring-black/20" />
          </div>

          {/* Title + version */}
          <div className="flex items-center gap-2 pl-1">
            <img src="/logo.png" alt="LayoutLingua Logo" className="h-5 w-5 rounded-[4px] object-contain shadow-[0_0_10px_rgba(0,242,254,0.4)]" />
            <span className="font-display text-[14px] font-semibold text-white/92">
              LayoutLingua
            </span>
            <span className="font-mono-ll rounded-[5px] bg-white/[0.07] px-1.5 py-0.5 text-[10px] font-medium tracking-tight text-white/55 ring-1 ring-inset ring-white/10">
              v1.0.0
            </span>
          </div>

          {/* Center segmented switcher */}
          <div className="absolute left-1/2 -translate-x-1/2">
            <div className="flex items-center gap-0.5 rounded-[9px] bg-black/30 p-0.5 ring-1 ring-inset ring-white/[0.06]">
              {TABS.map((t) => {
                const active = tab === t;
                return (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`relative rounded-[7px] px-3 py-1 text-[12px] font-medium transition-colors ${
                      active
                        ? "bg-white/[0.10] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.10)]"
                        : "text-white/50 hover:text-white/80"
                    }`}
                  >
                    {t === "Queue (3)" ? (
                      <span className="flex items-center gap-1.5">
                        Queue
                        <span className="rounded-full bg-[#3b82f6] px-1.5 text-[10px] font-semibold leading-[15px] text-white">
                          3
                        </span>
                      </span>
                    ) : (
                      t
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right controls */}
          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={() => setHandoff((v) => !v)}
              className="flex items-center gap-2 rounded-[8px] px-1 py-1"
            >
              <span className="text-[12px] font-medium text-white/60">Handoff Mode</span>
              <span
                className={`relative h-[18px] w-[30px] rounded-full transition-colors duration-200 ${
                  handoff ? "bg-[#28c840]" : "bg-white/15"
                }`}
              >
                <span
                  className={`absolute top-[2px] h-[14px] w-[14px] rounded-full bg-white shadow transition-transform duration-200 ${
                    handoff ? "translate-x-[13px]" : "translate-x-[2px]"
                  }`}
                />
              </span>
            </button>

            <div className="flex h-[28px] w-[190px] items-center gap-2 rounded-[8px] bg-black/30 px-2.5 ring-1 ring-inset ring-white/[0.08]">
              <IconSearch className="h-[14px] w-[14px] text-white/40" />
              <input
                placeholder="Search documents"
                className="w-full bg-transparent text-[12px] text-white/85 placeholder:text-white/35 focus:outline-none"
              />
            </div>
          </div>
        </header>

        {/* ---------------- Body ---------------- */}
        <div className="flex min-h-0 flex-1">
          {/* ---------- Sidebar ---------- */}
          <aside
            className="flex w-[260px] shrink-0 flex-col border-r border-white/[0.06]"
            style={{
              background:
                "linear-gradient(180deg, rgba(22,29,48,0.55) 0%, rgba(12,16,28,0.55) 100%)",
              backdropFilter: "blur(30px) saturate(160%)",
            }}
          >
            <div className="flex-1 overflow-y-auto px-3 py-4">
              <SidebarGroup label="Repositories">
                {[
                  { label: "Active Queue", badge: "3" },
                  { label: "Completed Translations", badge: "128" },
                  { label: "Source Archives", badge: null },
                ].map((it) => (
                  <SidebarItem
                    key={it.label}
                    label={it.label}
                    badge={it.badge}
                    active={activeRepo === it.label}
                    onClick={() => setActiveRepo(it.label)}
                    dot="#3b82f6"
                  />
                ))}
              </SidebarGroup>

              <SidebarGroup label="Language Presets">
                {[
                  { label: "Vietnamese - Scholarly", tone: "#f0abfc" },
                  { label: "English - Global", tone: "#7dd3fc" },
                  { label: "Chinese CJK - Beta", tone: "#fcd34d", beta: true },
                ].map((it) => (
                  <SidebarItem
                    key={it.label}
                    label={it.label}
                    active={activePreset === it.label}
                    onClick={() => setActivePreset(it.label)}
                    dot={it.tone}
                    beta={it.beta}
                  />
                ))}
              </SidebarGroup>
            </div>

            {/* Telemetry */}
            <div className="border-t border-white/[0.06] px-4 py-3">
              <Telemetry label="Memory Usage" value="142 MB" fill={0.34} />
              <div className="mt-2.5 flex items-center justify-between">
                <span className="text-[11px] text-white/40">Layout Engine</span>
                <span className="font-mono-ll text-[11px] text-white/55">Core v1.9.11</span>
              </div>
            </div>
          </aside>

          {/* ---------- Main Workspace ---------- */}
          <main className="relative flex min-w-0 flex-1 flex-col">
            <div className="flex-1 overflow-y-auto px-10 py-8">
              {/* Eyebrow */}
              <div className="mb-6 flex items-center gap-2.5">
                <span className="h-1 w-1 rounded-full bg-[#28c840]" />
                <p className="font-mono-ll text-[10.5px] font-medium uppercase tracking-[0.16em] text-white/45">
                  Target Specification: Latin &amp; Vietnamese · 1.2 Line-Height Floor
                </p>
              </div>

              {/* Double-bezel drop card */}
              <div className="rounded-2xl p-1.5 ring-1 ring-white/10">
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(false);
                  }}
                  className={`relative overflow-hidden rounded-xl bg-[#111A2C] p-8 transition-colors ${
                    dragging ? "ring-2 ring-[#3b82f6]/60" : ""
                  }`}
                >
                  {/* dotted intake border */}
                  <div className="rounded-lg border border-dashed border-white/12 px-6 py-8">
                    <div className="flex flex-col items-center text-center">
                      <LayoutBlueprint />
                      <p className="mt-6 font-display text-[17px] font-medium text-white/90">
                        Drop PDF documents or choose files from Finder
                      </p>
                      <p className="mt-1.5 max-w-md text-[12.5px] leading-relaxed text-white/45">
                        LayoutLingua preserves column grids, tables, and equation
                        typesetting while translating body text in place.
                      </p>
                      <div className="mt-5 flex items-center gap-2.5">
                        <button className="rounded-[8px] bg-white/[0.09] px-3.5 py-1.5 text-[12.5px] font-medium text-white/85 ring-1 ring-inset ring-white/10 transition hover:bg-white/[0.14]">
                          Choose Files…
                        </button>
                        <span className="text-[11.5px] text-white/35">
                          Accepts .pdf up to 200 MB
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Queue Drawer */}
              <div className="mb-6 mt-8 flex items-center justify-between">
                <h2 className="font-display text-[13px] font-semibold uppercase tracking-[0.08em] text-white/55">
                  Processing Queue
                </h2>
                <span className="font-mono-ll text-[11px] text-white/35">
                  3 items · est. 2m 40s
                </span>
              </div>

              <div className="space-y-2.5 pb-28">
                {queueItems.map((item, i) => (
                  <QueueRow key={item.name} item={item} index={i} />
                ))}
              </div>
            </div>

            {/* ---- Floating dock action ---- */}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center pb-6">
              <button className="pointer-events-auto group flex items-center gap-3 rounded-full py-2 pl-5 pr-2 text-[14px] font-semibold text-white shadow-[0_18px_40px_-12px_rgba(59,130,246,0.7)] ring-1 ring-inset ring-white/20 transition-transform hover:-translate-y-0.5"
                style={{
                  background:
                    "linear-gradient(180deg, #4f8dfb 0%, #2f6ff0 100%)",
                }}
              >
                <span className="font-display tracking-tight">Translate Queue</span>
                <span className="rounded-full bg-white/15 px-2 py-0.5 text-[12px] font-medium text-white/90">
                  3 Files
                </span>
                <IconArrowInCircle className="h-7 w-7 text-white transition-transform group-hover:translate-x-0.5" />
              </button>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sidebar pieces                                                      */
/* ------------------------------------------------------------------ */

function SidebarGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5">
      <p className="px-2 pb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-white/30">
        {label}
      </p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function SidebarItem({
  label,
  badge = null,
  active = false,
  onClick,
  dot,
  beta = false,
}: {
  label: string;
  badge?: string | null;
  active?: boolean;
  onClick?: () => void;
  dot: string;
  beta?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-2.5 rounded-[7px] px-2 py-[7px] text-left transition-colors ${
        active
          ? "bg-white/[0.09] ring-1 ring-inset ring-white/[0.06]"
          : "hover:bg-white/[0.04]"
      }`}
    >
      <span
        className="h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: dot, boxShadow: `0 0 8px ${dot}55` }}
      />
      <span
        className={`flex-1 truncate text-[12.5px] ${
          active ? "text-white/92" : "text-white/60"
        }`}
      >
        {label}
      </span>
      {beta && (
        <span className="rounded bg-[#fcd34d]/15 px-1 text-[9px] font-semibold uppercase tracking-wide text-[#fcd34d]">
          β
        </span>
      )}
      {badge && (
        <span className="font-mono-ll text-[11px] text-white/35">{badge}</span>
      )}
    </button>
  );
}

function Telemetry({
  label,
  value,
  fill,
}: {
  label: string;
  value: string;
  fill: number;
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-white/40">{label}</span>
        <span className="font-mono-ll text-[11px] text-white/60">{value}</span>
      </div>
      <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-[#3b82f6] to-[#60a5fa]"
          style={{ width: `${fill * 100}%` }}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Queue row                                                           */
/* ------------------------------------------------------------------ */

function QueueRow({
  item,
  index,
}: {
  item: (typeof queueItems)[number];
  index: number;
}) {
  const isDone = item.status === "done";
  const isTranslating = item.status === "translating";

  return (
    <div
      className="flex items-center gap-4 rounded-xl bg-white/[0.025] px-4 py-3 ring-1 ring-inset ring-white/[0.06] transition-colors hover:bg-white/[0.045]"
      style={{ marginLeft: index * 10 }}
    >
      {/* Icon */}
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] ring-1 ring-inset ${
          isDone
            ? "bg-[#28c840]/10 ring-[#28c840]/20"
            : isTranslating
            ? "bg-[#3b82f6]/10 ring-[#3b82f6]/20"
            : "bg-white/[0.05] ring-white/10"
        }`}
      >
        {isDone ? (
          <IconCheckCircleFill className="h-[18px] w-[18px] text-[#28c840]" />
        ) : isTranslating ? (
          <IconGearshape className="h-[18px] w-[18px] animate-[spin_6s_linear_infinite] text-[#7dacff]" />
        ) : (
          <IconDocViewfinder className="h-[18px] w-[18px] text-white/55" />
        )}
      </div>

      {/* Text + progress */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="font-mono-ll truncate text-[12.5px] text-white/85">
            {item.name}
          </p>
          <span className="shrink-0 rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-white/45 ring-1 ring-inset ring-white/[0.06]">
            {item.size}
          </span>
        </div>
        <p className="mt-0.5 truncate text-[11.5px] text-white/40">{item.detail}</p>

        {!isDone && (
          <div className="mt-2 h-[3px] w-full overflow-hidden rounded-full bg-white/[0.07]">
            <div
              className={`h-full rounded-full ${
                isTranslating
                  ? "bg-gradient-to-r from-[#3b82f6] to-[#60a5fa]"
                  : "bg-white/20"
              }`}
              style={{ width: `${Math.max(item.progress * 100, isTranslating ? 8 : 0)}%` }}
            />
          </div>
        )}
      </div>

      {/* Right meta */}
      <div className="shrink-0 text-right">
        {isDone ? (
          <span className="text-[11px] font-medium text-[#28c840]">Done</span>
        ) : isTranslating ? (
          <span className="font-mono-ll text-[12px] text-[#7dacff]">
            {Math.round(item.progress * 100)}%
          </span>
        ) : (
          <span className="text-[11px] text-white/35">Queued</span>
        )}
      </div>
    </div>
  );
}
