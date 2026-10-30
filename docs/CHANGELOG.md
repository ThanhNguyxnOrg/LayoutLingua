# 📜 Changelog (`CHANGELOG.md`)

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
  <img src="https://img.shields.io/badge/📜_Changelog-Keep_a_Changelog_1.1.0-0D9488?style=for-the-badge" alt="Keep a Changelog" />
  <img src="https://img.shields.io/badge/🔢_Versioning-SemVer_2.0.0-0284C7?style=for-the-badge" alt="SemVer" />
</p>

All notable changes to **LayoutLingua** are documented in this file.

---

## [2.1.3] — 2026-10-30

### 🚀 Added
- 📦 **Multi-Platform Desktop Packaging in CI/CD**:
  - Upgraded `.github/workflows/release.yml` desktop packaging pipelines for Windows (`.zip`), macOS (`.tar.gz`), and Linux (`.tar.gz`).
  - Bundles compiled Vite Web Studio assets (`dist/`), Express proxy (`server.ts`), core Python engine (`layoutlingua/`), dependencies (`requirements.txt`, `package.json`), and documentation into clean standalone release distributions.
- 🔬 **Empirical Root Cause Analysis & Resolution**:
  - Investigated and documented the PyMuPDF 2.0 layout-model gating failure mechanism, primary source evidence, and multi-tier defensive corroboration.

### 🩹 Fixed
- 📦 **PyMuPDF 2.0 & Cross-Platform CI Compatibility**:
  - Resolved `AssertionError: 0 != 1` in `TableGridValidator` on Linux (`ubuntu-latest`), macOS (`macos-latest`), and Windows (`windows-latest`) runners under Python 3.12.
  - PyMuPDF 2.0 bundled `pymupdf-layout==2.0` which defaulted `find_tables(use_layout=True)` and discarded candidate tables when layout models did not tag regions as `"table"`.
  - Updated `TableGridValidator.validate_page_tables` to call `find_tables(use_layout=False)` with safe fallbacks, bypassing layout-model early exits and guaranteeing strict physical vector stroke corroboration ($\ge 90\%$ coverage) across PyMuPDF versions `1.25.0` through `2.0+`.
- 🧮 **Documentation & Typographic Formulas Clean-up**:
  - Fixed syntax formatting errors in `docs/ALGORITHM.md` line 49/50 (resolved KaTeX percent escape handling and unbalanced parenthetical code formatting).
  - Synchronized 100% of all repository markdown documentation (`docs/*.md`, `README.md`) into fluent, professional English with rich visual badges, stickers, and emojis.
  - Bumped project semantic version to `2.1.3` across `package.json` and `layoutlingua/_version.py`.

---

## [2.1.2] — 2026-10-30

### 🚀 Added
- 📦 **Argos Offline AI Engine & Language Pack Manager**:
  - Added `GET /api/argos/status` endpoint querying CTranslate2 runtime health, installed models, and available packages.
  - Added `POST /api/argos/install` endpoint allowing one-click setup of the offline AI runtime (`pip install argostranslate`) directly from the UI, with on-demand download of language packs (`en↔vi`, `en↔zh`, `en↔ja`, `en↔ko`, `en↔fr`, `en↔de`, `en↔es`).
  - Added `auto_install=True` route resolution in `ArgosTranslationProvider` to automatically pull missing models during offline translation jobs.
- 🧠 **Gemini 404 Deprecation Auto-Healing**:
  - Implemented dynamic model alias resolution (`auto`, `latest`, `gemini-auto`) with multi-factor model scoring (`_score_gemini_model`) favoring newest active Flash models.
  - Built-in 404 Auto-Healing: if Google retires an older model in the future, LayoutLingua automatically queries `/v1beta/models`, switches to the newest active Flash model, and retries seamlessly without job interruption.
  - Added model discovery query in `GET /api/models?provider=gemini&api_key=...` with UI model chips in `SettingsModal.tsx`.
- 🦙 **Universal Local & Cloud LLM Presets**:
  - Added one-click UI presets in `SettingsModal.tsx` for **Local Ollama** (`http://localhost:11434/v1`), **Local LM Studio** (`http://localhost:1234/v1`), **OpenAI Cloud**, and **DeepSeek**.
  - Added auto-healing model fallback for local and OpenAI-compatible endpoints when a requested model ID is not loaded or deprecated.
- 🧪 **Test Suite Expansion**: Added unit tests in `test_slice3c_cloud_providers.py` for Gemini 404 auto-healing and Argos model auto-installation, bringing the automated test count to **276 passed (100%)**.

---

## [2.1.1] — 2026-10-30

### 🚀 Added
- **Live Provider Connection Test**: Added `POST /api/test-provider` endpoint and integrated a live "Test Connection" button in `SettingsModal.tsx`, validating API key validity, endpoint latency in milliseconds, and formula token invariance (`<b0></b0>`).
- **Zero-Dependency Native REST LLM Client**: Added standard-library `urllib.request` fallback in `OpenAITranslationProvider` and `GeminiTranslationProvider`, allowing direct cloud translation without requiring `pip install openai` or external SDKs.
- **Extended Language Code Normalization**: Supported full Chinese Traditional (`zh-TW`), Chinese Simplified (`zh-CN`), Portuguese (`pt`), Italian (`it`), Dutch (`nl`), Polish (`pl`), Turkish (`tr`), Arabic (`ar`), and Thai (`th`) in `GoogleRpcTranslationProvider`.

### 🩹 Fixed
- **Intra-Word Font Fallback Coalescing**: Natural prose words split mid-word across fallback font spans (e.g., `T` + `ổ` + `ng h` + `ợ` + `p` -> `Tổng hợp`) now cleanly coalesce into single prose tokens without creating false-positive math obstacles.
- **VNI Spaced Composite Normalization**: Re-ordered VNI decoding replacements so circumflex and breve rules execute before acute/grave, preventing `Hoaùn` / `Ho a ù n` from wrongly mutating to `Hốn`. Added idempotence guard to protect pre-composed Unicode text.
- **TOC Dot Leaders & Academic Glossary Alignment**: Fixed capitalization preservation for all-caps headings (`matched_str.isupper()`), prevented dot-leader stripping during post-restore glossary normalization, and refined target-language skipping heuristics to avoid falsely bypassing Vietnamese TOC headers like `7. Logarith ... 30`.
- **Inline Code Pill Vector Art Protection**: Added detection and parent-background clearance for borderless inline code/highlight pill rectangles (height 8–24pt), eliminating false `VECTOR_ART` collision fallbacks.
- **Test Suite Expansion**: Added 9 new regression tests in `test_math_book_fixes.py`, `test_slice4c_protection.py`, `test_google_rpc.py`, and `test_slice3c_cloud_providers.py`, bringing the automated test count to **274 passed (100%)**.

---

## [2.1.0] — 2026-10-29

### 🚀 Added
- **Full-Stack AI Studio Web Architecture**: Integrated the Google AI Studio runtime (`server.ts` Express + Vite dev proxy on port 3000, Python core engine on port 8765, React 19 + TypeScript + Tailwind CSS UI in `src/`).
- **Consolidated Clean Repository**: Retired obsolete legacy subfolders, streamlined dependency management (`package.json`, `package-lock.json`), and validated automated tests with live browser end-to-end verification.
- **Multi-Family Font Suite**: Packaged 21 TrueType font files in `layoutlingua/typesetting/assets/fonts/` (`DejaVuSans`, `DejaVuSerif`, `FreeSans`, `FreeSerif`, `DejaVuSansMono` with complete bold/italic variants), enabling rich typographic fidelity and automatic CJK inline fallback (`china-s`, `china-t`, `japan`, `korea`).
- **Phonological Syllabic Hyphenation**: Added `hyphenate_word` for Romance and Germanic languages, supporting narrow multi-line column header fitting and stacked label leftward expansion.
- **Server Disk Session Recovery**: Added `/api/recent-sessions` endpoint allowing clients to discover and rehydrate existing sessions directly from disk cache across restarts.
- **Enhanced DocumentIR Parser**: Added horizontal gap line splitting (`_split_lines_across_horizontal_gaps`), vertical graphic divider extraction (`_extract_page_vertical_dividers`), and vertical hyphenated fragment rejoining.
- **Web UI Rehydration & Lazy Rendering**: Added automatic session discovery on `OpenScreen`, retry and IntersectionObserver lazy loading in `PdfPage`, and complete 17-language code mapping in `Workspace`.

---

## [2.0.0] — 2026-10-25

🎉 **First stable release** — the complete layout-aware PDF translation engine, verified end-to-end on a 96-page Vietnamese mathematical handbook (921 prose groups, legacy VNI encoding, dense 2D equations) with **0 overflow warnings, 0 PUA leaks, and 100% vector preservation**.

### 🚀 Added

**🧮 Translation & Typesetting Engine**
- **Two-Pass Selective Prose Erasure**: only verified natural-language prose spans are removed from the PDF content stream (MuPDF-native redaction pre-pass on a private document copy, obstacle-clipped, with paint-over rectangles as the fail-closed fallback) — mathematical equations, vector arrows, curly braces, table grids, and geometric diagrams stay 100% untouched in the original vector paths. Copy/paste from the exported PDF yields only translated text + original math. 📋
- **Sub-Line Formula Pinning (`vflag`)**: glyphs in `Symbol` / `MT Extra` / TeX math fonts and 2D sub/superscript geometry ($\Delta y \ge 1.5\text{pt}$) are frozen as `MathObstacle`s; paragraph-relative italic style-switch and a 5-rule contextual recovery pass keep natural prose intact. **Zero hardcoded word lists.** 🚫📝
- **Bidirectional Pixmap Ray-Cast Clearance**: sub-point detection of vertical braces, diagrams, and table rules around every prose span.
- **Anisotropic `Tz` Fitting**: binary-search font scaling combined with PDF horizontal condensation (82–100%, **64% for single words scaled by the min font floor** — a lone word between formulas always fits its line 🤸), multi-line wrapping with multi-stage condensation (`92% / 86% / 80%`) so **no line is ever dropped**, and LaTeX `\dotfill` TOC leader harmonization.
- **🌍 17-Language Statistical Detection (`franc-min`)**: ISO 639-3 trigram profiles + Unicode script ranges; legacy **VNI-Windows** and **Symbol PUA** decoders normalize to Unicode NFC.
- **📚 16 Bidirectional Academic Math Glossaries**: 136+ terms, English-pivot across all 272 language pairs; CJK font dispatch (`Noto Sans SC/TC/JP/KR`) with kin-soku punctuation wrapping.

**🔌 Multi-Provider Pipeline & Persistence**
- **Zero-Setup Google Translate RPC** out of the box 🆓, plus Gemini, any OpenAI-compatible endpoint (OpenAI, DeepSeek, Groq, Ollama, LM Studio) with `/models` discovery, and **Argos Translate** for 100% offline privacy. 📴
- **💾 Dual-Layer Session Persistence**: backend disk store (`.cache/sessions/<sha256>/` — source, translated, live progress & integrity) + frontend IndexedDB blob cache; **restart-proof resume** verified by full engine kills, `/api/session-status` recovery, and content-hash upload dedupe via `X-Doc-Id`.
- **🧮 Persistent Segment Cache**: every translated segment survives restarts and rate-limit halts — no duplicate API cost.
- **🔗 Hyperlink & Navigation Preservation**: native `http(s)`/`mailto` links re-registered as PDF `/Link` annotations; internal GoTo destinations resolve to `#page=N` and the Mục lục viewer jumps straight to the target page; the PDF /Outlines bookmark tree is translated too.
- **🔌 Full REST contract on the engine** — `session-status` resume, content-hash upload dedupe, `cancel` (keeps translated pages), `page-preview?format=meta` block/hyperlink metadata with `#page=N` navigation, real-folder `/api/save` (OneDrive redirection aware ⚡ 0.3s), and the full export matrix.

**🖥️ Desktop Application & UI**
- **Tauri v2 Shell** (React 19 + TypeScript + Tailwind v4) with zero-window Python sidecar lifecycle (`CREATE_NO_WINDOW`, graceful exit).
- **Dual-View Workspace**: side-by-side synchronized canvases, **alpha-blend overlay slider** (0–100%), interactive bounding-box inspector & clickable hyperlink overlays, flicker-free incremental page streaming (`completed_pages` keys).
- **📥 Document Preflight & Recent Documents**: drag-and-drop upload, scanned-PDF detection with OCR warning, persistent recents with automatic session recovery.
- **📤 Export Dialog**: monolingual PDF, **bilingual interleaved PDF** (original ↔ translated pairs with doubled TOC page numbers), and structured Markdown; direct-to-folder saving with **Open in File Explorer**.
- **🩺 Quality Checks & Diagnostics**: two-tier fitting telemetry (document / page / block), structured `OVERFLOW_FALLBACK` warnings, one-click **Copy log** export for LLM triage.
- **🖼️ Demo Gallery**: real wide-angle captures embedded in the README (`docs/assets/`).
- **🗂️ Live Recent-Document Thumbnails**: each Recent documents row renders a miniature first-page preview (stable skeleton + graceful glyph fallback) instead of a blank placeholder.

### 🔧 Fixed
- **Display formulas survive redaction** 🧮: the MuPDF redaction pre-pass runs on a private document copy so its restructured Form XObjects stay self-consistent — earlier stream-transplant approaches blanked `f(x)=f(x±l)…`, `f′(x)≥0(f′(x)≤0)`, `lim`, and `x₀±a` regions.
- **`OVERFLOW_FALLBACK` on single-word sliver blocks**: one-word fragments between frozen math regions (10pt `từ` slots) now fit via min-floor-scaled `Tz` condensation — quality report **0 warnings** on the full 96-page benchmark. 🏆
- **`MT Extra` / Symbol vector arrow preservation**: unconditional `vflag` math classification — `0` PUA leaks (`υυυρ` corruption eliminated).
- **Symbol table row separation**: geometric row-obstacle guards stop adjacent table rows from merging vertically.
- **Flicker-free live preview**: stable run-scoped page keys — completed pages never unmount while later pages translate.
- **Export size & speed**: save-once + `subsetFonts()` + garbage-collected output — full 96-page document **46MB → ~1.5MB**, export < 1s. ⚡
- **🧮 Word-level formula pinning ported to the Python engine**: word tokens classified with the TS rules (`vflag` fonts, 2D sub/superscript adjacency, contextual italic recovery) and a token-flow typesetting path that freezes original math glyphs while drawing translated prose into the gaps — inline formulas render in position on the desktop engine (the shattered `f ′ x 0` fragments are gone). Includes sequential baseline-row clustering and strictly intra-line adjacency.
- **🔌 Google mirror stack + per-segment requests**: `client=at` mirrors with the AndroidTranslate UA tier first; delimiter packing replaced by segment-level requests (Google mangles the formula placeholders of every segment after the first — A/B verified).
- **Honest provider behaviour on both engines** 🤝: selecting **Argos Translate** without its offline runtime now fails explicitly instead of silently falling back to Google Translate RPC (web engine returns a 400 with guidance; the desktop engine raises the same error) — the offline privacy promise is never faked. The Settings card is labelled `DESKTOP ONLY` in the browser.
- **Desktop export slimming**: the Python accumulator subsets embedded fonts and garbage-collects the output — 96-page export **53.9MB → ~1.4MB**, matching the web engine.

### 🧹 Changed
- **🖥️ Single-runtime consolidation (final)**: the Node/TS web engine was fully merged into the Python typesetter — word-level formula pinning with token-flow glyph freezing, newline-packed Google RPC batching (15x fewer requests, no mid-job rate limits), TOC `#page=N` navigation, OneDrive-aware `/api/save`, legacy VNI/TCVN3 decoding — verified end-to-end on the 96-page benchmark (0 warnings, 0 source remnants) before retiring `server.ts`, the root `src/` copy, and the web packaging. `desktop/src/` is the single UI and `layoutlingua/server.py` the single engine.
- **📚 Documentation Hub**: the repo carries only `README.md` at the root — every deep-dive (Architecture, Algorithms, API Reference, Context, Changelog, Contributing, Conduct, Security) lives in `docs/` with cross-linked navigation back to the hub.
- Repo trimmed to pure source — no runtime caches, archives, drop archives, or scratch files.
- Full **245-test** pytest suite, strict TypeScript across web + desktop, CI matrix on Ubuntu / Windows / macOS.

---

## [1.x] — 2026

- 🌱 Early contract skeleton: DocumentIR, mock provider, CLI + JSON-RPC IPC, and the first MuPDF vector preview renderer.
