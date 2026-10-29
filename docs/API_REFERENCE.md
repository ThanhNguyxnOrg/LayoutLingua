# 🔌 REST API Reference (`docs/API_REFERENCE.md`)

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
  <img src="https://img.shields.io/badge/🔌_API-REST_+_Binary_Streams-0D9488?style=for-the-badge" alt="REST API" />
  <img src="https://img.shields.io/badge/🖥️_Engine-Python_::8765-FFC131?style=for-the-badge" alt="Engine" />
  <img src="https://img.shields.io/badge/🐍_Desktop_Engine-:8765_(server.py)-FFC131?style=for-the-badge" alt="Python Engine" />
  <img src="https://img.shields.io/badge/✅_Contract-100%25_Parity-22C55E?style=for-the-badge" alt="Parity" />
</p>

All backend routes are served under `/api/*` by the LayoutLingua engine:

- 🖥️ **Engine**: `layoutlingua/server.py` (Python + PyMuPDF vector core) on `http://127.0.0.1:8765` — the single backend serving the React desktop UI.

> ✅ Every endpoint below is the live contract of that engine.

---

## 🔁 Session Lifecycle

### 1. `GET /api/health`
Returns engine health and version metadata.

```json
{ "status": "ok", "version": "2.1.0", "engine": "PyMuPDF" }
```

### 2. `POST /api/upload`
Uploads a raw PDF binary stream, extracts page dimensions/word counts via MuPDF, detects the source language via `franc-min`, and persists the session to disk.

- **Headers**:
  - `Content-Type: application/pdf`
  - `X-Filename: <URI-encoded filename>`
  - `X-Doc-Id: <optional client session id>` — honored as the session id; otherwise a 12-char SHA-256 **content hash** is used
- 🔁 **Dedupe**: re-uploading the same content (same size + page count) returns the existing persisted session instead of re-parsing
- **Response (`200 OK`)**:
```json
{
  "id": "a3f8c2d1e4b6",
  "name": "textbook.pdf",
  "size": 2841920,
  "page_count": 96,
  "word_count": 17368,
  "detected_lang": "vi",
  "is_scanned": false,
  "scan_warning": "",
  "pages": [{ "page_number": 1, "width": 420.96, "height": 595.44 }]
}
```

### 2b. `GET /api/recent-sessions`
Discovers and enumerates sessions persisted in operating system cache directories (`source.pdf`, `meta.json`, `translated.pdf`), enabling desktop windows to discover and rehydrate previous sessions across restarts.

- **Query Parameters**: None
- **Response (`200 OK`)**:
```json
{
  "sessions": [
    {
      "id": "a3f8c2d1e4b6",
      "name": "textbook.pdf",
      "pages": 42,
      "size": 1048576,
      "status": "translated",
      "detectedLang": "vi",
      "targetLang": "en",
      "mtime": 1729864200
    }
  ]
}
```

### 3. `GET /api/session-status`
Checks whether a document session exists in memory or in the on-disk cache (`id` **or** `name` match).

- **Query**: `id` (optional), `name` (optional filename fallback)
- **Response (`200 OK`)**:
```json
{
  "exists": true,
  "id": "a3f8c2d1e4b6",
  "name": "textbook.pdf",
  "size": 2841920,
  "page_count": 96,
  "detected_lang": "vi",
  "target_lang": "en",
  "status": "translated" | "pending"
}
```

---

## 🖼️ Preview & Telemetry

### 4. `GET /api/page-preview`
Renders a 150 DPI PNG of one page, or returns interactive layout block metadata.

- **Query**: `id`, `page` (1-indexed), `type`: `source` | `translated`, `format`: `png` (default) | `meta`
- **`format=meta` response** — block bounding boxes powering the hover inspector & hyperlink overlays:
```json
{
  "page": 78,
  "pageW": 420.96,
  "pageH": 595.44,
  "blocks": [
    {
      "id": "p78_b6",
      "kind": "prose | toc | heading | math",
      "bbox": { "x": 54.0, "y": 231.1, "w": 10.1, "h": 13.3 },
      "pageW": 420.96,
      "pageH": 595.44,
      "sourceText": "từ",
      "translatedText": "word",
      "fontScale": 0.54,
      "preserved": false,
      "uri": "https://… (optional, hyperlink blocks only)"
    }
  ]
}
```

### 5. `GET /api/progress`
Polls real-time translation progress, speed, ETA and per-page integrity.

```json
{
  "stage_index": 3,
  "stage_name": "Fitting text to layout",
  "current_page": 25,
  "total_pages": 96,
  "overall_pct": 26,
  "status": "processing | done | idle | error",
  "speed": 0.3,
  "eta_seconds": 93,
  "subtitle": "Page 25 (25 of 96)",
  "message": "Typeset Page 25: 16 prose blocks translated, 10 formula regions preserved.",
  "integrity": {
    "blocks_translated": 921,
    "needs_review": 0,
    "preserved_pages": 0,
    "page_statuses": { "1": "ok" },
    "page_block_counts": { "1": 12 },
    "completed_pages": { "1": true },
    "issues": []
  }
}
```

---

## 🌍 Translation

### 6. `POST /api/translate`
Starts an asynchronous layout-preserving translation job across the selected page range. Idempotent: a second call while a job is running returns `{ "status": "processing" }`.

- **Request Body**:
```json
{
  "doc_id": "a3f8c2d1e4b6",
  "source_lang": "vi",
  "target_lang": "en",
  "page_range": "1-25",
  "custom_glossary": "viên phân = circular segment",
  "provider": "google",
  "gemini_key": "optional",
  "openai_key": "optional",
  "min_font_shrink": 0.65
}
```
- **Response**: `{ "status": "processing", "doc_id": "…", "total_pages": 25, "message": "Translation job started" }`

### 7. `POST /api/cancel`
Cancels the active job. ♻️ Pages already translated are **kept** — the partial output is committed to the session so it can be previewed, exported, and resumed.

- **Body**: `{ "doc_id": "a3f8c2d1e4b6" }`
- **Response**: `{ "status": "cancelled" }`

---

## 📤 Export & Filesystem

### 8. `GET /api/download`
Exports the translated document:

| Mode | Query | Output |
|:---|:---|:---|
| 📄 Monolingual PDF | `?id=<id>&format=pdf&mode=mono&scope=all\|translated_only` | Translated PDF |
| 📖 Bilingual interleaved | `?id=<id>&format=pdf&mode=bilingual&scope=…` | Original ↔ Translated page pairs (TOC page numbers doubled) |
| 📝 Markdown | `?id=<id>&format=md` | Structured Markdown notes |

### 9. `POST /api/save`
Writes the export directly to the user-chosen filesystem directory (resolves `~` and Windows OneDrive folder redirection such as `~/OneDrive/Desktop`).

- **Body**: `{ "doc_id", "filename", "directory", "mode": "mono|bilingual", "format": "pdf|md", "scope": "all|translated_only" }`
- **Response**: `{ "status": "ok", "saved_path": "C:\Users\…\textbook.en.pdf", "bytes": 1522432 }` — a real, verified path (typical full-document export completes in < 0.3s)

### 10. `GET /api/system-folders` · `GET /api/pick-folder` · `POST /api/open-folder`
Desktop folder helpers: known destination folders (`Desktop`, `Downloads`, `Documents`), a folder picker passthrough, and an "Open in File Explorer" action for a saved path.

---

## ⚙️ Providers

### 11. `GET /api/models`
Discovers models from any OpenAI-compatible endpoint (`/v1/models`).

- **Query**: `base_url`, optional `api_key`
- **Response**: `{ "models": ["groq/llama-3.3-70b", …] }`

---

## 🧭 Runtime Notes

| Capability | Implementation |
|:---|:---|
| Upload + content-hash dedupe (`X-Doc-Id`) | ✅ OS cache dir sessions |
| `session-status` disk recovery | ✅ restart-proof (`source.pdf` / `translated.pdf` / `meta.json`) |
| Live progress + integrity telemetry | ✅ per-page stages, ETA, issues |
| `cancel` keeping translated pages | ✅ partial output committed |
| `page-preview?format=meta` block metadata | ✅ DocumentIR blocks + `#page=N` navigation uris |
| Provider honesty | ✅ missing key/runtime stops the job explicitly |
| Bilingual interleaved + Markdown export | ✅ |
| Segment cache | ✅ SQLite persistent store |

