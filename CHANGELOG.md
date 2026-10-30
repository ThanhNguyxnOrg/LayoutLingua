# 📜 Changelog (`CHANGELOG.md`)

<p align="center">
  <a href="README.md">🏠 README</a> ·
  <a href="docs/ARCHITECTURE.md">🏛 Architecture</a> ·
  <a href="docs/ALGORITHM.md">🧮 Algorithms</a> ·
  <a href="docs/API_REFERENCE.md">🔌 API</a> ·
  <a href="docs/CHANGELOG.md">📜 Changelog</a> ·
  <a href="docs/CONTEXT.md">🧭 Context</a> ·
  <a href="docs/CONTRIBUTING.md">🤝 Contributing</a> ·
  <a href="docs/CODE_OF_CONDUCT.md">🌈 Conduct</a> ·
  <a href="docs/SECURITY.md">🔐 Security</a>
</p>

---

<p>
  <img src="https://img.shields.io/badge/📜_Changelog-Keep_a_Changelog_1.1.0-0D9488?style=for-the-badge" alt="Keep a Changelog" />
  <img src="https://img.shields.io/badge/🔢_Versioning-SemVer_2.0.0-0284C7?style=for-the-badge" alt="SemVer" />
</p>

All notable changes to **LayoutLingua** are documented in this file.

---

## [2.0.0] — 2026-10-30

🎉 **Major Milestone Release** — LayoutLingua 2.0 introduces native standalone desktop executables for **3 Operating Systems** (Windows direct `.exe`, macOS dual-architecture `.dmg`, Linux native binary), the **Argos Offline AI Engine**, resilient **Gemini 404 Deprecation Auto-Healing**, and zero-loss layout geometry and formula preservation verified across 276 automated tests. 🚀✨

> 💡 *Note*: Web dev server mode (`npm run dev`) is strictly reserved for local developer testing. End-user distributions are exclusively standalone native desktop applications.

### 🖥️ Native Standalone Desktop Applications (Direct Download — Zero ZIP)
- **🪟 Windows (`LayoutLingua-windows-x86_64.exe`)**: Direct standalone executable file with embedded high-resolution brand icon (`icon.ico`). Double-click to launch the native desktop application immediately with zero extraction, zero terminal commands, and zero Python/Node setup requirements.
- **🍎 macOS Apple Silicon (`LayoutLingua-macos-apple-silicon.dmg`)**: Native Apple Silicon disk image bundling `LayoutLingua.app` compiled for ARM64 (M1/M2/M3/M4 chips) with official `.icns` brand icons and standard `/Applications` drag-and-drop installer.
- **🍎 macOS Intel (`LayoutLingua-macos-intel.dmg`)**: Native Intel Mac disk image bundling `LayoutLingua.app` compiled for x86_64 Intel Macs with official `.icns` brand icons and standard `/Applications` drag-and-drop installer.
- **🐧 Linux (`LayoutLingua-linux-x86_64`)**: Standalone native ELF binary executable pre-configured for direct execution on any modern Linux distribution.
- **🎨 Brand Identity & Iconography**: Embedded official multi-resolution icon assets (16x16 to 256x256) into binaries, application window title bars, taskbars, and browser favicons.

### 📦 Argos Offline AI Engine & Privacy
- **100% Offline Translation**: Integrated CTranslate2 and Argos Translate runtime support for complete data confidentiality without sending a single byte to external clouds.
- **Language Pack Manager**: Added `GET /api/argos/status` and `POST /api/argos/install` endpoints enabling one-click download of language pairs directly from the UI (`en↔vi`, `en↔zh`, `en↔ja`, `en↔ko`, `en↔fr`, `en↔de`, `en↔es`).
- **Auto-Installation on Demand**: Automatically downloads and installs required offline model packages when missing during an offline translation run (`auto_install=True`).

### 🧠 Gemini 404 Deprecation Auto-Healing
- **Dynamic Model Alias Resolution**: Maps `auto`, `latest`, and `gemini-auto` to the highest-scoring active Flash model via `_score_gemini_model`.
- **Zero-Downtime Deprecation Recovery**: If Google sunsets an older model in the future, LayoutLingua intercepts HTTP 404 deprecation errors, queries `/v1beta/models`, switches to the newest active Flash model, and retries seamlessly without interrupting the user.
- **Live Model Discovery**: Added `GET /api/models?provider=gemini` with dynamic UI chip selection in `SettingsModal.tsx`.

### 🔌 Universal Multi-Provider Pipeline
- **Zero-Setup Google Translate RPC**: High-speed, zero-cost Google RPC translation out of the box with Android Translate user-agent emulation and smart segment packing.
- **Live Connection Test**: Added `POST /api/test-provider` endpoint with live latency benchmarks and mathematical token invariance verification (`<b0></b0>`).
- **Zero-Dependency Native REST LLM Fallback**: Added standard-library `urllib.request` fallback in `OpenAITranslationProvider` and `GeminiTranslationProvider`, allowing cloud translation without requiring `pip install openai` or external SDKs.
- **Extended Language Support**: Added full support for Chinese Traditional (`zh-TW`), Chinese Simplified (`zh-CN`), Portuguese (`pt`), Italian (`it`), Dutch (`nl`), Polish (`pl`), Turkish (`tr`), Arabic (`ar`), and Thai (`th`).

### 🧮 Two-Pass Selective Prose Erasure & Formula Pinning
- **Selective Vector Preservation**: Only verified natural-language prose spans are redacted from the PDF stream; vector equations, diagrams, table rules, and curly braces remain 100% untouched.
- **Sub-Line Formula Pinning (`vflag`)**: Mathematical fonts (`Symbol`, `MT Extra`, TeX) and sub/superscript geometries ($\Delta y \ge 1.5\text{pt}$) are frozen as `MathObstacle`s with zero hardcoded word lists.
- **Anisotropic Font & Space Fitting**: Binary-search font scaling down to 64% condensation floor, guaranteeing lone words between formulas always fit without dropping lines.
- **Multi-Family Font Suite**: Bundled 21 TrueType font files in `layoutlingua/typesetting/assets/fonts/` (`DejaVuSans`, `DejaVuSerif`, `FreeSans`, `FreeSerif`, `DejaVuSansMono`) with bold/italic variants and CJK fallbacks (`Noto Sans SC/TC/JP/KR`).

### 🩹 PyMuPDF 2.0 Compatibility & Defensive Hardening
- **PyMuPDF 2.0 Layout Gating Bypass**: Resolved `AssertionError: 0 != 1` in `TableGridValidator` by setting `use_layout=False` with safe fallback, ensuring strict physical vector stroke corroboration ($\ge 90\%$ coverage) across PyMuPDF 1.25 through 2.0+.
- **Intra-Word Font Fallback Coalescing**: Solved mid-word font splits in non-Latin scripts, coalescing fragmented spans cleanly into single prose tokens.
- **VNI Spaced Composite Normalization**: Re-ordered VNI decoding replacements so circumflex and breve rules execute before acute/grave, preventing corruption of accented characters.
- **TOC Leader & Vector Pill Protection**: Preserved dot leaders during glossary replacement, prevented false skipping of headings, and added parent-background clearance for borderless code pills.

### 🧪 Automated Quality & Test Coverage
- **276 Automated Tests Passing (100%)**: Validated across all test suites on Ubuntu Linux, macOS, and Windows runners in continuous integration.
- **100% Fluent English Documentation**: Harmonized all documentation files (`docs/*.md`, `README.md`) into fluent English with rich Markdown badges and stickers.

---

## [1.1.0] — 2026-09-05

### 🚀 Added
- **Canonical Semantic Document IR (`pdf2zh/ir.py`)**: 3-stage intermediate representation (`DocumentIR`, `PageIR`, `ParagraphIR`, `TableIR`, `CellIR`, `FormulaIR`) conforming to modern Document AI standards.
- **Layout-Aware Reading Order Engine**: Vertical whitespace gutter detection and topological sorting over DAG spatial graphs, eliminating multi-column text leakage.
- **Structure-Aware Table Engine**: `TableGrid` and `TableCell` models with numerical, measurement, uncertainty (`±`), and currency protection.
- **Session Checkpoint Manager**: Atomic disk checkpointing (`.checkpoint.json`) enabling zero-loss resumption for large documents.
- **Enhanced Formula Recovery**: Heuristic normalization for MT formatting artifacts and automatic closure recovery for swallowed style tags.
- **Adaptive Typesetting Solver**: Multi-variable constraint optimization balancing font scaling, line height, and word spacing with Vietnamese diacritic headroom (`1.8pt`).
- **Global Terminology Memory**: Custom JSON/CSV glossary management with longest-match priority.
- **Bulk Translation Batcher**: Reduced network round-trips by up to 70% with mathematical segment isolation.

---

## [1.0.0] — 2026-09-05

### 🚀 Added
- Initial public release of LayoutLingua.
- Core PDF layout parser and bounding box extraction.
- MuPDF vector rendering pipeline.
- Cross-platform CLI with JSON-RPC stdio IPC.
