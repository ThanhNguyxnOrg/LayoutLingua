# ADR 0001: Desktop Architecture with Tauri v2, React 19, and Python Sidecar IPC

## Status
Accepted

## Context
LayoutLingua requires a modern, responsive, high-performance desktop graphical user interface to visualize document translation, layout inspection, and quality metrics across Windows, macOS, and Linux. The user created a refined React 19 + TypeScript + Tailwind CSS v4 interface mockup and requested architectural selection for long-term scalability and efficiency.

The system consists of two primary operational components:
1. **Core Processing Engine**: Python-based headless document parsing, layout recognition, translation coordination, and typesetting engine (`layoutlingua`).
2. **Desktop Client**: Front-facing graphical interface for document loading, dual-pane side-by-side translation preview, page navigation, telemetry reporting, and export controls.

## Decision
1. **Framework Choice (Tauri v2 + React 19)**:
   - Use **Tauri v2** with a native Rust application shell and native webview (WebView2 on Windows, WebKitGTK on Linux, WKWebView on macOS).
   - Use **React 19, TypeScript, Vite, and Tailwind CSS v4** for the frontend application layer.
   - *Rationale*: Compared to Electron (~120–180 MB idle RAM and large bundle size), Tauri v2 provides ultra-low memory footprint (~30–45 MB RAM), instantaneous startup, native OS integration, and high security boundaries. It reuses 100% of the user's React components without requiring a complete rewrite into Python GUI frameworks.

2. **IPC Integration (JSON-RPC over Stdio Sidecar)**:
   - The desktop shell spawns the Python `layoutlingua` process as a background sidecar.
   - Communication is conducted via bidirectional JSON-RPC 2.0 messages over standard input/output (`stdin`/`stdout`).
   - *Rationale*: Zero-port network conflict, zero firewall / antivirus interception risks, strict process lifecycle coupling (if UI crashes, sidecar shuts down cleanly; if sidecar fails, UI detects and displays recovery).

3. **Repository Structure (Monorepo with Dedicated `desktop/` Directory)**:
   - All desktop UI code resides in `desktop/` (`desktop/src/`, `desktop/package.json`, `desktop/vite.config.ts`, `desktop/src-tauri/`).
   - Python core code remains isolated in `layoutlingua/` and `tests/`.
   - *Rationale*: Clean separation of concerns, independent CI dependency caches, zero pollution of Python repository root.

4. **Data Layer (Adapter Pattern: Mock Simulator & Real IPC)**:
   - The frontend implements a unified `DocumentService` interface.
   - `MockDocumentService`: Uses the user's crafted preview data for offline UI development and browser testing (`npm run dev`).
   - `TauriIpcDocumentService`: Bridges directly to the Rust backend and Python JSON-RPC engine in release desktop builds.
   - *Rationale*: Enables fast frontend iteration and visual design testing without running heavy machine-learning and translation backends, while guaranteeing seamless production binding.

## Consequences
- **Positive**:
  - Extremely fast UI with native performance and minimal memory footprint.
  - Complete isolation between Python environment and desktop UI.
  - Full reuse of the user's custom design system and layout components.
  - Completely sanitized from third-party vendor bloat (zero Figma artifacts).
- **Negative / Trade-offs**:
  - Packaging requires bundling the Python runtime / virtual environment sidecar for standalone installer generation.
