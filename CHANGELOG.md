# Changelog

All notable changes to the LayoutLingua project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-10-16

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
- **Universal OpenAI-Compatible Model Discovery & Auto-Inference**:
  - Renamed and generalized the provider to **OpenAI-Compatible** supporting any standard inference server (DeepSeek, Groq, OpenRouter, Qwen DashScope, Ollama, vLLM, LM Studio).
  - Added live model discovery endpoint (`/api/models` / `/api/fetch-models`) to scan hosted models from the server with 1 click.
  - Added one-click configuration presets for DeepSeek, Groq Cloud, OpenAI Official, OpenRouter, Ollama, and Qwen.
  - Zero-friction model resolution: if the user leaves Model ID empty, the backend automatically infers the correct model based on the Base URL domain (e.g., DeepSeek $\rightarrow$ `deepseek-chat`, Groq $\rightarrow$ `llama-3.3-70b-versatile`, OpenAI $\rightarrow$ `gpt-4o-mini`).
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
