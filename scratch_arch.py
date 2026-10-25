# -*- coding: utf-8 -*-
"""One-off: rewrite docs/ARCHITECTURE.md for the single-runtime (Python engine) layout."""
p = 'docs/ARCHITECTURE.md'
s = open(p, encoding='utf-8').read()

# 1. Replace section 2 (Two Synchronized Runtimes) with single-runtime statement
i2 = s.find('## 2. 🖥 Two Synchronized Runtimes')
i3 = s.find('## 3. 📂 Repository Directory Layout')
assert i2 > 0 and i3 > i2, 'section bounds not found'

sec2 = """## 2. 🖥 Single Runtime — One Engine, One UI

LayoutLingua ships **one runtime**: the Python engine is the whole backend, and `desktop/src/` is the single copy of the React UI that the Tauri shell builds and serves.

| | 🖥️ LayoutLingua Desktop |
|:---|:---|
| **Shell** | Tauri v2 native window (`desktop/src-tauri/`) |
| **UI bundle** | `desktop/src/` (Vite `:5173` during development, bundled by `npm run tauri build`) |
| **Engine** | `layoutlingua/server.py` — PyMuPDF vector core on `http://127.0.0.1:8765` |
| **Session store** | OS cache dir via `platformdirs` (`…/layoutlingua/Cache/sessions/`) |
| **Lifecycle** | Tauri auto-spawns the Python sidecar (`CREATE_NO_WINDOW`), kills it on exit; `start_app.bat` does the same for portable builds |

> ✅ **Provider honesty**: every provider must be genuinely available at translate time — Gemini requires its API key, OpenAI-compatible requires a key or a local endpoint, and Argos requires the `argostranslate` runtime. A missing dependency stops the job with an explicit error instead of silently falling back to another provider.

---

"""
s = s[:i2] + sec2 + s[i3:]

# 2. Directory tree: drop server.ts + src/, mark desktop/src as the single UI
old_tree_head = """LayoutLingua/
├── README.md                         # 🏠 Documentation hub — links to every doc in docs/
├── server.ts                         # 🌐 Express full-stack server, REST endpoints & .cache/sessions store
├── src/                              # 🎨 Web UI + TS translation engine
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
│   └── public/                       # Static assets (logo, favicons)"""
new_tree_head = """LayoutLingua/
├── README.md                         # 🏠 Documentation hub — links to every doc in docs/
├── desktop/                          # 🖥️ Tauri v2 desktop stack
│   ├── src/                          # 🎨 The single React UI copy (components, services, entry points)
│   │   ├── App.tsx                   # Application shell, navigation rail & modal orchestration
│   │   ├── components/               # OpenScreen · Workspace · PdfPage · ExportDialog · SettingsModal …
│   │   └── services/                 # api (engine URL) · history (IndexedDB) · settings
│   ├── src-tauri/                    # 🦀 Rust shell: backend sidecar lifecycle, CSP, bundle icons
│   └── public/                       # Static assets (logo, favicons)"""
assert old_tree_head in s, 'tree head not found'
s = s.replace(old_tree_head, new_tree_head)

# 3. Module titles: point at python modules
s = s.replace(
    '### 🧩 Module A: `analyzePdfPageLayout` (`src/engine/pdfTranslator.ts`)',
    '### 🧩 Module A: Structure & Clearance Analysis (`layoutlingua/core/parser.py`)'
)
s = s.replace(
    '### 🌍 Module B: `translateBatchWithFormulaShield` (`src/engine/pdfTranslator.ts`)',
    '### 🌍 Module B: Formula-Shielded Translation (`layoutlingua/translation/`)'
)
s = s.replace(
    '### 🖋️ Module C: `translateAndTypesetPage` (`src/engine/pdfTranslator.ts`)',
    '### 🖋️ Module C: Two-Pass Typesetting (`layoutlingua/typesetting/`)'
)
s = s.replace(
    '### 💾 Module D: Dual-Layer Session Persistence (`server.ts` & `src/services/history.ts`)',
    '### 💾 Module D: Dual-Layer Session Persistence (`layoutlingua/server.py` & desktop IndexedDB)'
)

# 4. Module D tail: replace the TS-specific bullets with python parity wording
old_d_tail = """- 🌐 **Frontend IndexedDB Store (`layoutlingua_pdf_cache_v1`)**:
  - Caches the raw `ArrayBuffer` of every opened PDF in browser IndexedDB.
  - `restoreOrVerifyRecentDoc` queries `/api/session-status` before opening any Recent Document and transparently re-uploads the cached binary if the server cache was cleared.
- 🐍 **Python engine mirror**: `layoutlingua/server.py` implements the same store (`source.pdf` / `translated.pdf` / `meta.json` under the OS cache dir), the same `session-status` recovery, `X-Doc-Id` content-hash dedupe, and `cancel` semantics that preserve already-translated pages."""
new_d_tail = """- 🌐 **Frontend IndexedDB Store (`layoutlingua_pdf_cache_v1`)**:
  - Caches the raw `ArrayBuffer` of every opened PDF in browser IndexedDB.
  - `restoreOrVerifyRecentDoc` queries `/api/session-status` before opening any Recent Document and transparently re-uploads the cached binary if the server cache was cleared.
- 🛡️ **Fail-closed guarantees**: a missing provider dependency (e.g. `argostranslate` for offline Argos) stops the job with an explicit error — the engine never silently substitutes another provider."""
assert old_d_tail in s, 'module D tail not found'
s = s.replace(old_d_tail, new_d_tail)

open(p, 'w', encoding='utf-8', newline='').write(s)
print('ARCHITECTURE.md rewritten for single runtime')
