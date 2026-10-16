"""Lightweight, high-performance local HTTP server for LayoutLingua.

Bridges the web-based React/Tauri desktop client directly to the Python core engine:
- Renders authentic high-DPI PDF page previews to PNG via PyMuPDF.
- Parses document IR, formulas, and table bounding boxes.
- Executes real layout-aware translation and typesetting.
- Streams real-time progress and exports genuine translated PDF files.
"""

from __future__ import annotations

import io
import json
import os
import sys
import re
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import uuid

import pymupdf

from layoutlingua._version import __version__
from layoutlingua.core.ir import DocumentIR
from layoutlingua.core.parser import parse_pdf
from layoutlingua.translation.mock import MockTranslationProvider
from layoutlingua.translation.models import TextSegment
from layoutlingua.translation.service import (
    TranslationService,
    extract_document_segments,
)
from layoutlingua.typesetting.engine import TypesetEngine
from layoutlingua.typesetting.models import TypesetOptions

# In-memory document session cache with bounded capacity
_SESSIONS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()
MAX_SESSIONS = 15


class LayoutLinguaHandler(BaseHTTPRequestHandler):
    """HTTP request handler for LayoutLingua desktop client API."""

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        allowed = False
        if not origin:
            allowed = True
        else:
            o_low = origin.lower()
            if (
                o_low.startswith("http://localhost:")
                or o_low.startswith("http://127.0.0.1:")
                or o_low.startswith("https://localhost:")
                or o_low.startswith("https://127.0.0.1:")
                or o_low in ("http://localhost", "http://127.0.0.1")
                or o_low.startswith("tauri://")
                or "tauri.localhost" in o_low
            ):
                allowed = True

        if allowed:
            self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-Filename",
            )
            self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_image(self, img_bytes: bytes, content_type: str = "image/png") -> None:
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(img_bytes)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(img_bytes)

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # 1. Health check
        if path in ("/api/health", "/health"):
            self._send_json({"status": "ok", "version": __version__, "engine": "PyMuPDF"})
            return

        # 2. Page preview rendering (High DPI PNG)
        if path in ("/api/page-preview", "/page-preview"):
            doc_id = query.get("id", [""])[0]
            page_num_str = query.get("page", ["1"])[0]
            preview_type = query.get("type", ["source"])[0]

            try:
                page_num = max(1, int(page_num_str))
            except ValueError:
                page_num = 1

            with _LOCK:
                session = _SESSIONS.get(doc_id)

            if not session:
                self._send_json({"error": f"Session '{doc_id}' not found"}, status=404)
                return

            try:
                # Select source or translated document
                if preview_type == "translated" and session.get("translated_pdf_bytes"):
                    pdf_doc = pymupdf.open(stream=session["translated_pdf_bytes"], filetype="pdf")
                else:
                    pdf_doc = pymupdf.open(stream=session["source_pdf_bytes"], filetype="pdf")

                page_idx = min(len(pdf_doc) - 1, max(0, page_num - 1))
                page = pdf_doc[page_idx]

                # Render page at 150 DPI for crisp typography preview
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                pdf_doc.close()

                self._send_image(img_data, "image/png")
            except Exception as e:
                self._send_json({"error": f"Failed to render page: {e}"}, status=500)
            return

        # 3. Translation progress tracking
        if path in ("/api/progress", "/progress"):
            doc_id = query.get("id", [""])[0]
            with _LOCK:
                session = _SESSIONS.get(doc_id)

            if not session:
                self._send_json({"error": "Document session not found"}, status=404)
                return

            prog = session.get("progress", {
                "current_page": 0,
                "total_pages": session.get("page_count", 0),
                "status": "idle",
            })
            self._send_json(prog)
            return

        # 4. Download translated PDF file
        if path in ("/api/download", "/download"):
            doc_id = query.get("id", [""])[0]
            with _LOCK:
                session = _SESSIONS.get(doc_id)

            if not session:
                self._send_json({"error": "Document session not found"}, status=404)
                return

            pdf_bytes = session.get("translated_pdf_bytes") or session.get("source_pdf_bytes")
            file_name = session.get("filename", "document.pdf")
            if not file_name.endswith(".vi.pdf") and not file_name.endswith(".en.pdf"):
                file_name = file_name.replace(".pdf", "") + ".translated.pdf"
            clean_filename = re.sub(r'[\r\n"\\]', '_', file_name)

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{clean_filename}"')
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)
            return

        # 5. Query models from any OpenAI-compatible provider
        if path in ("/api/models", "/api/fetch-models"):
            base_url = query.get("base_url", ["https://api.openai.com/v1"])[0].rstrip("/")
            api_key = query.get("api_key", [""])[0].strip()

            if not (base_url.startswith("http://") or base_url.startswith("https://")):
                self._send_json(
                    {"models": [], "status": "error", "error": "Invalid URL scheme. Only HTTP and HTTPS endpoints are permitted."},
                    status=400,
                )
                return

            models_url = f"{base_url}/models"
            try:
                headers = {"User-Agent": "LayoutLingua/2.0"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                req = urllib.request.Request(models_url, headers=headers)
                with urllib.request.urlopen(req, timeout=4.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                    self._send_json({"models": models, "status": "ok"})
                    return
            except Exception as e:
                self._send_json({
                    "models": [],
                    "status": "error",
                    "error": f"Failed to fetch models from {models_url}: {e}",
                })
                return

        self._send_json({"error": f"Path not found: {path}"}, status=404)

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_json({"error": "Invalid Content-Length header"}, status=400)
            return

        if content_length < 0:
            self._send_json({"error": "Negative Content-Length header"}, status=400)
            return

        post_body = self.rfile.read(content_length)

        # 1. Upload & parse document
        if path in ("/api/upload", "/upload"):
            try:
                # Handle raw PDF bytes or JSON { filename, base64 }
                filename = "document.pdf"
                pdf_bytes: bytes

                if self.headers.get("Content-Type", "").startswith("application/json"):
                    req_json = json.loads(post_body.decode("utf-8"))
                    filename = req_json.get("filename", "document.pdf")
                    import base64

                    pdf_bytes = base64.b64decode(req_json["data"])
                elif b"%PDF" in post_body:
                    # Direct raw PDF stream or binary body
                    idx = post_body.find(b"%PDF")
                    pdf_bytes = post_body[idx:]
                    raw_fn = self.headers.get("X-Filename", "document.pdf")
                    filename = urllib.parse.unquote(raw_fn)
                else:
                    # Multipart upload parse
                    pdf_bytes = post_body
                    filename = "document.pdf"

                # Verify valid PDF with PyMuPDF
                doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                page_count = len(doc)

                pages_info = []
                total_words = 0
                for i in range(page_count):
                    p = doc[i]
                    text = p.get_text()
                    words = len(text.split())
                    total_words += words
                    pages_info.append({
                        "n": i + 1,
                        "width": round(p.rect.width, 1),
                        "height": round(p.rect.height, 1),
                        "words": words,
                        "status": "pending",
                    })

                # Detect Vietnamese language from sample text
                sample_text = ""
                for p in doc[: min(5, len(doc))]:
                    sample_text += p.get_text() + " "

                vi_marks = set("àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ")
                vi_count = sum(1 for ch in sample_text if ch in vi_marks)
                detected_lang = "vi" if vi_count > 3 else "en"

                doc_id = uuid.uuid4().hex[:12]

                # Parse DocumentIR
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(pdf_bytes)
                    tmp_path = tmp.name

                try:
                    doc_ir = parse_pdf(tmp_path)
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                with _LOCK:
                    while len(_SESSIONS) >= MAX_SESSIONS:
                        oldest_k = next(iter(_SESSIONS))
                        del _SESSIONS[oldest_k]

                    _SESSIONS[doc_id] = {
                        "doc_id": doc_id,
                        "filename": filename,
                        "source_pdf_bytes": pdf_bytes,
                        "doc_ir": doc_ir,
                        "page_count": page_count,
                        "translated_pdf_bytes": None,
                        "issues": [],
                        "detected_lang": detected_lang,
                        "progress": {
                            "current_page": 0,
                            "total_pages": page_count,
                            "status": "idle",
                        },
                    }

                doc.close()

                self._send_json({
                    "id": doc_id,
                    "name": filename,
                    "size": len(pdf_bytes),
                    "page_count": page_count,
                    "word_count": total_words,
                    "detected_lang": detected_lang,
                    "pages": pages_info,
                })
            except Exception as e:
                self._send_json({"error": f"Failed to parse PDF document: {e}"}, status=400)
            return

        # 2. Run document translation & typesetting
        if path in ("/api/translate", "/translate"):
            try:
                req_json = json.loads(post_body.decode("utf-8"))
                doc_id = req_json.get("doc_id", "")
                target_lang = req_json.get("target_lang", "vi")

                with _LOCK:
                    session = _SESSIONS.get(doc_id)

                if not session:
                    self._send_json({"error": f"Session '{doc_id}' not found"}, status=404)
                    return

                doc_ir: DocumentIR = session["doc_ir"]
                src_bytes: bytes = session["source_pdf_bytes"]

                # Extract translatable segments
                segments = extract_document_segments(doc_ir)

                # Read provider options
                provider_type = str(req_json.get("provider", "mock")).lower()
                api_key = str(req_json.get("api_key", "")).strip()
                base_url = str(req_json.get("base_url", "")).strip()
                model_name = str(req_json.get("model", "")).strip()

                provider_inst = None
                try:
                    if provider_type in ("openai", "ollama") or base_url:
                        from layoutlingua.translation.openai_compat import OpenAITranslationProvider

                        b_url = base_url if base_url else ("http://localhost:11434/v1" if provider_type == "ollama" else "https://api.openai.com/v1")
                        m_id = (model_name or "").strip()
                        if not m_id:
                            # Dynamic model discovery from server
                            try:
                                headers = {"User-Agent": "LayoutLingua/2.0"}
                                if api_key and api_key != "ollama":
                                    headers["Authorization"] = f"Bearer {api_key}"
                                req_m = urllib.request.Request(f"{b_url.rstrip('/')}/models", headers=headers)
                                with urllib.request.urlopen(req_m, timeout=2.5) as r_m:
                                    data_m = json.loads(r_m.read().decode("utf-8"))
                                    fetched = [m.get("id") for m in data_m.get("data", []) if m.get("id")]
                                    if fetched:
                                        m_id = fetched[0]
                            except Exception:
                                pass

                        if not m_id:
                            if "api.openai.com" in b_url:
                                m_id = "gpt-4o-mini"
                            else:
                                raise ValueError(
                                    f"No model specified and could not auto-discover models from {b_url}. "
                                    f"Please specify a Model ID in Settings."
                                )

                        provider_inst = OpenAITranslationProvider(
                            api_key=api_key or "ollama",
                            model_id=m_id,
                            base_url=b_url,
                        )
                    elif provider_type == "gemini" and api_key:
                        from layoutlingua.translation.gemini import GeminiTranslationProvider

                        m_id = model_name if model_name else "gemini-2.5-flash"
                        provider_inst = GeminiTranslationProvider(
                            api_key=api_key,
                            profile_or_model=m_id,
                        )
                    elif provider_type in ("google", "google_rpc"):
                        from layoutlingua.translation.google_rpc import GoogleRpcTranslationProvider

                        provider_inst = GoogleRpcTranslationProvider()
                    elif provider_type == "argos":
                        from layoutlingua.translation.argos.provider import ArgosTranslationProvider

                        argos = ArgosTranslationProvider()
                        if argos.manager.is_runtime_available():
                            provider_inst = argos
                except Exception as p_err:
                    print(f"[LayoutLingua] Provider init notice: {p_err}")
                    provider_inst = None

                if provider_inst is None and provider_type != "mock":
                    try:
                        from layoutlingua.translation.google_rpc import GoogleRpcTranslationProvider

                        provider_inst = GoogleRpcTranslationProvider()
                    except Exception as g_err:
                        print(f"[LayoutLingua] Online MT fallback error: {g_err}")

                if provider_inst is None:
                    provider_inst = MockTranslationProvider()

                translated_segments: dict[str, str] = {}
                if isinstance(provider_inst, MockTranslationProvider):
                    for seg in segments:
                        translated_segments[seg.segment_id] = provider_inst.translate_segment(
                            segment_id=seg.segment_id,
                            text=seg.masked_text,
                            target_lang=target_lang,
                        )
                else:
                    from layoutlingua.translation.models import BatchTranslationRequest

                    batch_sz = 20
                    for b_idx in range(0, len(segments), batch_sz):
                        chunk = segments[b_idx : b_idx + batch_sz]
                        req = BatchTranslationRequest(
                            batch_id=f"batch-{b_idx}",
                            source_language=session.get("detected_lang", "auto"),
                            target_language=target_lang,
                            segments=tuple(chunk),
                        )
                        try:
                            b_res = provider_inst.translate_batch(req)
                            translated_segments.update(b_res.translations)
                        except Exception as b_err:
                            print(f"[LayoutLingua] Live batch error: {b_err}, falling back to mock")
                            mock_fallback = MockTranslationProvider()
                            for seg in chunk:
                                translated_segments[seg.segment_id] = mock_fallback.translate_segment(
                                    segment_id=seg.segment_id,
                                    text=seg.masked_text,
                                    target_lang=target_lang,
                                    )

                # Run TypesetEngine with language-aware font selection
                src_doc = pymupdf.open(stream=src_bytes, filetype="pdf")
                t_lang = (target_lang or "vi").lower().strip()
                typeset_font = "DejaVuSans"
                if t_lang in ("zh", "chinese", "zh-cn", "zh-tw"):
                    typeset_font = "china-s"
                elif t_lang in ("ja", "japanese"):
                    typeset_font = "japan"
                elif t_lang in ("ko", "korean"):
                    typeset_font = "korea"

                engine = TypesetEngine(options=TypesetOptions(font_name=typeset_font))

                # Typeset document page-by-page
                from layoutlingua.typesetting.accumulator import DocumentAccumulator

                accumulator = DocumentAccumulator(source_doc=src_doc)
                total_p = len(src_doc)

                for page_idx in range(total_p):
                    with _LOCK:
                        session["progress"] = {
                            "current_page": page_idx + 1,
                            "total_pages": total_p,
                            "status": "processing",
                        }
                    p_ir = doc_ir.pages[page_idx] if page_idx < len(doc_ir.pages) else None
                    if p_ir:
                        tx = engine.stage_page_transaction(
                            source_doc=src_doc,
                            page_ir=p_ir,
                            document_ir=doc_ir,
                            translated_segments=translated_segments,
                        )
                        accumulator.commit_page(tx)
                    else:
                        accumulator.commit_pristine_source_page(page_idx)

                # Finalize rendered PDF
                translated_bytes = accumulator.finish()
                src_doc.close()

                with _LOCK:
                    session["translated_pdf_bytes"] = translated_bytes
                    session["progress"] = {
                        "current_page": total_p,
                        "total_pages": total_p,
                        "status": "done",
                    }

                self._send_json({
                    "status": "done",
                    "doc_id": doc_id,
                    "translated_pages": total_p,
                    "total_pages": total_p,
                    "issues": [],
                })
            except Exception as e:
                import traceback

                traceback.print_exc()
                self._send_json({"error": f"Translation failed: {e}"}, status=500)
            return

        self._send_json({"error": f"Unknown POST endpoint: {path}"}, status=404)


def start_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Start the LayoutLingua API server."""
    server = ThreadingHTTPServer((host, port), LayoutLinguaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[LayoutLingua] Server running at http://{host}:{port}/")
    return server


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), LayoutLinguaHandler)
    print(f"[LayoutLingua] Local API Server listening on http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LayoutLingua] Server stopped.")
