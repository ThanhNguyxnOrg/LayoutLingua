# Changelog

All notable changes to the LayoutLingua project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-10-17

### Added
- **Cluster-Level Formula & Layout Clearance (pdf2zh & BabelDOC Pattern)**:
  - Replaced coarse line-level union bounding boxes with cluster-level span grouping in `compute_tight_line_clearance_regions`.
  - Prevents bounding boxes from straddling across mathematical grouping braces (Page 7) or fraction division lines and denominators (Pages 6 & 17).
- **Non-Contracting Dynamic Layout Box Expansion**:
  - Fixed `compute_expanded_layout_box` in `TypesetEngine` to never contract below original block width (`x1`) when obstacle regions appear at paragraph tails (e.g. Page 11).
  - Constrained obstacle detection exclusively to the right of the block (`ox0 >= x1 - 5.0`).
- **Elastic Single-Line Math Label Scaling**:
  - Lowered minimum font floor for single-line math labels to 0.50x (5.0pt) in `TextFitTester`, allowing labels like Page 13 to fit horizontally without catastrophic vertical overflow.
- **TOC & Sibling List Font Harmonization**:
  - Harmonizes font sizes across sibling Table of Contents entries and numbered list items to prevent ragged font disparity.
  - Dynamically adapts dot leaders (`.....`) using the LaTeX `\dotfill` algorithm to ensure page numbers align cleanly to the right margin.
- **True Bold Font Typography & Heading Casing Preservation**:
  - Bundled version-pinned `DejaVuSans-Bold.ttf` asset with complete Unicode glyph coverage for mathematical symbols and composite Vietnamese diacritics.
  - Implemented `resolve_block_font` in `TypesetEngine` to dynamically map bold spans to actual bold font files.
  - Automatically preserves uppercase heading casing (`V. LƯỢNG GIÁC` -> `V. TRIGONOMETRY`) to maintain document hierarchy.
- **One-Click Quality Diagnostic Export ("Copy log")**:
  - Added dedicated copy button in the Quality checks tab with copy-to-clipboard state feedback to export complete structured warning logs for LLM triage.
- **Dual Number Page Range Selector**:
  - Direct numeric page inputs ("From page" and "To page") with automatic boundary clamping and bidirectional validation.
- **Autonomous CI/CD & Core Team Triage Pipeline**:
  - Fixed multi-platform CI test suite (`test.yml`) running 245 unit and integration tests across Ubuntu, Windows, and macOS with `pytest`.
  - Standardized automated merge and triage workflow (`auto-merge.yml`) powered by `ThanhNguyxnAgent` with 100% English messaging.
  - Automatic tagging and review assignment to `@ThanhNguyxnOrg/core` (`@RealThanhNguyxn`, `@ThanhNguyxn07`) for critical PRs.

### Added
- **Native Desktop Application (Tauri 2.0 + React 19)**:
  - High-performance, cross-platform desktop UI supporting Windows, macOS, and Linux.
  - Automatic zero-window Python backend lifecycle management (`CREATE_NO_WINDOW` auto-spawn on launch, graceful termination on exit).
  - Standalone single-executable distribution (`LayoutLingua.exe`) and Windows NSIS installer (`LayoutLingua_Setup_v2.0.0.exe`).
- **Zero-Setup Google Translate RPC Engine**:
  - Built-in machine translation engine (`GoogleRpcTranslationProvider`) available out of the box with zero API keys or complex environment setup.
  - Full support for English ↔ Vietnamese with sentence boundary tokenization and rate-limit handling.
  - Flexible provider switching: Google RPC, Google Gemini 2.5, OpenAI-compatible APIs, local Ollama, and offline Argos Translate.
- **Persistent Document History & Recents**:
  - LocalStorage-backed document history management (`history.ts`).
  - Real-time status tracking (`Translated`, `Needs review`, `Failed`, `Pending`) updating dynamically upon translation completion.
  - Clean empty states and persistent deletion without mock data contamination.
- **Dual-View & Interactive Layout Inspection**:
  - Side-by-side synchronized view between original PDF and translated PDF.
  - Interactive Alpha Blend Overlay slider (0% to 100%) to visually inspect layout deviations, baseline shifts, and font line-height fidelity.
  - High-resolution vector preview rasterization via PyMuPDF backend (`/api/page-preview`).
- **Formula & Mathematical Typography Shielding**:
  - Computer Modern (`CM[^RT]`) and mathematical font detection with spatial bounding-box isolation.
  - Invariant token shielding (`«MATH_0»`) preventing neural translation models from corrupting subscripts, superscripts, Greek characters, and integrals.
  - Cambria Math and DejaVu Sans TrueType font embedding with `Identity-H` ToUnicode mapping for crisp math rendering and full Vietnamese diacritics.
- **Adaptive Typesetting & Layout Preservation**:
  - Dynamic font downscaling with strict minimum line floor (7.5pt) to accommodate ~25–35% text length expansion in Vietnamese/German without overflow.
  - Multi-page transactional staging (`DocumentAccumulator`) with automatic rollback of corrupted pages to pristine source pages.
- **Universal Multi-Language Font Preservation**:
  - Language-aware font dispatch: automatically routes CJK targets (Chinese, Japanese, Korean) to PyMuPDF's built-in fonts (`china-s`, `china-t`, `japan`, `korea`) and Latin/Cyrillic/Vietnamese targets to version-pinned `DejaVuSans.ttf`.
  - Guarantees zero mojibake, zero missing box glyphs, and zero character corruption regardless of source/target language pairing.
- **Universal OpenAI-Compatible Model Discovery & Cloud/Local LLM Unification**:
  - Unified all cloud and local LLMs (OpenAI, Claude via OpenRouter, DeepSeek, Groq, Ollama, LM Studio, vLLM) into a single, standardized **OpenAI-Compatible** provider (`OpenAITranslationProvider`).
  - Removed brittle domain substring guessing; model resolution now prioritizes explicit user input and dynamically queries `{base_url}/models` to discover installed models automatically.
  - Added live model auto-discovery via `🔍 Fetch Available Models` button with datalist suggestions and selectable model chips.
  - Streamlined provider configuration across settings and workspace into 4 clean, synchronized options: Google Translate RPC (Zero Setup), OpenAI-Compatible (Universal LLM), Google AI Studio (Gemini), and Argos Translate (Offline).
  - Documented protocol analysis and open-source benchmarks in `docs/research_openai_compatible_and_local_llm_unification.md`.
- **Open-Source Architectural Research**:
  - In-depth comparative research documenting patterns from `pdf2zh`, `BabelDOC`, `MinerU`, and `BilingualBookMaker` in `docs/research_opensource_pdf_translation_patterns.md`.

### Fixed
- **UI Freeze on Multi-page Translation**:
  - Resolved critical React re-render cancellation deadlock in `Workspace.tsx` where progress state polling (`done`) unmounted in-flight HTTP translation requests.
  - Rebuilt translation lifecycle with single-flight action dispatching (`isTranslatingRef`) and decoupled progress polling.
- **Preview Mock Fallback**:
  - Fixed issue where in-progress translation fell back to rendering static mock papers ("Sparse Attention...") by enforcing real document session ID binding.
- **Language & UI Consistency**:
  - Standardized 100% of UI copy, error alerts, and help dialogs to English.
- **Repository Hygiene**:
  - Cleaned up obsolete scratch test artifacts, temporary font-test PDFs, and scratch PNGs.

### Changed
- Replaced mock-based UI components with real backend integration endpoints (`/api/upload`, `/api/translate`, `/api/progress`, `/api/page-preview`, `/api/download`).
- Verified full test suite stability: 165 / 165 tests passing.
