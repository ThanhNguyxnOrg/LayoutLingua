# REST API Reference (`docs/API_REFERENCE.md`)

<p>
  <img src="https://img.shields.io/badge/API-REST%20%2B%20Binary%20Streams-0D9488?style=for-the-badge" alt="REST API" />
  <img src="https://img.shields.io/badge/Port-3000-0284C7?style=for-the-badge" alt="Port 3000" />
</p>

All backend routes are served by `server.ts` on port `3000` under `/api/*`.

---

## 1. `GET /api/health`
Returns engine health and version metadata.

```json
{
  "status": "ok",
  "version": "2.0.0",
  "engine": "LayoutLingua-MuPDF-VectorEngine"
}
```

---

## 2. `POST /api/upload`
Uploads a raw PDF binary stream, extracts page dimensions and word counts via MuPDF, detects source language via `franc-min`, and persists the session to `.cache/sessions/<sha256>/`.

- **Headers**:
  - `Content-Type: application/pdf`
  - `X-Filename: <URI-encoded filename>`
  - `X-Doc-Id: <optional client session ID>`
- **Response (`200 OK`)**:
```json
{
  "id": "3151691ef4f9",
  "name": "Sotaytoanhoc.pdf",
  "size": 2841920,
  "page_count": 96,
  "word_count": 18420,
  "detected_lang": "vi",
  "is_scanned": false,
  "scan_warning": "",
  "pages": [{ "page_number": 1, "width": 420, "height": 595 }]
}
```

---

## 3. `GET /api/session-status`
Verifies whether a document session exists in memory or in `.cache/sessions/` on disk.

- **Query Parameters**: `id` (required), `name` (optional filename fallback)
- **Response (`200 OK`)**:
```json
{
  "exists": true,
  "id": "3151691ef4f9",
  "name": "Sotaytoanhoc.pdf",
  "size": 2841920,
  "page_count": 96,
  "detected_lang": "vi",
  "target_lang": "en",
  "status": "translated"
}
```

---

## 4. `GET /api/page-preview`
Renders a 150 DPI PNG image of a specific PDF page (`format=png`) or returns interactive layout block & hyperlink metadata (`format=meta`).

- **Query Parameters**:
  - `id`: Document session ID
  - `page`: 1-indexed page number
  - `type`: `source` | `translated`
  - `format`: `png` (default) | `meta`

---

## 5. `POST /api/translate`
Starts an asynchronous layout-preserving translation job across the selected page range.

- **Request Body**:
```json
{
  "doc_id": "3151691ef4f9",
  "source_lang": "vi",
  "target_lang": "en",
  "page_range": "1-25",
  "custom_glossary": "viên phân = circular segment",
  "provider": "google",
  "min_font_shrink": 0.65
}
```

---

## 6. `GET /api/progress`
Polls real-time translation progress, speed, ETA, and per-page visual integrity (`completed_pages`, `page_statuses`, `page_block_counts`, `issues`).

---

## 7. `GET /api/download`
Exports the translated document in three formats:
- **Monolingual Translated PDF**: `/api/download?id=<id>&format=pdf&mode=mono&scope=all|translated_only`
- **Bilingual Interleaved PDF**: `/api/download?id=<id>&format=pdf&mode=bilingual&scope=all|translated_only`
- **Structured Markdown**: `/api/download?id=<id>&format=md`
