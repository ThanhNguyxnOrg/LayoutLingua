# 📜 Changelog (`CHANGELOG.md`)

<p>
  <img src="https://img.shields.io/badge/📜_Changelog-Keep_a_Changelog_1.1.0-0D9488?style=for-the-badge" alt="Keep a Changelog" />
  <img src="https://img.shields.io/badge/🔢_Versioning-SemVer_2.0.0-0284C7?style=for-the-badge" alt="SemVer" />
</p>

All notable changes to **LayoutLingua** are documented in this file.

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
- **🖥️ Dual-Engine REST Contract**: the React UI runs unchanged on the Node web engine (`:3000`) and the Python engine (`:8765`) — `session-status`, content-hash dedupe, `cancel` (keeps translated pages), `page-preview?format=meta` block/hyperlink metadata, real-folder `/api/save` (OneDrive redirection aware ⚡ 0.3s), and the full export matrix.

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

### 🧹 Changed
- Documentation consolidated into a **self-contained README hub** (algorithms + REST API folded in); repo trimmed to pure source — no runtime caches, archives, or scratch files.
- Full **245-test** pytest suite, strict TypeScript across web + desktop, CI matrix on Ubuntu / Windows / macOS.

---

## [1.x] — 2026

- 🌱 Early contract skeleton: DocumentIR, mock provider, CLI + JSON-RPC IPC, and the first MuPDF vector preview renderer.
