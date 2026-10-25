# Changelog (`CHANGELOG.md`)

<p>
  <img src="https://img.shields.io/badge/Changelog-Keep%20a%20Changelog%201.1.0-0D9488?style=for-the-badge" alt="Keep a Changelog" />
  <img src="https://img.shields.io/badge/Versioning-Semantic%20Versioning%202.0.0-0284C7?style=for-the-badge" alt="SemVer" />
</p>

All notable changes to **LayoutLingua** are documented in this file.

---

## [2.1.1] — 2026-10-25

### 🚀 Added
- **🖥️ Full Desktop/Engine Parity**: The Tauri desktop stack (`desktop/` + Python engine `layoutlingua/server.py`) now implements the identical REST contract as the web stack — `GET /api/session-status`, content-hash upload dedupe with `X-Doc-Id`, `POST /api/cancel` (keeps already-translated pages), and `page-preview?format=meta` block metadata for the inspector/hyperlink overlays.
- **💾 Python Engine Session Persistence Hardening**: Disk-backed session cache (`source.pdf` / `translated.pdf` / `meta.json` under the OS cache dir) with transparent recovery after full engine restarts, plus per-5-page continuous persistence and bounded `MAX_SESSIONS` eviction.
- **🖼️ Demo Documentation Suite**: Wide-angle demo captures (Open & Preflight, Dual-View Workspace, Alpha-Blend Overlay) bundled at `docs/assets/` and embedded in the README.

### 🔧 Fixed
- **`OVERFLOW_FALLBACK` on Single-Word Sliver Blocks**: One-word prose fragments sandwiched between frozen math regions (e.g. a 10pt `từ` slot on page 78) could never fit their translation at the `82%` Tz condensation floor. Single words now tolerate a **`72%` Tz floor** (no wrap points — the same squeeze range the TOC and multi-line paths already use). Verified on the 96-page benchmark: quality report drops from `1 warning` to **`0`** with the fragment rendering inside its clearance without overlap.
- **🪄 Logo Wordmark Restored**: The header logo `<img src="/logo.png">` (previously replaced by a text badge during the workspace sync) is back in **both** web and desktop shells.

### 🧹 Changed
- **README & Docs Overhaul**: README now embeds real demo screenshots and the desktop quickstart; `ARCHITECTURE.md` documents the two-runtime topology (web TS engine ↔ desktop Python engine) with the parity matrix; `docs/API_REFERENCE.md` covers the full shared endpoint contract; `docs/ALGORITHM.md` documents the new single-word `Tz` rule.
- **Repository Hygiene**: Test sessions, temporary exports, and stray runtime artifacts purged; `.gitignore` covers `.cache/` and drop archives.

---

## [2.1.0] — 2026-10-23

### 🚀 Added
- **17-Language Statistical Trigram Detection (`franc-min`)**: Replaced static keyword heuristics with ISO 639-3 character trigram profiles (`franc-min`) combined with Unicode script range detectors across all 17 supported languages (`en`, `vi`, `zh-CN`, `zh-TW`, `ja`, `ko`, `fr`, `de`, `es`, `ru`, `it`, `pt`, `id`, `nl`, `pl`, `tr`, `uk`).
- **Dual-Layer Recent Documents Persistence**:
  - **Backend Disk Store (`.cache/sessions/<sha256>/`)**: Automatically persists `source.pdf`, `translated.pdf`, and `state.json` on disk across server restarts.
  - **Frontend IndexedDB Cache (`layoutlingua_pdf_cache_v1`)**: Caches binary PDF blobs in IndexedDB and validates `/api/session-status` before opening recent documents, automatically re-uploading if needed.
- **Interactive PDF Hyperlink Overlay**: Extracts native PDF `/Link` annotations via MuPDF `page.getLinks()` and resolves flattened blue citation links (`More…`) into clickable `<a>` overlays on both Source and Translated views.
- **16 Bidirectional Academic Math Glossaries**: Synchronized 136+ geometry, algebra, calculus, and combinatorics handbook entries across all 16 `src/engine/glossaries/academic_math_en_*.json` files with English-pivot support for arbitrary language pairs.
- **CJK Font Bundling & Grapheme Line Wrapping**: Automatic embedding of `Noto Sans SC`, `Noto Sans TC`, `Noto Sans JP`, and `Noto Sans KR` with CJK punctuation kin-soku rules.

### 🔧 Fixed
- **Flicker-Free Live Page Preview**: Scoped `<PdfPage>` keys to `(docId, pageNum, runId, targetLang)` and tracked per-page completion (`completed_pages`) on the backend so already-translated pages never unmount or flicker while subsequent pages translate.
- **`MT Extra` / `Symbol` Vector Arrow Preservation**: Enforced unconditional `vflag` math classification (`if (hasSymbolFont) return true`) so 4-glyph PUA vector arrows (`0xF075, 0xF075, 0xF075, 0xF072` over $\overrightarrow{AB}$) are 100% preserved and never rendered as `"υυυρ"`.
- **Multi-Column Symbol Table Row Separation**: Added geometric row-obstacle guards (`hasNewLeftSymbolRow` and `hasDistinctRightFormulaRows`) and line-width fill checks in `canMerge` so adjacent rows in symbol tables (e.g., *"Đồng dạng"* vs. *"Song song và cùng chiều"* vs. *"Song song và ngược chiều"*) never merge vertically.
- **Subscripted Leading Variables ($P_n.$)**: Prioritized `hasAdjacentSubSup` before list/initial prefix matching in `isMathWordToken` so subscripted symbols followed by a period ($P_n.$) are preserved as 2D math obstacles.
- **Parenthetical 1D Variable Grouping (`(n factorial)`)**: Preserved opening parenthetical 1D variables (`(n`) with their immediately following prose clause (`giai thừa)`).
- **Zero Line Truncation in Multi-Line Paragraphs**: Added multi-stage horizontal condensation (`Tz` at `92%`, `86%`, `80%`) for multi-line paragraphs so 100% of translated lines fit vertically without dropping lines.

---

## [2.0.0] — 2026-09-15

### 🚀 Added
- Initial **Two-Pass Selective Prose Erasure** and **Sub-Line Formula Pinning** architecture using MuPDF structured text quads and `pdf-lib`.
- LaTeX `\dotfill` Table-of-Contents dot leader harmonization.
- Legacy **VNI-Windows** (`VNI-Times`) and **Symbol PUA** (`U+F020..U+F0FF`) Unicode NFC decoders.
- Dual-view React 19 workspace with Side-by-Side and Alpha-Blend Overlay inspection modes.
