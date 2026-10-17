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
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import uuid

import pymupdf

from layoutlingua._version import __version__
from layoutlingua.core.ir import DocumentIR
from layoutlingua.core.parser import parse_pdf
from layoutlingua.translation.errors import RateLimitError
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

# Vision ONNX Layout Detector (lazy loaded if model exists)
_GLOBAL_DETECTOR: Any = None
_DETECTOR_TRIED: bool = False


def get_user_known_folders() -> dict[str, str]:
    """Retrieve verified absolute filesystem paths for Desktop, Downloads, and Documents."""
    folders: dict[str, str] = {}
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            )
            for k_name, reg_val in [
                ("Desktop", "Desktop"),
                ("Downloads", "{374DE290-123F-4565-9164-39C4925E467B}"),
                ("Documents", "Personal"),
            ]:
                try:
                    val, _ = winreg.QueryValueEx(key, reg_val)
                    p = os.path.normpath(os.path.expandvars(val))
                    if os.path.isdir(p):
                        folders[k_name] = p
                except Exception:
                    pass
        except Exception:
            pass

    home = os.path.expanduser("~")
    for k_name in ["Desktop", "Downloads", "Documents"]:
        if k_name not in folders:
            d = os.path.join(home, k_name)
            folders[k_name] = d if os.path.isdir(d) else home
    return folders


def get_layout_detector() -> Any:
    """Retrieve active ONNX vision layout detector if model file is present."""
    global _GLOBAL_DETECTOR, _DETECTOR_TRIED
    if not _DETECTOR_TRIED:
        _DETECTOR_TRIED = True
        model_env = os.environ.get("LAYOUTLINGUA_ONNX_MODEL", "models/doclayout_yolo.onnx")
        model_path = Path(model_env)
        if model_path.is_file():
            try:
                from layoutlingua.processing.vision import OnnxLayoutDetector

                det = OnnxLayoutDetector(model_path)
                if det.is_available():
                    _GLOBAL_DETECTOR = det
                    print(f"[LayoutLingua] Loaded ONNX vision layout detector from {model_path}")
            except Exception as exc:
                print(f"[LayoutLingua] Failed to initialize ONNX detector: {exc}")
    return _GLOBAL_DETECTOR


def _get_session_cache_dir() -> Path:
    """Return persistent on-disk cache directory for document sessions."""
    try:
        import platformdirs

        base_dir = Path(platformdirs.user_cache_dir("layoutlingua"))
    except Exception:
        base_dir = Path.home() / ".layoutlingua" / "cache"
    session_dir = base_dir / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _persist_session_to_disk(session: dict[str, Any]) -> None:
    """Save session PDF bytes and metadata to persistent disk cache."""
    try:
        doc_id = session.get("doc_id")
        if not doc_id:
            return
        target_dir = _get_session_cache_dir() / doc_id
        target_dir.mkdir(parents=True, exist_ok=True)

        src_bytes = session.get("source_pdf_bytes")
        if src_bytes:
            src_file = target_dir / "source.pdf"
            if not src_file.exists() or src_file.stat().st_size != len(src_bytes):
                src_file.write_bytes(src_bytes)

        trans_bytes = session.get("translated_pdf_bytes")
        if trans_bytes:
            (target_dir / "translated.pdf").write_bytes(trans_bytes)

        meta = {
            "doc_id": doc_id,
            "filename": session.get("filename", "document.pdf"),
            "page_count": session.get("page_count", 0),
            "detected_lang": session.get("detected_lang", "en"),
            "target_lang": session.get("target_lang", "vi"),
            "is_scanned": session.get("is_scanned", False),
            "scan_warning": session.get("scan_warning", ""),
            "has_translated": bool(trans_bytes),
            "selected_pages": session.get("selected_pages", []),
        }
        (target_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[LayoutLingua] Notice: Could not cache session to disk: {exc}")


def _get_or_recover_session(doc_id: str) -> Optional[dict[str, Any]]:
    """Retrieve session from RAM or transparently recover from persistent disk cache or local files."""
    if not doc_id:
        return None

    with _LOCK:
        if doc_id in _SESSIONS:
            return _SESSIONS[doc_id]

    cache_root = _get_session_cache_dir()

    # Strategy 1: Check direct disk cache folder: sessions / doc_id
    target_dir = cache_root / doc_id
    pdf_bytes: Optional[bytes] = None
    trans_bytes: Optional[bytes] = None
    meta_info: dict[str, Any] = {}

    if target_dir.is_dir() and (target_dir / "source.pdf").is_file():
        try:
            pdf_bytes = (target_dir / "source.pdf").read_bytes()
            if (target_dir / "translated.pdf").is_file():
                trans_bytes = (target_dir / "translated.pdf").read_bytes()
            if (target_dir / "meta.json").is_file():
                meta_info = json.loads((target_dir / "meta.json").read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[LayoutLingua] Error reading session cache for {doc_id}: {e}")

    # Strategy 2: If not found by direct doc_id folder, search all cached sessions in cache_root
    # in case doc_id was a filename or an older session ID
    if not pdf_bytes and cache_root.is_dir():
        for sub in cache_root.iterdir():
            if sub.is_dir() and (sub / "source.pdf").is_file():
                meta_file = sub / "meta.json"
                if meta_file.is_file():
                    try:
                        m = json.loads(meta_file.read_text(encoding="utf-8"))
                        if m.get("doc_id") == doc_id or m.get("filename") == doc_id or sub.name == doc_id:
                            pdf_bytes = (sub / "source.pdf").read_bytes()
                            if (sub / "translated.pdf").is_file():
                                trans_bytes = (sub / "translated.pdf").read_bytes()
                            meta_info = m
                            break
                    except Exception:
                        pass

    # Strategy 3: Check candidate file paths (Desktop, Downloads, Documents, cwd) if doc_id matches a file
    if not pdf_bytes:
        candidate_paths: list[Path] = []
        p = Path(doc_id)
        candidate_paths.append(p)
        candidate_paths.append(Path.cwd() / p.name)
        if not p.suffix:
            candidate_paths.append(Path.cwd() / f"{p.name}.pdf")
        try:
            folders = get_user_known_folders()
            for fld in folders.values():
                candidate_paths.append(Path(fld) / p.name)
                if not p.suffix:
                    candidate_paths.append(Path(fld) / f"{p.name}.pdf")
        except Exception:
            pass

        for cand in candidate_paths:
            try:
                if cand.is_file() and cand.suffix.lower() == ".pdf":
                    pdf_bytes = cand.read_bytes()
                    meta_info = {"filename": cand.name, "doc_id": doc_id}
                    break
            except Exception:
                continue

    if not pdf_bytes:
        return None

    # Reconstruct session and DocumentIR
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        doc.close()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            doc_ir = parse_pdf(tmp_path, layout_detector=get_layout_detector())
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        with _LOCK:
            while len(_SESSIONS) >= MAX_SESSIONS:
                oldest_k = next(iter(_SESSIONS))
                del _SESSIONS[oldest_k]

            recovered_session = {
                "doc_id": doc_id,
                "filename": meta_info.get("filename", "document.pdf"),
                "source_pdf_bytes": pdf_bytes,
                "doc_ir": doc_ir,
                "page_count": page_count,
                "translated_pdf_bytes": trans_bytes,
                "issues": [],
                "detected_lang": meta_info.get("detected_lang", "en"),
                "is_scanned": meta_info.get("is_scanned", False),
                "scan_warning": meta_info.get("scan_warning", ""),
                "selected_pages": meta_info.get("selected_pages", []),
                "progress": {
                    "stage_index": 5 if trans_bytes else 0,
                    "stage_name": "Complete" if trans_bytes else "idle",
                    "current_page": page_count if trans_bytes else 0,
                    "total_pages": page_count,
                    "overall_pct": 100 if trans_bytes else 0,
                    "status": "done" if trans_bytes else "idle",
                },
            }
            _SESSIONS[doc_id] = recovered_session

        # Ensure it's persisted under doc_id directory as well
        _persist_session_to_disk(recovered_session)
        print(f"[LayoutLingua] Transparently recovered session '{doc_id}' ({meta_info.get('filename')})")
        return recovered_session
    except Exception as exc:
        print(f"[LayoutLingua] Failed to rehydrate session '{doc_id}': {exc}")
        return None


def _run_translation_worker(doc_id: str, req_json: dict) -> None:
    """Background worker thread that translates and typesets a document."""
    session = _get_or_recover_session(doc_id)
    if not session:
        return

    try:
        doc_ir: DocumentIR = session["doc_ir"]
        src_bytes: bytes = session["source_pdf_bytes"]
        target_lang = req_json.get("target_lang", "vi")
        source_lang = req_json.get("source_lang") or session.get("detected_lang") or "auto"

        # Parse selective page range
        page_range_spec = req_json.get("page_range", "all")
        from layoutlingua.processing.page_range import parse_page_range

        selected_pages = parse_page_range(page_range_spec, total_pages=len(doc_ir.pages))

        # Extract translatable segments strictly for selected pages
        segments = extract_document_segments(doc_ir, page_numbers=selected_pages)

        # Read provider options
        provider_type = str(req_json.get("provider", "google")).lower().strip()
        api_key = str(req_json.get("api_key", "")).strip()
        base_url = str(req_json.get("base_url", "")).strip()
        model_name = str(req_json.get("model", "")).strip()
        custom_glossary = req_json.get("custom_glossary", None)

        provider_inst = None
        try:
            if provider_type in ("openai", "ollama") or base_url:
                from layoutlingua.translation.openai_compat import OpenAITranslationProvider

                b_url = base_url if base_url else ("http://localhost:11434/v1" if provider_type == "ollama" else "https://api.openai.com/v1")
                m_id = (model_name or "").strip()
                if not m_id:
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
            from layoutlingua.translation.google_rpc import GoogleRpcTranslationProvider

            provider_inst = GoogleRpcTranslationProvider()

        from layoutlingua.translation.cache import CachedTranslationProvider

        provider_inst = CachedTranslationProvider(provider_inst)

        translated_segments: dict[str, str] = {}
        start_time = time.time()
        total_p = len(doc_ir.pages)

        from layoutlingua.processing.citation import shield_citations, unshield_citations
        from layoutlingua.processing.text_sanitizer import (
            shield_academic_abbreviations,
            unshield_academic_abbreviations,
        )

        batch_sz = 35
        total_segs = len(segments)
        concurrency = 3 if (provider_type in ("openai", "gemini", "ollama") or base_url) else 1

        all_ref_mappings = {}
        all_abbr_mappings = {}
        shielded_chunks = []
        for b_idx in range(0, total_segs, batch_sz):
            chunk = segments[b_idx : b_idx + batch_sz]
            shielded_chunk = []
            for seg in chunk:
                s_text, ref_map = shield_citations(seg.masked_text)
                s_text, abbr_map = shield_academic_abbreviations(s_text)
                if ref_map:
                    all_ref_mappings[seg.segment_id] = ref_map
                if abbr_map:
                    all_abbr_mappings[seg.segment_id] = abbr_map
                if ref_map or abbr_map:
                    shielded_chunk.append(
                        TextSegment(
                            segment_id=seg.segment_id,
                            raw_text=seg.raw_text,
                            masked_text=s_text,
                            tokens=seg.tokens,
                            span_ids=seg.span_ids,
                        )
                    )
                else:
                    shielded_chunk.append(seg)
            shielded_chunks.append(shielded_chunk)

        from layoutlingua.translation.concurrent_pool import concurrent_batch_translate

        def _on_chunk_progress(c_idx: int, done_segs: int, chunk_res: dict[str, str]):
            # Stage 2: Translating text blocks (5% -> 55% overall)
            overall_pct = 5 + int((done_segs / max(1, total_segs)) * 50)
            elapsed = max(0.2, time.time() - start_time)
            curr_speed = round(done_segs / elapsed, 1)
            rem_segs = max(0, total_segs - done_segs)
            calc_eta = int(rem_segs / max(curr_speed, 0.1)) + int(total_p * 0.25)
            # Estimate current page from segment completion ratio
            est_page = max(1, min(total_p, int((done_segs / max(1, total_segs)) * total_p)))
            with _LOCK:
                session["progress"] = {
                    "stage_index": 2,
                    "stage_name": "Translating text blocks",
                    "current_page": est_page,
                    "total_pages": total_p,
                    "segments_done": done_segs,
                    "segments_total": total_segs,
                    "overall_pct": overall_pct,
                    "status": "processing",
                    "speed": curr_speed,
                    "speed_unit": "seg/s",
                    "eta_seconds": calc_eta,
                    "message": f"Translating text blocks ({done_segs}/{total_segs} segments)...",
                }

        try:
            raw_batch_res = concurrent_batch_translate(
                provider=provider_inst,
                chunks=shielded_chunks,
                source_lang=source_lang,
                target_lang=target_lang,
                max_workers=concurrency,
                on_chunk_done=_on_chunk_progress,
            )
            from layoutlingua.processing.formula.isolator import FormulaIsolator

            isolator = FormulaIsolator()
            seg_dict = {seg.segment_id: seg for seg in segments}

            for s_id, t_text in raw_batch_res.items():
                if s_id in all_abbr_mappings:
                    t_text = unshield_academic_abbreviations(t_text, all_abbr_mappings[s_id])
                if s_id in all_ref_mappings:
                    t_text = unshield_citations(t_text, all_ref_mappings[s_id])

                seg = seg_dict.get(s_id)
                if seg and seg.tokens:
                    t_text = isolator.restore_translation(seg, t_text)

                translated_segments[s_id] = t_text
        except RateLimitError as rl_err:
            print(f"[LayoutLingua] Rate limit error: {rl_err}")
            with _LOCK:
                session["progress"] = {
                    "current_page": session.get("progress", {}).get("current_page", 1),
                    "total_pages": total_p,
                    "status": "rate-limited",
                    "speed": 0,
                    "eta_seconds": 0,
                    "message": "Google free quota temporarily blocked (HTTP 429). Please switch provider in Settings.",
                    "error_type": "rate_limit",
                    "provider": "google",
                }
                session["is_translating"] = False
            return
        except Exception as b_err:
            print(f"[LayoutLingua] Translation error: {b_err}")
            with _LOCK:
                session["progress"] = {
                    "current_page": session.get("progress", {}).get("current_page", 1),
                    "total_pages": total_p,
                    "status": "error",
                    "speed": 0,
                    "eta_seconds": 0,
                    "message": f"Translation error: {b_err}",
                }
                session["is_translating"] = False
            return

        elapsed_after_trans = max(0.2, time.time() - start_time)
        trans_speed = round(total_segs / elapsed_after_trans, 1)

        with _LOCK:
            session["progress"] = {
                "stage_index": 2,
                "stage_name": "Translating text blocks",
                "current_page": total_p,
                "total_pages": total_p,
                "segments_done": total_segs,
                "segments_total": total_segs,
                "overall_pct": 52,
                "status": "processing",
                "speed": trans_speed,
                "speed_unit": "seg/s",
                "eta_seconds": int(total_p * 0.25),
                "message": "Applying academic terminology glossaries...",
            }

        # Apply domain glossary & custom user overrides with source text normalization
        try:
            from layoutlingua.translation.glossary import GlossaryManager

            for s_id, t_text in list(translated_segments.items()):
                seg = seg_dict.get(s_id)
                s_text = seg.raw_text if seg else ""
                norm_text = GlossaryManager.normalize_translation(
                    source_text=s_text,
                    translated_text=t_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    custom_glossary=custom_glossary,
                )
                translated_segments[s_id] = GlossaryManager.apply_glossary(
                    text=norm_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    custom_glossary=custom_glossary,
                )
        except Exception as g_err:
            print(f"[LayoutLingua] Glossary application notice: {g_err}")

        # Run TypesetEngine with language-aware font selection
        src_doc = pymupdf.open(stream=src_bytes, filetype="pdf")
        t_lang = (target_lang or "vi").lower().strip()
        typeset_font = "DejaVuSans"
        if t_lang in ("zh-tw", "zh-hant", "chinese (traditional)"):
            typeset_font = "china-t"
        elif t_lang in ("zh", "chinese", "zh-cn", "zh-hans", "chinese (simplified)"):
            typeset_font = "china-s"
        elif t_lang in ("ja", "japanese"):
            typeset_font = "japan"
        elif t_lang in ("ko", "korean"):
            typeset_font = "korea"

        engine = TypesetEngine(options=TypesetOptions(font_name=typeset_font))

        from layoutlingua.typesetting.accumulator import DocumentAccumulator

        accumulator = DocumentAccumulator(source_doc=src_doc)
        total_p = len(src_doc)

        for page_idx in range(total_p):
            pages_done = page_idx + 1
            # Stage 3: Fitting text & typesetting layout (55% -> 95% overall)
            overall_pct = 55 + int((pages_done / max(1, total_p)) * 40)
            elapsed = max(0.2, time.time() - start_time)
            curr_speed = round(pages_done / elapsed, 1)
            rem_p = max(0, total_p - pages_done)
            calc_eta = int(rem_p / max(curr_speed, 0.1)) if curr_speed > 0 else 0

            with _LOCK:
                session["progress"] = {
                    "stage_index": 3,
                    "stage_name": "Fitting text to layout",
                    "current_page": pages_done,
                    "total_pages": total_p,
                    "overall_pct": overall_pct,
                    "status": "processing",
                    "speed": curr_speed,
                    "speed_unit": "p/s",
                    "eta_seconds": calc_eta,
                    "message": f"Fitting text to layout for page {pages_done} of {total_p}...",
                }

            p_ir = doc_ir.pages[page_idx] if page_idx < len(doc_ir.pages) else None
            if p_ir and (page_idx + 1) in selected_pages:
                tx = engine.stage_page_transaction(
                    source_doc=src_doc,
                    page_ir=p_ir,
                    document_ir=doc_ir,
                    translated_segments=translated_segments,
                )
                accumulator.commit_page(tx)
            else:
                accumulator.commit_pristine_source_page(page_idx)

        # Stage 4: Table of Contents & Writing final PDF
        with _LOCK:
            session["progress"] = {
                "stage_index": 4,
                "stage_name": "Writing output PDF",
                "current_page": total_p,
                "total_pages": total_p,
                "overall_pct": 97,
                "status": "processing",
                "speed": curr_speed,
                "speed_unit": "p/s",
                "eta_seconds": 1,
                "message": "Writing final vector output PDF...",
            }

        translated_toc = None
        try:
            from layoutlingua.processing.toc import translate_toc

            translated_toc = translate_toc(
                source_doc=src_doc,
                target_lang=target_lang,
                source_lang=session.get("detected_lang", "en"),
                custom_glossary=custom_glossary,
                bilingual_mode=False,
            )
        except Exception as toc_err:
            print(f"[LayoutLingua] TOC translation notice: {toc_err}")

        # Finalize rendered PDF
        translated_bytes = accumulator.finish(translated_toc=translated_toc)
        src_doc.close()

        with _LOCK:
            session["translated_pdf_bytes"] = translated_bytes
            session["translated_segments"] = translated_segments
            session["target_lang"] = target_lang
            session["custom_glossary"] = custom_glossary
            session["selected_pages"] = sorted(list(selected_pages))
            session["progress"] = {
                "stage_index": 5,
                "stage_name": "Complete",
                "current_page": total_p,
                "total_pages": total_p,
                "overall_pct": 100,
                "selected_pages_count": len(selected_pages),
                "status": "done",
                "speed": round(total_p / max(0.2, time.time() - start_time), 1),
                "speed_unit": "p/s",
                "eta_seconds": 0,
                "message": "Translation complete!",
            }
            session["is_translating"] = False
            _persist_session_to_disk(session)
    except Exception as e:
        import traceback

        traceback.print_exc()
        with _LOCK:
            p_curr = session.get("progress", {}).get("current_page", 1)
            t_p = len(session["doc_ir"].pages) if session.get("doc_ir") else 1
            session["progress"] = {
                "current_page": p_curr,
                "total_pages": t_p,
                "status": "error",
                "speed": 0,
                "eta_seconds": 0,
                "message": f"Translation failed: {e}",
            }
            session["is_translating"] = False


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

            session = _get_or_recover_session(doc_id)

            if not session:
                self._send_json({"error": f"Session '{doc_id}' not found"}, status=404)
                return

            try:
                # Select source or translated document
                if preview_type == "translated":
                    if session.get("translated_pdf_bytes"):
                        pdf_doc = pymupdf.open(stream=session["translated_pdf_bytes"], filetype="pdf")
                    else:
                        self._send_json({"error": "Translated document not yet ready", "status": "processing"}, status=404)
                        return
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
            session = _get_or_recover_session(doc_id)

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
            session = _get_or_recover_session(doc_id)

            if not session:
                self._send_json({"error": "Document session not found"}, status=404)
            export_fmt = query.get("format", ["pdf"])[0].lower().strip()
            if export_fmt in ("md", "markdown"):
                from layoutlingua.processing.markdown_export import export_document_markdown

                md_text = export_document_markdown(
                    doc_ir=session["doc_ir"],
                    translated_segments=session.get("translated_segments"),
                )
                md_bytes = md_text.encode("utf-8")
                base_stem = session.get("filename", "document.pdf").rsplit(".pdf", 1)[0]
                clean_filename = f"{base_stem}.translated.md"
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{clean_filename}"')
                self.send_header("Content-Length", str(len(md_bytes)))
                self.end_headers()
                self.wfile.write(md_bytes)
                return

            raw_source = session.get("source_pdf_bytes")
            raw_translated = session.get("translated_pdf_bytes")

            layout_mode = query.get("mode", ["mono"])[0].lower().strip()
            if layout_mode == "bilingual" and raw_source and raw_translated:
                try:
                    src_doc = pymupdf.open(stream=raw_source, filetype="pdf")
                    tgt_doc = pymupdf.open(stream=raw_translated, filetype="pdf")
                    bi_doc = pymupdf.open()
                    n_pages = max(len(src_doc), len(tgt_doc))
                    for idx in range(n_pages):
                        if idx < len(src_doc):
                            bi_doc.insert_pdf(src_doc, from_page=idx, to_page=idx, annots=True)
                        if idx < len(tgt_doc):
                            bi_doc.insert_pdf(tgt_doc, from_page=idx, to_page=idx, annots=True)
                    if src_doc.metadata:
                        bi_doc.set_metadata(src_doc.metadata)

                    # Translate and set bilingual TOC (doubles page numbers for interleaved layout)
                    try:
                        from layoutlingua.processing.toc import translate_toc

                        bi_toc = translate_toc(
                            source_doc=src_doc,
                            target_lang=session.get("target_lang", "vi"),
                            source_lang=session.get("detected_lang", "en"),
                            custom_glossary=session.get("custom_glossary"),
                            bilingual_mode=True,
                        )
                        if bi_toc:
                            bi_doc.set_toc(bi_toc)
                        elif src_doc.get_toc():
                            bi_doc.set_toc(src_doc.get_toc())
                    except Exception as bi_toc_err:
                        print(f"[LayoutLingua] Bilingual TOC notice: {bi_toc_err}")

                    pdf_bytes = bi_doc.tobytes(deflate=True, garbage=3)
                    bi_doc.close()
                    src_doc.close()
                    tgt_doc.close()
                except Exception as bi_err:
                    print(f"[LayoutLingua] Bilingual export notice: {bi_err}")
                    pdf_bytes = raw_translated or raw_source
            else:
                pdf_bytes = raw_translated or raw_source

            scope = query.get("scope", ["all"])[0].lower().strip()
            selected_pages = session.get("selected_pages")
            total_doc_pages = session.get("page_count", 0)
            if (
                scope == "translated_only"
                and selected_pages
                and total_doc_pages > 0
                and len(selected_pages) < total_doc_pages
            ):
                try:
                    full_pdf = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                    trimmed_pdf = pymupdf.open()
                    for p_num in sorted(selected_pages):
                        if 1 <= p_num <= len(full_pdf):
                            trimmed_pdf.insert_pdf(full_pdf, from_page=p_num - 1, to_page=p_num - 1, annots=True)
                    if full_pdf.metadata:
                        trimmed_pdf.set_metadata(full_pdf.metadata)
                    pdf_bytes = trimmed_pdf.tobytes(deflate=True, garbage=3)
                    trimmed_pdf.close()
                    full_pdf.close()
                except Exception as trim_err:
                    print(f"[LayoutLingua] Scope trim notice: {trim_err}")

            file_name = session.get("filename", "document.pdf")
            base_stem = file_name.rsplit(".pdf", 1)[0]
            tgt_lang_code = session.get("target_lang", "vi")
            if layout_mode == "bilingual":
                file_name = f"{base_stem}.bilingual.pdf"
            else:
                file_name = f"{base_stem}.{tgt_lang_code}.pdf"
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

        # 6. Discover user system folders (Desktop, Downloads, Documents)
        if path in ("/api/system-folders", "/system-folders"):
            folders = get_user_known_folders()
            self._send_json(folders)
            return

        # 7. Native folder picker dialog
        if path in ("/api/pick-folder", "/pick-folder"):
            selected_dir = ""
            try:
                initial = query.get("initial", [""])[0] or get_user_known_folders().get("Desktop", "")
                if sys.platform == "win32":
                    import subprocess

                    ps_cmd = (
                        "Add-Type -AssemblyName System.Windows.Forms; "
                        "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                        f"$f.SelectedPath = '{initial}'; "
                        "$f.Description = 'Select Destination Folder for LayoutLingua Export'; "
                        "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
                    )
                    res = subprocess.run(
                        ["powershell", "-STA", "-NoProfile", "-Command", ps_cmd],
                        capture_output=True,
                        text=True,
                        timeout=25,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        selected_dir = res.stdout.strip().splitlines()[-1].strip()
                elif sys.platform == "darwin":
                    import subprocess

                    osa_cmd = (
                        'POSIX path of (choose folder with prompt "Select Destination Folder for LayoutLingua Export")'
                    )
                    res = subprocess.run(
                        ["osascript", "-e", osa_cmd],
                        capture_output=True,
                        text=True,
                        timeout=25,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        selected_dir = res.stdout.strip()
            except Exception as e:
                print(f"[LayoutLingua] Folder dialog error: {e}")
            self._send_json({"path": selected_dir or ""})
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
                total_images = 0
                for i in range(page_count):
                    p = doc[i]
                    text = p.get_text()
                    words = len(text.split())
                    total_words += words
                    total_images += len(p.get_images())
                    pages_info.append({
                        "n": i + 1,
                        "width": round(p.rect.width, 1),
                        "height": round(p.rect.height, 1),
                        "words": words,
                        "status": "pending",
                    })

                # Scanned PDF pre-flight detection
                avg_words = total_words / max(1, page_count)
                is_scanned = bool(page_count > 0 and ((avg_words < 12 and total_images > 0) or total_words == 0))
                scan_warning = ""
                if is_scanned:
                    scan_warning = (
                        "Scanned document detected: Pages appear to contain image-only scans without selectable text layers. "
                        "LayoutLingua specializes in digital vector typography; an OCR pre-processing step is recommended."
                    )

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
                    doc_ir = parse_pdf(tmp_path, layout_detector=get_layout_detector())
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
                        "is_scanned": is_scanned,
                        "scan_warning": scan_warning,
                        "progress": {
                            "current_page": 0,
                            "total_pages": page_count,
                            "status": "idle",
                        },
                    }
                    _persist_session_to_disk(_SESSIONS[doc_id])

                doc.close()

                self._send_json({
                    "id": doc_id,
                    "name": filename,
                    "size": len(pdf_bytes),
                    "page_count": page_count,
                    "word_count": total_words,
                    "detected_lang": detected_lang,
                    "is_scanned": is_scanned,
                    "scan_warning": scan_warning,
                    "pages": pages_info,
                })
            except Exception as e:
                self._send_json({"error": f"Failed to parse PDF document: {e}"}, status=400)
            return

        # 2. Run document translation & typesetting (asynchronous job)
        if path in ("/api/translate", "/translate"):
            try:
                req_json = json.loads(post_body.decode("utf-8"))
                doc_id = req_json.get("doc_id", "")

                session = _get_or_recover_session(doc_id)

                if not session:
                    self._send_json({"error": f"Session '{doc_id}' not found"}, status=404)
                    return

                with _LOCK:
                    if session.get("is_translating"):
                        self._send_json({
                            "status": "processing",
                            "doc_id": doc_id,
                            "message": "Translation already in progress",
                        })
                        return

                    session["is_translating"] = True
                    total_pages = len(session["doc_ir"].pages) if session.get("doc_ir") else session.get("page_count", 1)
                    session["progress"] = {
                        "current_page": 0,
                        "total_pages": total_pages,
                        "status": "processing",
                        "speed": 0,
                        "eta_seconds": 60,
                        "message": "Initializing background neural translation worker...",
                    }

                worker_th = threading.Thread(
                    target=_run_translation_worker,
                    args=(doc_id, req_json),
                    daemon=True,
                )
                worker_th.start()

                self._send_json({
                    "status": "processing",
                    "doc_id": doc_id,
                    "total_pages": total_pages,
                    "message": "Translation job started",
                })
            except Exception as e:
                import traceback

                traceback.print_exc()
                self._send_json({"error": f"Failed to start translation: {e}"}, status=500)
            return

        # 3. Save file directly to filesystem destination path
        if path in ("/api/save", "/save", "/api/save-file"):
            try:
                req_json = json.loads(post_body.decode("utf-8"))
                doc_id = req_json.get("doc_id", "")
                dest_dir = req_json.get("directory", "").strip()
                file_name = req_json.get("filename", "").strip() or "translated_document.pdf"
                export_fmt = req_json.get("format", "pdf").lower().strip()
                layout_mode = req_json.get("mode", "mono").lower().strip()

                with _LOCK:
                    session = _SESSIONS.get(doc_id)

                if not session:
                    self._send_json({"error": f"Session '{doc_id}' not found"}, status=404)
                    return

                # Resolve known directory nicknames like ~/Desktop, ~/Downloads, Desktop
                known_folders = get_user_known_folders()
                if not dest_dir or dest_dir.lower() in ("desktop", "~/desktop", "desk"):
                    dest_dir = known_folders.get("Desktop", os.path.expanduser("~/Desktop"))
                elif dest_dir.lower() in ("downloads", "~/downloads", "down"):
                    dest_dir = known_folders.get("Downloads", os.path.expanduser("~/Downloads"))
                elif dest_dir.lower() in ("documents", "~/documents", "docs"):
                    dest_dir = known_folders.get("Documents", os.path.expanduser("~/Documents"))
                elif dest_dir.startswith("~"):
                    dest_dir = os.path.expanduser(dest_dir)

                norm_dir = os.path.normpath(os.path.abspath(dest_dir))
                os.makedirs(norm_dir, exist_ok=True)

                clean_filename = re.sub(r'[\r\n/\\:*?"<>|]', '_', file_name)

                # Generate content
                if export_fmt in ("md", "markdown"):
                    from layoutlingua.processing.markdown_export import export_document_markdown

                    md_text = export_document_markdown(
                        doc_ir=session["doc_ir"],
                        translated_segments=session.get("translated_segments"),
                    )
                    content_bytes = md_text.encode("utf-8")
                    if not clean_filename.lower().endswith(".md"):
                        clean_filename += ".md"
                else:
                    raw_source = session.get("source_pdf_bytes")
                    raw_translated = session.get("translated_pdf_bytes")

                    if layout_mode == "bilingual" and raw_source and raw_translated:
                        src_doc = pymupdf.open(stream=raw_source, filetype="pdf")
                        tgt_doc = pymupdf.open(stream=raw_translated, filetype="pdf")
                        bi_doc = pymupdf.open()
                        n_pages = max(len(src_doc), len(tgt_doc))
                        for idx in range(n_pages):
                            if idx < len(src_doc):
                                bi_doc.insert_pdf(src_doc, from_page=idx, to_page=idx, annots=True)
                            if idx < len(tgt_doc):
                                bi_doc.insert_pdf(tgt_doc, from_page=idx, to_page=idx, annots=True)
                        if src_doc.metadata:
                            bi_doc.set_metadata(src_doc.metadata)
                        content_bytes = bi_doc.tobytes(deflate=True, garbage=3)
                        bi_doc.close()
                        src_doc.close()
                        tgt_doc.close()
                    else:
                        content_bytes = raw_translated or raw_source

                    scope = req_json.get("scope", "all").lower().strip()
                    selected_pages = session.get("selected_pages")
                    total_doc_pages = session.get("page_count", 0)
                    if (
                        scope == "translated_only"
                        and selected_pages
                        and total_doc_pages > 0
                        and len(selected_pages) < total_doc_pages
                    ):
                        try:
                            full_pdf = pymupdf.open(stream=content_bytes, filetype="pdf")
                            trimmed_pdf = pymupdf.open()
                            for p_num in sorted(selected_pages):
                                if 1 <= p_num <= len(full_pdf):
                                    trimmed_pdf.insert_pdf(full_pdf, from_page=p_num - 1, to_page=p_num - 1, annots=True)
                            if full_pdf.metadata:
                                trimmed_pdf.set_metadata(full_pdf.metadata)
                            content_bytes = trimmed_pdf.tobytes(deflate=True, garbage=3)
                            trimmed_pdf.close()
                            full_pdf.close()
                        except Exception as trim_err:
                            print(f"[LayoutLingua] Save scope trim notice: {trim_err}")

                    if not clean_filename.lower().endswith(".pdf"):
                        clean_filename += ".pdf"

                target_file_path = os.path.join(norm_dir, clean_filename)
                with open(target_file_path, "wb") as f_out:
                    f_out.write(content_bytes)

                self._send_json({
                    "status": "ok",
                    "saved_path": target_file_path,
                    "directory": norm_dir,
                    "filename": clean_filename,
                    "bytes": len(content_bytes),
                })
            except Exception as e:
                import traceback

                traceback.print_exc()
                self._send_json({"error": f"Failed to save file: {e}"}, status=500)
            return

        # 4. Open saved file location in Windows Explorer
        if path in ("/api/open-folder", "/open-folder"):
            try:
                req_json = json.loads(post_body.decode("utf-8"))
                target_p = req_json.get("path", "").strip()
                if target_p:
                    norm = os.path.normpath(target_p)
                    if os.path.isfile(norm):
                        subprocess.Popen(["explorer.exe", f"/select,{norm}"])
                    elif os.path.isdir(norm):
                        os.startfile(norm)
                self._send_json({"status": "ok"})
            except Exception as e:
                self._send_json({"error": f"Failed to open folder: {e}"}, status=500)
            return

        self._send_json({"error": f"Unknown POST endpoint: {path}"}, status=404)


def start_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Start the LayoutLingua API server."""
    server = ThreadingHTTPServer((host, port), LayoutLinguaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[LayoutLingua] Server running at http://{host}:{port}/")
    return server


def main() -> None:
    """Run the LayoutLingua server as a standalone process."""
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), LayoutLinguaHandler)
    print(f"[LayoutLingua] Local API Server listening on http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LayoutLingua] Server stopped.")


if __name__ == "__main__":
    main()
