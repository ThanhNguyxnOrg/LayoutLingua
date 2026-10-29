# 🏛 System Architecture (`ARCHITECTURE.md`)

<p align="center">
  <a href="../README.md">🏠 README</a> ·
  <a href="ARCHITECTURE.md">🏛 Architecture</a> ·
  <a href="ALGORITHM.md">🧮 Algorithms</a> ·
  <a href="API_REFERENCE.md">🔌 API</a> ·
  <a href="CHANGELOG.md">📜 Changelog</a> ·
  <a href="CONTEXT.md">🧭 Context</a> ·
  <a href="CONTRIBUTING.md">🤝 Contributing</a> ·
  <a href="CODE_OF_CONDUCT.md">🌈 Conduct</a> ·
  <a href="SECURITY.md">🔐 Security</a>
</p>

---

<p>
  <img src="https://img.shields.io/badge/🏛️_Architecture-Deep_Modules-0D9488?style=for-the-badge" alt="Deep Modules" />
  <img src="https://img.shields.io/badge/⚡_Runtime-Python_+_PyMuPDF-0284C7?style=for-the-badge" alt="Runtime" />
  <img src="https://img.shields.io/badge/🖥️_Desktop-Tauri_v2_+_Python_Engine-FFC131?style=for-the-badge" alt="Desktop Runtime" />
  <img src="https://img.shields.io/badge/🎨_Frontend-React_19_+_Tailwind_v4-3178C6?style=for-the-badge" alt="Frontend" />
  <img src="https://img.shields.io/badge/💾_Persistence-Disk_SHA256_+_IndexedDB-8B5CF6?style=for-the-badge" alt="Persistence" />
</p>

---

## 1. 🧭 Architectural Philosophy

LayoutLingua follows John Ousterhout's **Deep Module** design principle: each core subsystem exposes a minimal, declarative interface while encapsulating complex geometric, typographic, and linguistic machinery internally. 🧅

### 🧷 Core Invariants
1. **🚫 Zero Hardcoded Linguistic Heuristics**: Word classification, formula isolation, paragraph merging, and language detection rely strictly on **font-table flags (`vflag`)**, **2D coordinate geometry**, **Unicode general categories (`\p{Lu}`, `\p{Ll}`, `\p{Lo}`)**, and **statistical trigram profiles (`franc-min`)**.
2. **🛡️ Non-Destructive Vector Preservation**: Native PDF vector streams (diagrams, fraction bars, radical signs, integral symbols, curly braces, and table borders) are never parsed into lossy intermediate formats; only verified prose bounding boxes (`ProseSpan`s) are masked during Pass 1.
3. **📺 Flicker-Free Incremental Streaming**: Each translated page is committed atomically to the session buffer and tagged in `completed_pages`. Already-rendered pages in the React workspace remain mounted with stable keys (`runId + targetLang`) while subsequent pages process.
4. **🔁 Fail-Closed Resumability**: Sessions, translated bytes, and live integrity telemetry persist to disk continuously — killing the engine mid-job never loses completed work, and every un-fittable block falls back to its source text rather than rendering garbage.

---

## 2. 🖥 Single Runtime — One Engine, One UI

LayoutLingua ships **one runtime**: the Python engine is the whole backend, and `desktop/src/` is the single copy of the React UI that the Tauri shell builds and serves. The former Node/TypeScript web engine was fully merged into the Python typesetter (word-level formula pinning, token-flow freezing, newline-packed RPC, TOC navigation, legacy VNI decoding) and retired.

| | 🖥️ LayoutLingua Desktop |
|:---|:---|
| **Shell** | Tauri v2 native window (`desktop/src-tauri/`) |
| **UI bundle** | `desktop/src/` (Vite `:5173` during development, bundled by `npm run tauri build`) |
| **Engine** | `layoutlingua/server.py` — PyMuPDF vector core on `http://127.0.0.1:8765` |
| **Session store** | OS cache dir via `platformdirs` (`…/layoutlingua/Cache/sessions/`) |
| **Lifecycle** | Tauri auto-spawns the Python sidecar (`CREATE_NO_WINDOW`), kills it on exit; `start_app.bat` does the same for portable builds |

> ✅ **Provider honesty**: every provider must be genuinely available at translate time — Gemini requires its API key, OpenAI-compatible requires a key or a local endpoint, and Argos requires the `argostranslate` runtime. A missing dependency stops the job with an explicit error instead of silently falling back to another provider.

---

## 3. 📂 Repository Directory Layout

```text
LayoutLingua/
├── README.md                         # 🏠 Documentation hub — links to every doc in docs/
├── desktop/                          # 🖥️ Tauri v2 desktop stack
│   ├── App.tsx                       # Root application shell, navigation rail & modal orchestration
│   ├── main.tsx                      # React 19 entry point
│   ├── index.css                     # Tailwind CSS v4 design tokens & studio typography
│   ├── components/
│   │   ├── OpenScreen.tsx            # 📥 Document preflight, drag-and-drop upload & Recent Documents
│   │   ├── Workspace.tsx             # 📖 Dual-view canvas (Side-by-Side / Overlay), Inspector & Progress
│   │   ├── PdfPage.tsx               # 🖼️ High-DPI PNG page renderer, block hover & hyperlink overlays
│   │   ├── HistoryScreen.tsx         # 🗂️ Searchable recent document history with auto-recovery
│   │   ├── ExportDialog.tsx          # 📤 Monolingual PDF, Bilingual Interleaved PDF & Markdown export
│   │   ├── SettingsModal.tsx         # ⚙️ Provider configuration (Google NMT, Gemini, OpenAI/Ollama)
│   │   ├── HelpModal.tsx             # ⌨️ Keyboard shortcuts & pipeline reference
│   │   ├── data.ts                   # Shared TypeScript interfaces & 17-language registry
│   │   ├── shell.tsx                 # 🧭 AppHeader & NavRail components
│   │   ├── ui.tsx                    # 🧩 Studio UI primitives (Buttons, Badges, Notices)
│   │   └── icons.tsx                 # ✒️ Vector SVG icon library
│   ├── engine/
│   │   ├── pdfTranslator.ts          # ⚙️ Core MuPDF + pdf-lib layout analyzer, math isolator & typesetter
│   │   └── glossaries/               # 📚 16 bidirectional academic math JSON glossaries (en <-> 16 langs)
│   └── services/
│       ├── api.ts                    # 🔗 API URL resolver
│       ├── history.ts                # 💾 localStorage + IndexedDB binary PDF cache & session recovery
│       └── settings.ts               # 🔧 Persistent translation & typography settings
├── desktop/                          # 🖥️ Tauri v2 desktop stack
│   ├── src/                          # Synced React UI fork (Tauri-specific ExportDialog & SettingsModal)
│   ├── src-tauri/                    # 🦀 Rust shell: backend sidecar lifecycle, CSP, bundle icons
│   └── public/                       # Static assets (logo, favicons)
├── layoutlingua/                     # 🐍 Independent Python engine (JSON-RPC/HTTP on :8765)
│   ├── server.py                     # REST endpoints, session store & worker threads
│   ├── core/                         # DocumentIR parser & geometry model
│   ├── translation/                  # Providers, glossaries & persistent segment cache
│   ├── typesetting/                  # TypesetEngine, DocumentAccumulator, fitting telemetry
│   └── processing/                   # Page ranges, TOC translation, Markdown export, telemetry
├── tests/                            # 🧪 265 automated engine tests (pytest)
└── docs/                             # 📚 Documentation tree (README.md at root is the hub)
    ├── ARCHITECTURE.md               # 🏛 Deep Module specifications & two-runtime design
    ├── ALGORITHM.md                  # 🧮 vflag pinning, ray-cast clearance, anisotropic Tz
    ├── API_REFERENCE.md              # 🔌 Dual-engine REST contract & payload schemas
    ├── CONTEXT.md                    # 🧭 Ubiquitous domain language
    ├── CHANGELOG.md                  # 📜 Release history
    ├── CONTRIBUTING.md               # 🤝 Engineering standards & PR checklist
    ├── CODE_OF_CONDUCT.md            # 🌈 Community covenant
    ├── SECURITY.md                   # 🔐 Privacy guarantees & reporting
    └── assets/                       # 🖼️ Logo & demo screenshots
```

---

## 4. 🔬 Deep Module Specifications

### 🧩 Module A: `analyzePdfPageLayout` (`layoutlingua/`)
- **Responsibility**: Extracts structured characters from a MuPDF page, normalizes legacy encodings, partitions tokens into `ProseGroup`s vs. `MathObstacle`s / `LinkObstacle`s, and computes pixel-exact horizontal clearances.
- **Pipeline Stages**:
  1. **🔍 Structured Text Walk**: Walks `page.toStructuredText('preserve-whitespace')` to capture every glyph's quad (`x0, y0, x1, y1`), baseline origin (`ox, oy`), font name, weight/style flags (`bold, italic, serif, mono`), size, and RGB fill color.
  2. **🌡️ Superscript Degree Normalization**: Normalizes raised degree glyphs (`MT Extra 0xF06F`, `Symbol 0xF0B0`, `°`, `º`) onto their preceding token's baseline so `60°` and `n°` remain 1D inline tokens.
  3. **🧲 2D Sub/Superscript Separation**: Extracts characters with `size < 8.5pt` as immediate `MathObstacle`s and marks horizontally/vertically adjacent main tokens with `hasAdjSubSup = true`.
  4. **📏 Baseline Row & Column Run Grouping**: Groups main characters into baseline rows ($\Delta oy \le 2.2\text{pt}$), detects full-row Table-of-Contents dot leaders (`.....`), and splits multi-column runs at horizontal gaps ($> \max(14\text{pt}, 1.4 \times \text{size})$).
  5. **✂️ Word Tokenization & Contextual Pass**: Applies `isMathWordToken` followed by a 5-rule contextual pass (`lineIsMostlyItalic`, ALL-CAPS heading recovery, 1D variable lists, and opening parenthetical variables).
  6. **📡 Pixmap Ray-Cast Clearance**: Renders a 1x RGB pixmap of the page and scans horizontally left and right from each `ProseSpan` to find the exact clearance (`leftClearanceX`, `rightClearanceX`) before hitting ink from diagrams, braces, or adjacent columns.
  7. **🧱 Multi-Line Paragraph Merging (`canMerge`)**: Merges consecutive `ProseSpan`s into `ProseGroup`s when style, color, background, column alignment, and line-width fill ratio match—while refusing to merge across horizontal table borders or parallel formula table rows.

### 🌍 Module B: `translateBatchWithFormulaShield` (`layoutlingua/`)
- **Responsibility**: Translates an array of `ProseGroup` strings while guaranteeing 100% invariance of inline mathematical expressions and domain terminology.
- **Pipeline Stages**:
  1. **🔠 ALL-CAPS Heading Recasing**: Converts ALL-CAPS headings to sentence case before NMT so subword BPE tokenizers never truncate uppercase endings, then restores uppercase after translation.
  2. **🔒 Formula & Glossary Shielding (`shieldFormulas`)**: Replaces user custom glossary terms, standalone academic glossary headings, and inline mathematical expressions with opaque `⟦M0⟧`, `⟦M1⟧` tokens.
  3. **⚡ Target-Language Short-Circuit (`isAlreadyInTargetLanguage`)**: Uses `franc-min` trigram detection to skip blocks already written in the target language.
  4. **🔀 Multi-Provider Dispatch**: Routes batches through Gemini 2.5 Flash, OpenAI-compatible endpoints, or multi-mirror Google Translate (`client=at` POST + `client=gtx` GET) with SHA-256 in-memory caching.
  5. 🩹 **Self-Healing Token Restoration (`restoreFormulas`)**: Repairs any NMT spacing or bracket mutations (`[M0]`, `【M 0】` $\rightarrow$ `⟦M0⟧`) and restores exact formula strings.

### 🖋️ Module C: `translateAndTypesetPage` (`layoutlingua/`)
- **Responsibility**: Executes Two-Pass Selective Erasure and Adaptive Vector Typesetting onto a `pdf-lib` `PDFPage`.
- **🧽 Pass 1 (Selective Prose Erasure)**:
  - Draws background-matched rectangles (`sampleBackgroundRGB`) over each `ProseSpan` of every translated `ProseGroup`, clipped strictly by neighboring `MathObstacle`s so adjacent fraction bars, integrals, and curly braces are never touched.
- **🖋️ Pass 2 (Adaptive Vector Typesetting)**:
  - **🧭 TOC Entries (`kind === 'toc'`)**: Renders the translated title at left alignment, right-aligns the page number at `sp.x1`, and dynamically fills the gap with `. . .` leaders (`\dotfill`).
  - **➡️ Single-Line Spans (`spans.length === 1`)**: Uses bidirectional clearance (`availLeftShift` + `rightClearanceX`), 2-line compact wrapping when unobstructed below, or anisotropic `Tz` horizontal condensation (`82%–100%` for multi-word text, **`72%` for a single word** — a lone word has no wrap points and may ride the same 72–78% squeeze the TOC/multi-line paths use) combined with vertical font scaling.
  - **📚 Multi-Line Paragraphs (`spans.length > 1`)**: Binary-searches font scale from `1.0` down to `effectiveMinScale`, falling back to horizontal condensation (`Tz` at `92%`, `86%`, `80%`) so all translated lines fit within `maxBottomY` without ever dropping or truncating lines.

### 💾 Module D: Dual-Layer Session Persistence (`layoutlingua/server.py` & desktop IndexedDB)
- **🗄️ Backend Disk Store (`.cache/sessions/<docId>/`)**:
  - Keyed by the 12-character SHA-256 content hash of the uploaded PDF (or the client-provided `X-Doc-Id`).
  - Stores `source.pdf`, `translated.pdf`, and `state.json` (`page_results`, `progress`, `integrity`, `page_dimensions`).
  - Automatically recovers sessions across server restarts via `findPersistedSession`, and **deduplicates re-uploads** of the same content so reopening a document never duplicates translation work.
- **🌐 Frontend IndexedDB Store (`layoutlingua_pdf_cache_v1`)**:
  - Caches the raw `ArrayBuffer` of every opened PDF in browser IndexedDB.
  - `restoreOrVerifyRecentDoc` queries `/api/session-status` before opening any Recent Document and transparently re-uploads the cached binary if the server cache was cleared.
- 🐍 **Python engine mirror**: `layoutlingua/server.py` implements the same store (`source.pdf` / `translated.pdf` / `meta.json` under the OS cache dir), the same `session-status` recovery, `X-Doc-Id` content-hash dedupe, and `cancel` semantics that preserve already-translated pages.
