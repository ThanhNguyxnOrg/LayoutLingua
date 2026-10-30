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
import hashlib
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
from typing import Any, Optional
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
_RECOVERY_LOCK = threading.Lock()
_PDF_RENDER_LOCK = threading.Lock()
_PREVIEW_CACHE: dict[tuple[str, str, str, int, int, str], bytes] = {}
MAX_PREVIEW_CACHE = 2500
MAX_SESSIONS = 15
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB upload limit
PARSER_VERSION = "2.18"

_SAFE_DOC_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_BLOCKED_SSRF_HOSTS = frozenset({
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.goog",
    "100.100.100.200",
    "0.0.0.0",
    "::",
    "[::]",
})


def _sanitize_doc_id(raw_id: str) -> str:
    """Sanitize document session ID to prevent path traversal."""
    cleaned = os.path.basename((raw_id or "").strip().replace("\\", "/"))
    if not cleaned or cleaned in (".", "..") or ".." in cleaned:
        return ""
    if _SAFE_DOC_ID_RE.match(cleaned):
        return cleaned
    # Fallback deterministic safe slug
    safe_slug = re.sub(r"[^A-Za-z0-9._-]", "_", cleaned)[:64].strip("._")
    return safe_slug


def _validate_provider_base_url(raw_url: str) -> str:
    """Validate OpenAI-compatible provider base_url against SSRF and invalid schemes."""
    candidate = (raw_url or "").strip().rstrip("/")
    if not candidate:
        return "https://api.openai.com/v1"
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Invalid URL scheme. Only HTTP and HTTPS endpoints are permitted.")
    host_low = parsed.hostname.lower()
    if (
        host_low in _BLOCKED_SSRF_HOSTS
        or host_low.startswith("169.254.")
        or host_low.startswith("fe80:")
        or host_low.endswith(".internal")
    ):
        raise ValueError("Blocked restricted or link-local metadata address.")
    if parsed.username or parsed.password:
        raise ValueError("Embedded credentials in base_url are not permitted.")
    # Restrict localhost self-proxy port 8765 to prevent recursive SSRF loop
    port = parsed.port
    if host_low in ("localhost", "127.0.0.1", "::1") and port == int(os.environ.get("PYTHON_ENGINE_PORT") or 8765):
        raise ValueError("Cannot use internal LayoutLingua engine port as LLM provider.")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _is_safe_export_directory(norm_dir: str) -> bool:
    """Ensure export directory is within user home, temp directory, or workspace root."""
    try:
        target = Path(norm_dir).resolve()
        allowed_roots = [
            Path.home().resolve(),
            Path(tempfile.gettempdir()).resolve(),
            Path(__file__).resolve().parent.parent,
        ]
        return any(target == root or target.is_relative_to(root) for root in allowed_roots)
    except Exception:
        return False


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
    workspace_cache = Path(__file__).resolve().parent.parent / ".layoutlingua_cache" / "sessions"
    try:
        workspace_cache.mkdir(parents=True, exist_ok=True)
        return workspace_cache
    except Exception:
        pass
    try:
        import platformdirs

        base_dir = Path(platformdirs.user_cache_dir("layoutlingua"))
    except Exception:
        base_dir = Path.home() / ".layoutlingua" / "cache"
    session_dir = base_dir / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _get_candidate_cache_dirs() -> list[Path]:
    """Return all candidate session cache directories (workspace persistent + OS user cache)."""
    dirs: list[Path] = [_get_session_cache_dir()]
    try:
        import platformdirs

        os_dir = Path(platformdirs.user_cache_dir("layoutlingua")) / "sessions"
        if os_dir not in dirs and os_dir.is_dir():
            dirs.append(os_dir)
    except Exception:
        pass
    return dirs


def _persist_session_to_disk(session: dict[str, Any]) -> None:
    """Save session PDF bytes and metadata to persistent disk cache."""
    try:
        doc_id = _sanitize_doc_id(str(session.get("doc_id") or ""))
        if not doc_id:
            return
        cache_dir = _get_session_cache_dir().resolve()
        target_dir = (cache_dir / doc_id).resolve()
        if not target_dir.is_relative_to(cache_dir):
            return
        target_dir.mkdir(parents=True, exist_ok=True)

        src_bytes = session.get("source_pdf_bytes")
        if src_bytes:
            src_file = target_dir / "source.pdf"
            if not src_file.exists() or src_file.stat().st_size != len(src_bytes):
                src_file.write_bytes(src_bytes)

        trans_bytes = session.get("translated_pdf_bytes")
        trans_pdf_path = target_dir / "translated.pdf"
        if trans_bytes:
            trans_pdf_path.write_bytes(trans_bytes)
            try:
                session["_disk_mtime"] = float(trans_pdf_path.stat().st_mtime)
            except Exception:
                pass
        elif trans_pdf_path.exists():
            try:
                trans_pdf_path.unlink()
                session["_disk_mtime"] = 0.0
            except Exception:
                pass

        page_results = session.get("page_results")
        pr_path = target_dir / "page_results.json"
        if isinstance(page_results, dict) and page_results:
            try:
                serializable_pr = {str(k): v for k, v in page_results.items()}
                pr_path.write_text(
                    json.dumps(serializable_pr, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:
                pass
        elif pr_path.exists():
            try:
                pr_path.unlink()
            except Exception:
                pass

        meta = {
            "doc_id": doc_id,
            "parser_version": PARSER_VERSION,
            "filename": session.get("filename", "document.pdf"),
            "page_count": session.get("page_count", 0),
            "detected_lang": session.get("detected_lang", "en"),
            "target_lang": session.get("target_lang", "vi"),
            "is_scanned": session.get("is_scanned", False),
            "scan_warning": session.get("scan_warning", ""),
            "has_translated": bool(trans_bytes),
            "selected_pages": session.get("selected_pages", []),
            "integrity": session.get("integrity"),
        }
        (target_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[LayoutLingua] Notice: Could not cache session to disk: {exc}")


def _clear_disk_translated_artifacts(doc_id: str) -> None:
    """Remove any cached translated.pdf and page_results.json on disk when a new translation run starts."""
    safe_id = _sanitize_doc_id(doc_id)
    if not safe_id:
        return
    for cache_root in _get_candidate_cache_dirs():
        target_dir = cache_root / safe_id
        if not target_dir.is_dir():
            continue
        for fname in ("translated.pdf", "page_results.json"):
            fpath = target_dir / fname
            if fpath.is_file():
                try:
                    fpath.unlink()
                except Exception:
                    pass
        meta_path = target_dir / "meta.json"
        if meta_path.is_file():
            try:
                m = json.loads(meta_path.read_text(encoding="utf-8"))
                m["has_translated"] = False
                m["integrity"] = None
                meta_path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass


def _ensure_session_doc_ir(session: dict[str, Any]) -> Optional[DocumentIR]:
    """Lazily parse and attach DocumentIR to a recovered session when needed."""
    doc_ir = session.get("doc_ir")
    if doc_ir is not None:
        return doc_ir
    with _RECOVERY_LOCK:
        doc_ir = session.get("doc_ir")
        if doc_ir is not None:
            return doc_ir
        doc_id = _sanitize_doc_id(str(session.get("doc_id") or ""))
        if doc_id and session.get("parser_version") == PARSER_VERSION:
            for cache_root in _get_candidate_cache_dirs():
                ir_file = cache_root / doc_id / "ir.json"
                if ir_file.is_file():
                    try:
                        doc_ir = DocumentIR.from_json(ir_file.read_text(encoding="utf-8"))
                        session["doc_ir"] = doc_ir
                        return doc_ir
                    except Exception:
                        pass
        pdf_bytes = session.get("source_pdf_bytes")
        if not pdf_bytes:
            return None
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        try:
            doc_ir = parse_pdf(tmp_path, layout_detector=get_layout_detector())
            session["doc_ir"] = doc_ir
            if doc_id:
                try:
                    target_dir = _get_session_cache_dir() / doc_id
                    if target_dir.is_dir():
                        (target_dir / "ir.json").write_text(doc_ir.to_json(), encoding="utf-8")
                except Exception:
                    pass
            return doc_ir
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _get_disk_translated_mtime(doc_id: str) -> float:
    safe_id = _sanitize_doc_id(doc_id)
    if not safe_id:
        return 0.0
    for cache_root in _get_candidate_cache_dirs():
        t_pdf = cache_root / safe_id / "translated.pdf"
        if t_pdf.is_file():
            try:
                return float(t_pdf.stat().st_mtime)
            except Exception:
                pass
    return 0.0


def _get_or_recover_session(doc_id: str, require_ir: bool = False) -> Optional[dict[str, Any]]:
    """Retrieve session from RAM or transparently recover from persistent disk cache or local files."""
    doc_id = _sanitize_doc_id(doc_id)
    if not doc_id:
        return None

    disk_mtime = _get_disk_translated_mtime(doc_id)

    with _LOCK:
        if doc_id in _SESSIONS and _SESSIONS[doc_id].get("parser_version") == PARSER_VERSION:
            cand_s = _SESSIONS[doc_id]
            if not cand_s.get("is_translating") and disk_mtime > float(cand_s.get("_disk_mtime") or 0.0) + 0.5:
                del _SESSIONS[doc_id]
                for k in [k for k in _PREVIEW_CACHE if k[0] == doc_id]:
                    del _PREVIEW_CACHE[k]
                existing_s = None
            else:
                existing_s = cand_s
        else:
            existing_s = None

    if existing_s is not None:
        if require_ir and existing_s.get("doc_ir") is None:
            _ensure_session_doc_ir(existing_s)
        return existing_s

    with _RECOVERY_LOCK:
        with _LOCK:
            if doc_id in _SESSIONS and _SESSIONS[doc_id].get("parser_version") == PARSER_VERSION:
                existing_s = _SESSIONS[doc_id]
            else:
                existing_s = None
        if existing_s is not None:
            if require_ir and existing_s.get("doc_ir") is None:
                _ensure_session_doc_ir(existing_s)
            return existing_s

        pdf_bytes: Optional[bytes] = None
        trans_bytes: Optional[bytes] = None
        meta_info: dict[str, Any] = {}
        recovered_page_results: dict[int, dict[str, Any]] = {}

        # Strategy 1 & 2: Check all candidate session cache directories
        for cache_root in _get_candidate_cache_dirs():
            target_dir = cache_root / doc_id
            if target_dir.is_dir() and (target_dir / "source.pdf").is_file():
                try:
                    pdf_bytes = (target_dir / "source.pdf").read_bytes()
                    if (target_dir / "translated.pdf").is_file():
                        trans_bytes = (target_dir / "translated.pdf").read_bytes()
                        disk_mtime = max(disk_mtime, float((target_dir / "translated.pdf").stat().st_mtime))
                    if (target_dir / "meta.json").is_file():
                        meta_info = json.loads((target_dir / "meta.json").read_text(encoding="utf-8"))
                    if (target_dir / "page_results.json").is_file():
                        raw_pr = json.loads((target_dir / "page_results.json").read_text(encoding="utf-8"))
                        if isinstance(raw_pr, dict):
                            recovered_page_results = {int(k): v for k, v in raw_pr.items() if str(k).isdigit()}
                    break
                except Exception as e:
                    print(f"[LayoutLingua] Error reading session cache for {doc_id}: {e}")

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
                                    if (sub / "page_results.json").is_file():
                                        raw_pr = json.loads((sub / "page_results.json").read_text(encoding="utf-8"))
                                        if isinstance(raw_pr, dict):
                                            recovered_page_results = {int(k): v for k, v in raw_pr.items() if str(k).isdigit()}
                                    meta_info = m
                                    break
                            except Exception:
                                pass
                if pdf_bytes:
                    break

        # Strategy 3: Check candidate file paths (Desktop, Downloads, Documents, cwd) if doc_id is a safe bare filename
        if not pdf_bytes:
            candidate_paths: list[Path] = []
            safe_name = os.path.basename(doc_id)
            if safe_name and safe_name not in (".", ".."):
                p = Path(safe_name)
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

        # Fast-path session recovery: open PDF header for page_count in ~1ms and defer heavy parse_pdf
        # until DocumentIR is explicitly needed (e.g. during translation or uncached block inspection).
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)
            doc.close()

            is_current_version = meta_info.get("parser_version") == PARSER_VERSION
            recovered_integrity = meta_info.get("integrity") if is_current_version else None
            effective_trans_bytes = trans_bytes if is_current_version else None
            effective_page_results = recovered_page_results if is_current_version else {}

            doc_ir: Optional[DocumentIR] = None
            if require_ir:
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
                    "parser_version": PARSER_VERSION,
                    "filename": meta_info.get("filename", "document.pdf"),
                    "source_pdf_bytes": pdf_bytes,
                    "doc_ir": doc_ir,
                    "page_count": page_count,
                    "translated_pdf_bytes": effective_trans_bytes,
                    "translated_page_pdfs": {},
                    "issues": recovered_integrity.get("issues", []) if isinstance(recovered_integrity, dict) else [],
                    "integrity": recovered_integrity,
                    "detected_lang": meta_info.get("detected_lang", "en"),
                    "target_lang": meta_info.get("target_lang", "vi"),
                    "is_scanned": meta_info.get("is_scanned", False),
                    "scan_warning": meta_info.get("scan_warning", ""),
                    "selected_pages": meta_info.get("selected_pages", []) if is_current_version else [],
                    "page_results": effective_page_results,
                    "_disk_mtime": disk_mtime,
                    "progress": {
                        "stage_index": 5 if effective_trans_bytes else 0,
                        "stage_name": "Complete" if effective_trans_bytes else "idle",
                        "current_page": page_count if effective_trans_bytes else 0,
                        "total_pages": page_count,
                        "overall_pct": 100 if effective_trans_bytes else 0,
                        "status": "done" if effective_trans_bytes else "idle",
                        **({"integrity": recovered_integrity} if recovered_integrity else {}),
                    },
                }
                _SESSIONS[doc_id] = recovered_session

            # Ensure it's persisted under primary workspace cache directory as well
            _persist_session_to_disk(recovered_session)
            recovered_session["_disk_mtime"] = _get_disk_translated_mtime(doc_id)
            print(f"[LayoutLingua] Transparently recovered session '{doc_id}' ({meta_info.get('filename')})")
            return recovered_session
        except Exception as exc:
            print(f"[LayoutLingua] Failed to rehydrate session '{doc_id}': {exc}")
            return None


def _find_persisted_session(doc_id: str, filename_hint: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Locate a session in RAM or in the persistent disk cache by id or filename."""
    with _LOCK:
        if doc_id and doc_id in _SESSIONS:
            return _SESSIONS[doc_id]
        if filename_hint:
            for s in _SESSIONS.values():
                if s.get("filename") == filename_hint:
                    return s

    if doc_id == "sample_academic":
        return _get_or_recover_session("sample_academic")

    try:
        for cache_root in _get_candidate_cache_dirs():
            if not cache_root.is_dir():
                continue
            for entry in cache_root.iterdir():
                meta_file = entry / "meta.json"
                if not entry.is_dir() or not meta_file.is_file():
                    continue
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if (doc_id and meta.get("doc_id") == doc_id) or (
                    filename_hint and meta.get("filename") == filename_hint
                ):
                    return _get_or_recover_session(meta.get("doc_id") or doc_id)
    except Exception:
        pass
    return None


def _resolve_provider_config(req_json: dict[str, Any]) -> tuple[str, str, str, str, float]:
    """Normalize provider configuration from either frontend UI payload keys or direct API keys."""
    provider_type = str(req_json.get("provider", "")).lower().strip()
    if provider_type in ("openai-compatible", "openai_compat", "custom"):
        provider_type = "openai"
    if not provider_type:
        provider_type = "openai" if req_json.get("base_url") else "google"

    if provider_type == "gemini":
        api_key = str(
            req_json.get("gemini_key")
            or req_json.get("api_key")
            or os.environ.get("GEMINI_API_KEY")
            or ""
        ).strip()
        model_name = str(
            req_json.get("gemini_model")
            or req_json.get("model")
            or "gemini-2.5-flash"
        ).strip()
        base_url = ""
    elif provider_type in ("openai", "ollama"):
        api_key = str(
            req_json.get("openai_key")
            or req_json.get("api_key")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        base_url = str(
            req_json.get("openai_endpoint")
            or req_json.get("base_url")
            or ("http://localhost:11434/v1" if provider_type == "ollama" else "https://api.openai.com/v1")
        ).strip()
        model_name = str(
            req_json.get("openai_model")
            or req_json.get("model")
            or ""
        ).strip()
    else:
        api_key = ""
        base_url = ""
        model_name = ""

    raw_scale = req_json.get("min_font_scale")
    if raw_scale is None:
        raw_scale = req_json.get("min_font_shrink")
    try:
        scale_val = float(raw_scale) if raw_scale is not None else 0.70
        if scale_val > 1.5:
            scale_val = scale_val / 100.0
        min_font_scale = max(0.40, min(1.0, scale_val))
    except (ValueError, TypeError):
        min_font_scale = 0.70

    return provider_type, api_key, base_url, model_name, min_font_scale


def _instantiate_provider(req_json: dict[str, Any]):
    """Instantiate the requested translation provider from normalized request payload."""
    provider_type, api_key, base_url, model_name, _ = _resolve_provider_config(req_json)

    if provider_type in ("google", "google_rpc"):
        from layoutlingua.translation.google_rpc import GoogleRpcTranslationProvider

        return GoogleRpcTranslationProvider()
    elif provider_type == "gemini":
        if not api_key:
            raise ValueError("Gemini API key is required. Please enter your Gemini API key in Settings.")
        from layoutlingua.translation.gemini import GeminiTranslationProvider

        m_id = model_name if model_name else "gemini-2.5-flash"
        return GeminiTranslationProvider(
            api_key=api_key,
            profile_or_model=m_id,
        )
    elif provider_type == "argos":
        from layoutlingua.translation.argos.provider import ArgosTranslationProvider

        argos = ArgosTranslationProvider(auto_install=True)
        if argos.manager.is_runtime_available():
            return argos
        raise ValueError(
            "Argos Translate offline runtime is not installed in this Python environment. "
            "Click 'Install Offline Engine' in Settings or run: pip install argostranslate"
        )
    elif provider_type in ("openai", "ollama") or base_url:
        from layoutlingua.translation.openai_compat import OpenAITranslationProvider

        raw_b_url = base_url if base_url else ("http://localhost:11434/v1" if provider_type == "ollama" else "https://api.openai.com/v1")
        b_url = _validate_provider_base_url(raw_b_url)
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
            b_low = b_url.lower()
            if "api.openai.com" in b_low:
                m_id = "gpt-4o-mini"
            elif "deepseek" in b_low:
                m_id = "deepseek-chat"
            elif "groq" in b_low:
                m_id = "llama-3.3-70b-versatile"
            elif "openrouter" in b_low:
                m_id = "openai/gpt-4o-mini"
            elif "ollama" in b_low or ":11434" in b_low:
                m_id = "llama3.2"
            else:
                raise ValueError(
                    f"No model specified and could not auto-discover models from {b_url}. "
                    f"Please specify a Model ID in Settings."
                )

        return OpenAITranslationProvider(
            api_key=api_key or "ollama",
            model_id=m_id,
            base_url=b_url,
        )

    from layoutlingua.translation.google_rpc import GoogleRpcTranslationProvider

    return GoogleRpcTranslationProvider()



def _run_translation_worker(doc_id: str, req_json: dict, job_id: str = "") -> None:
    """Background worker thread that translates and typesets a document."""
    session = _get_or_recover_session(doc_id, require_ir=True)
    if not session:
        return

    def _is_superseded() -> bool:
        return bool(job_id and session.get("active_job_id") != job_id)

    try:
        doc_ir: DocumentIR = _ensure_session_doc_ir(session)  # type: ignore[assignment]
        total_p = len(doc_ir.pages) if doc_ir and doc_ir.pages else max(1, int(session.get("page_count") or 1))
        src_bytes: bytes = session["source_pdf_bytes"]
        target_lang = req_json.get("target_lang", "vi")
        source_lang = req_json.get("source_lang") or session.get("detected_lang") or "auto"

        # Parse selective page range
        page_range_spec = req_json.get("page_range", "all")
        from layoutlingua.processing.page_range import parse_page_range

        selected_pages = parse_page_range(page_range_spec, total_pages=len(doc_ir.pages))

        # Extract translatable segments strictly for selected pages
        segments = extract_document_segments(
            doc_ir,
            page_numbers=selected_pages,
            source_lang=source_lang,
            target_lang=target_lang,
        )

        # Read provider options (supports both UI payload keys and direct API keys)
        provider_type, api_key, base_url, model_name, min_font_scale = _resolve_provider_config(req_json)
        custom_glossary = req_json.get("custom_glossary", None)

        provider_inst = None
        try:
            provider_inst = _instantiate_provider(req_json)
        except Exception as p_err:
            print(f"[LayoutLingua] Provider init notice: {p_err}")
            with _LOCK:
                session["progress"] = {
                    "current_page": session.get("progress", {}).get("current_page", 1),
                    "total_pages": total_p,
                    "status": "error",
                    "speed": 0,
                    "eta_seconds": 0,
                    "message": f"Provider error: {p_err}",
                }
                session["is_translating"] = False
            return


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
        from layoutlingua.processing.telemetry import PipelineProgressTracker

        selected_count = len(selected_pages)
        tracker = PipelineProgressTracker(total_pages=selected_count, total_segments=total_segs)
        tracker.set_stage(2)

        def _on_chunk_progress(c_idx: int, done_segs: int, chunk_res: dict[str, str]):
            with _LOCK:
                if _is_superseded():
                    return
                snap = tracker.update_translation(done_segs, total_segs)
                snap["job_id"] = job_id
                snap["target_lang"] = target_lang
                if selected_count < total_p:
                    snap["subtitle"] = f"segment {done_segs} of {total_segs} ({selected_count} pp)"
                    snap["message"] = f"Translating selected text ({done_segs}/{total_segs} segments across {selected_count} pp)..."
                session["progress"] = snap

        effective_batch_src_lang = (
            source_lang
            if (source_lang and source_lang != "auto")
            else (session.get("detected_lang") or "en" if provider_type in ("argos", "gemini", "openai", "ollama") else "auto")
        )

        try:
            raw_batch_res = concurrent_batch_translate(
                provider=provider_inst,
                chunks=shielded_chunks,
                source_lang=effective_batch_src_lang,
                target_lang=target_lang,
                max_workers=concurrency,
                on_chunk_done=_on_chunk_progress,
            )
            from layoutlingua.processing.formula.isolator import FormulaIsolator

            isolator = FormulaIsolator()
            seg_dict = {seg.segment_id: seg for seg in segments}

            from layoutlingua.translation.glossary import GlossaryManager

            eff_src_lang_pre = source_lang if (source_lang and source_lang != "auto") else (session.get("detected_lang") or "vi")
            for s_id, t_text in raw_batch_res.items():
                if s_id in all_abbr_mappings:
                    t_text = unshield_academic_abbreviations(t_text, all_abbr_mappings[s_id])
                if s_id in all_ref_mappings:
                    t_text = unshield_citations(t_text, all_ref_mappings[s_id])

                seg = seg_dict.get(s_id)
                if seg:
                    try:
                        t_text = GlossaryManager.normalize_translation(
                            source_text=seg.raw_text,
                            translated_text=t_text,
                            source_lang=eff_src_lang_pre,
                            target_lang=target_lang,
                            custom_glossary=custom_glossary,
                            masked_source_text=seg.masked_text,
                        )
                    except Exception:
                        pass
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

        with _LOCK:
            if _is_superseded():
                return
            snap_gloss = tracker.snapshot(message="Applying academic terminology glossaries...")
            snap_gloss["job_id"] = job_id
            snap_gloss["target_lang"] = target_lang
            session["progress"] = snap_gloss

        # Always apply built-in academic & mathematical terminology glossary + optional user overrides
        try:
            from layoutlingua.translation.glossary import GlossaryManager

            eff_src_lang = source_lang if (source_lang and source_lang != "auto") else (session.get("detected_lang") or "vi")
            for s_id, t_text in list(translated_segments.items()):
                seg = seg_dict.get(s_id)
                s_text = seg.raw_text if seg else ""
                m_text = seg.masked_text if seg else None
                norm_text = GlossaryManager.normalize_translation(
                    source_text=s_text,
                    translated_text=t_text,
                    source_lang=eff_src_lang,
                    target_lang=target_lang,
                    custom_glossary=custom_glossary,
                    masked_source_text=m_text,
                )
                if custom_glossary and str(custom_glossary).strip():
                    norm_text = GlossaryManager.apply_glossary(
                        text=norm_text,
                        source_lang=eff_src_lang,
                        target_lang=target_lang,
                        custom_glossary=custom_glossary,
                    )
                translated_segments[s_id] = norm_text
        except Exception as g_err:
            print(f"[LayoutLingua] Glossary application notice: {g_err}")

        # Run Sub-Line Formula Pinning & Horizontal-Scale Typesetter via core TypesetEngine
        from layoutlingua.typesetting.accumulator import DocumentAccumulator
        from layoutlingua.typesetting.engine import TypesetEngine
        from layoutlingua.typesetting.models import BlockFittingStatus, FittingReport, TypesetOptions

        src_doc = pymupdf.open(stream=src_bytes, filetype="pdf")
        accum = DocumentAccumulator(src_doc)
        total_p = len(src_doc)

        engine = TypesetEngine(options=TypesetOptions(min_font_scale=min_font_scale))
        report = FittingReport()

        total_replaced_blocks = 0
        total_review_blocks = 0
        total_preserved_pages = 0
        page_statuses: dict[int, str] = {}
        page_block_counts: dict[int, int] = {}
        collected_issues: list[dict[str, Any]] = []
        page_results: dict[int, dict[str, Any]] = dict(session.get("page_results") or {})

        tracker.set_stage(3)
        processed_selected = 0
        cancel_requested = False

        for page_idx in range(total_p):
            if _is_superseded():
                src_doc.close()
                return
            if session.get("cancel_requested"):
                cancel_requested = True
                break
            p_ir = doc_ir.pages[page_idx] if page_idx < len(doc_ir.pages) else None
            p_num = page_idx + 1
            if p_num in selected_pages and p_ir is not None:
                processed_selected += 1
                with _LOCK:
                    if _is_superseded():
                        src_doc.close()
                        return
                    snap = tracker.update_typesetting(processed_selected)
                    snap["job_id"] = job_id
                    snap["target_lang"] = target_lang
                    if selected_count < total_p:
                        snap["subtitle"] = f"page {p_num} ({processed_selected} of {selected_count})"
                        snap["message"] = f"Fitting layout for page {p_num} ({processed_selected}/{selected_count} selected)..."
                    snap["integrity"] = {
                        "blocks_translated": total_replaced_blocks,
                        "needs_review": total_review_blocks,
                        "preserved_pages": total_preserved_pages,
                        "page_statuses": dict(page_statuses),
                        "page_block_counts": dict(page_block_counts),
                        "issues": list(collected_issues),
                    }
                    session["progress"] = snap

                tx_result = engine.stage_page_transaction(
                    source_doc=src_doc,
                    page_ir=p_ir,
                    document_ir=doc_ir,
                    translated_segments=translated_segments,
                )
                try:
                    single_page_pdf = tx_result.staging_doc.tobytes(deflate=False)
                except Exception:
                    single_page_pdf = None
                accum.commit_page(tx_result)

                detail_by_id = {d.block_id: d for d in tx_result.details}
                page_w = float(p_ir.geometry.width) if p_ir else 595.0
                page_h = float(p_ir.geometry.height) if p_ir else 842.0
                blocks_meta: list[dict[str, Any]] = []
                page_issues: list[dict[str, Any]] = []

                for b in p_ir.blocks:
                    bx0, by0, bx1, by1 = b.bbox
                    d = detail_by_id.get(b.block_id)
                    status_val = d.status if d else BlockFittingStatus.SKIPPED_UNCHANGED
                    trans_str = (
                        d.translated_text
                        if (d and d.translated_text)
                        else translated_segments.get(b.block_id, b.text)
                    )
                    shrink_val = float(d.shrink_ratio) if d else 1.0
                    is_preserved = status_val != BlockFittingStatus.SUCCESS
                    blocks_meta.append({
                        "id": b.block_id,
                        "kind": b.block_type,
                        "bbox": {
                            "x": float(bx0),
                            "y": float(by0),
                            "w": float(bx1 - bx0),
                            "h": float(by1 - by0),
                        },
                        "pageW": page_w,
                        "pageH": page_h,
                        "sourceText": b.text,
                        "translatedText": trans_str,
                        "fontScale": shrink_val,
                        "preserved": is_preserved,
                    })
                    if status_val in (
                        BlockFittingStatus.OVERFLOW_FALLBACK,
                        BlockFittingStatus.COLLISION_FALLBACK,
                        BlockFittingStatus.TRANSACTION_FALLBACK,
                    ):
                        pct_x = round((float(bx0) / max(1.0, page_w)) * 100.0, 1)
                        pct_y = round((float(by0) / max(1.0, page_h)) * 100.0, 1)
                        pct_w = round((max(8.0, float(bx1 - bx0)) / max(1.0, page_w)) * 100.0, 1)
                        pct_h = round((max(8.0, float(by1 - by0)) / max(1.0, page_h)) * 100.0, 1)
                        page_issues.append({
                            "id": f"iss_p{p_num}_{b.block_id}",
                            "severity": "warning",
                            "page": p_num,
                            "block_id": b.block_id,
                            "code": status_val.value.upper(),
                            "title": f"Page {p_num}: Layout fallback ({status_val.value})",
                            "detail": d.reason if d else f"Preserved original block: {b.text[:80]}",
                            "shrink_ratio": round(shrink_val, 3),
                            "region": {
                                "x": pct_x,
                                "y": pct_y,
                                "w": pct_w,
                                "h": pct_h,
                                "label": b.block_id,
                            },
                            "next": "Inspect the highlighted region or add a shorter term in Glossary.",
                            "action": f"Inspect region on page {p_num}",
                        })
                    elif status_val == BlockFittingStatus.SUCCESS and shrink_val < 0.65:
                        pct_x = round((float(bx0) / max(1.0, page_w)) * 100.0, 1)
                        pct_y = round((float(by0) / max(1.0, page_h)) * 100.0, 1)
                        pct_w = round((max(8.0, float(bx1 - bx0)) / max(1.0, page_w)) * 100.0, 1)
                        pct_h = round((max(8.0, float(by1 - by0)) / max(1.0, page_h)) * 100.0, 1)
                        page_issues.append({
                            "id": f"iss_p{p_num}_{b.block_id}",
                            "severity": "warning",
                            "page": p_num,
                            "block_id": b.block_id,
                            "code": "FONT_SHRINK_NOTICE",
                            "title": f"Page {p_num}: Tight fit ({round(shrink_val * 100)}% scale)",
                            "detail": f"Source: \"{b.text[:70]}\" → \"{trans_str[:70]}\"",
                            "shrink_ratio": round(shrink_val, 3),
                            "region": {
                                "x": pct_x,
                                "y": pct_y,
                                "w": pct_w,
                                "h": pct_h,
                                "label": f"{round(shrink_val * 100)}% scale",
                            },
                            "next": "Verify legibility in dual-view or define a more concise glossary term.",
                            "action": f"Review block on page {p_num}",
                        })

                replaced_on_page = int(tx_result.summary.replaced_blocks + tx_result.summary.replaced_cells)
                overflow_on_page = len(page_issues)
                if tx_result.is_fallback:
                    total_preserved_pages += 1

                total_replaced_blocks += replaced_on_page
                total_review_blocks += overflow_on_page
                page_block_counts[p_num] = len(blocks_meta)
                page_statuses[p_num] = "warn" if overflow_on_page > 0 else "ok"
                collected_issues.extend(page_issues)

                page_results[p_num] = {
                    "page": p_num,
                    "pageW": page_w,
                    "pageH": page_h,
                    "blocksTranslated": replaced_on_page,
                    "blocks": blocks_meta,
                    "issues": page_issues,
                }

                # Progressive commit after each page using fast single-page stream so live preview,
                # block metadata, and Quality checks update immediately without re-compressing all 96 pages
                try:
                    with _LOCK:
                        if _is_superseded():
                            src_doc.close()
                            return
                        if single_page_pdf is not None:
                            session.setdefault("translated_page_pdfs", {})[p_num] = single_page_pdf
                        session["page_results"] = dict(page_results)
                        live_integrity = {
                            "blocks_translated": total_replaced_blocks,
                            "needs_review": len(collected_issues),
                            "preserved_pages": total_preserved_pages,
                            "page_statuses": dict(page_statuses),
                            "page_block_counts": dict(page_block_counts),
                            "completed_pages": {k: True for k in page_results},
                            "issues": list(collected_issues),
                        }
                        session["integrity"] = live_integrity
                        if isinstance(session.get("progress"), dict):
                            session["progress"]["integrity"] = live_integrity
                except Exception:
                    pass
            else:
                accum.commit_pristine_source_page(page_idx)
                page_statuses[p_num] = "ok"
                page_block_counts[p_num] = len(p_ir.blocks) if p_ir else 0

        if cancel_requested:
            try:
                for rem_idx in range(len(accum.output_doc), total_p):
                    accum.commit_pristine_source_page(rem_idx)
                partial_bytes = accum.finish(report=report)
                src_doc.close()
                with _LOCK:
                    session["translated_pdf_bytes"] = partial_bytes
                    session["translated_segments"] = translated_segments
                    session["page_results"] = page_results
                    session["selected_pages"] = sorted(list(selected_pages))
                    session["is_translating"] = False
                    session["progress"] = {
                        "stage_index": 3,
                        "stage_name": "Cancelled",
                        "current_page": processed_selected,
                        "total_pages": selected_count,
                        "overall_pct": tracker.calculate_overall_pct(),
                        "status": "idle",
                        "eta_seconds": 0,
                        "message": "Translation cancelled. Pages already translated are kept.",
                    }
                _persist_session_to_disk(session)
            except Exception as cancel_err:
                print(f"[LayoutLingua] Cancel finalize notice: {cancel_err}")
            return

        # Stage 4: Table of Contents & Writing final PDF
        with _LOCK:
            if _is_superseded():
                src_doc.close()
                return
            tracker.set_stage(4)
            snap_s4 = tracker.snapshot(
                message="Writing final vector output PDF...",
                integrity={
                    "blocks_translated": total_replaced_blocks,
                    "needs_review": total_review_blocks,
                    "preserved_pages": total_preserved_pages,
                    "page_statuses": dict(page_statuses),
                    "page_block_counts": dict(page_block_counts),
                    "issues": list(collected_issues),
                },
            )
            snap_s4["job_id"] = job_id
            snap_s4["target_lang"] = target_lang
            session["progress"] = snap_s4

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

        # Finalize rendered PDF via DocumentAccumulator (restores links, subsets fonts, preserves metadata)
        translated_bytes = accum.finish(report=report, translated_toc=translated_toc)
        src_doc.close()

        integrity_data = {
            "blocks_translated": total_replaced_blocks,
            "needs_review": total_review_blocks,
            "preserved_pages": total_preserved_pages,
            "page_statuses": page_statuses,
            "page_block_counts": page_block_counts,
            "completed_pages": {k: True for k in page_results},
            "issues": collected_issues,
        }

        with _LOCK:
            if _is_superseded():
                return
            session["translated_pdf_bytes"] = translated_bytes
            session["translated_segments"] = translated_segments
            session["page_results"] = page_results
            session["target_lang"] = target_lang
            session["custom_glossary"] = custom_glossary
            session["selected_pages"] = sorted(list(selected_pages))
            session["integrity"] = integrity_data
            session["progress"] = {
                "job_id": job_id,
                "target_lang": target_lang,
                "stage_index": 5,
                "stage_name": "Complete",
                "current_page": selected_count,
                "total_pages": selected_count,
                "overall_pct": 100,
                "selected_pages_count": selected_count,
                "status": "done",
                "speed": round(selected_count / max(0.2, time.time() - start_time), 1),
                "speed_unit": "p/s",
                "eta_seconds": 0,
                "message": "Translation complete!",
                "integrity": integrity_data,
            }
            session["is_translating"] = False
            session.pop("_cached_trans_doc", None)
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
                "Content-Type, Authorization, X-Filename, X-Doc-Id",
            )
            self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_image(self, img_bytes: bytes, content_type: str = "image/png") -> None:
        try:
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(img_bytes)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(img_bytes)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # 1. Health check
        if path in ("/api/health", "/health"):
            self._send_json({"status": "ok", "version": __version__, "engine": "PyMuPDF (Python Sub-Line IR)"})
            return

        # 1a. Export complete converted Python engine archive (.zip)
        if path in ("/api/export-python-engine", "/export-python-engine"):
            import zipfile

            buf = io.BytesIO()
            root_dir = Path(__file__).resolve().parent.parent
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for rel_target in ("layoutlingua", "tests", "pyproject.toml", "requirements.txt", "LayoutLingua.bat", "README.md"):
                    target_path = root_dir / rel_target
                    if target_path.is_file():
                        zf.write(target_path, arcname=rel_target)
                    elif target_path.is_dir():
                        for fp in target_path.rglob("*"):
                            if fp.is_file() and "__pycache__" not in fp.parts and not fp.name.endswith(".pyc"):
                                zf.write(fp, arcname=str(fp.relative_to(root_dir)))
            zip_bytes = buf.getvalue()
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="layoutlingua-python-engine.zip"')
            self.send_header("Content-Length", str(len(zip_bytes)))
            self.end_headers()
            self.wfile.write(zip_bytes)
            return

        # 1b. Check whether a recent document session exists on the server (in memory or on disk)
        if path in ("/api/session-status", "/session-status"):
            doc_id = query.get("id", [""])[0]
            name_hint = query.get("name", [""])[0] or None
            found = _find_persisted_session(doc_id, name_hint) if (doc_id or name_hint) else None
            if found:
                prog = found.get("progress") or {}
                is_done = bool(found.get("translated_pdf_bytes")) or prog.get("status") == "done"
                self._send_json({
                    "exists": True,
                    "id": found.get("doc_id", doc_id),
                    "name": found.get("filename", name_hint or "Document.pdf"),
                    "size": len(found.get("source_pdf_bytes") or b""),
                    "page_count": found.get("page_count", 0),
                    "detected_lang": found.get("detected_lang", "en"),
                    "target_lang": found.get("target_lang", "vi"),
                    "status": "translated" if is_done else "pending",
                })
            else:
                self._send_json({"exists": False})
            return

        if path in ("/api/recent-sessions", "/recent-sessions"):
            recent_items: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            for cache_root in _get_candidate_cache_dirs():
                if not cache_root.is_dir():
                    continue
                for sub in sorted(cache_root.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
                    if not sub.is_dir() or not (sub / "source.pdf").is_file() or not (sub / "meta.json").is_file():
                        continue
                    try:
                        m = json.loads((sub / "meta.json").read_text(encoding="utf-8"))
                        did = str(m.get("doc_id") or sub.name)
                        if did in seen_ids:
                            continue
                        seen_ids.add(did)
                        has_trans = (sub / "translated.pdf").is_file()
                        recent_items.append({
                            "id": did,
                            "name": m.get("filename", f"{did}.pdf"),
                            "pages": int(m.get("page_count") or 1),
                            "size": (sub / "source.pdf").stat().st_size,
                            "status": "translated" if has_trans else "pending",
                            "detectedLang": m.get("detected_lang", "vi"),
                        })
                    except Exception:
                        pass
            self._send_json({"sessions": recent_items})
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

            # Return layout block metadata JSON for interactive hover overlay
            if query.get("format", ["png"])[0].lower() == "meta":
                page_res_map = session.get("page_results") or {}
                if page_num in page_res_map:
                    pr = page_res_map[page_num]
                    self._send_json({
                        "page": page_num,
                        "pageW": pr.get("pageW", 595.0),
                        "pageH": pr.get("pageH", 842.0),
                        "blocks": pr.get("blocks", []),
                    })
                    return

                blocks_out: list[dict[str, Any]] = []
                doc_ir_obj = session.get("doc_ir") or _ensure_session_doc_ir(session)
                page_ir = (
                    doc_ir_obj.pages[page_num - 1]
                    if doc_ir_obj is not None and 0 <= page_num - 1 < len(doc_ir_obj.pages)
                    else None
                )
                page_w = float(page_ir.geometry.width) if page_ir else 595.0
                page_h = float(page_ir.geometry.height) if page_ir else 842.0

                # Navigation links: source GoTo annotations become #page=N uris
                goto_links: list[dict[str, Any]] = []
                try:
                    nav_doc = pymupdf.open(stream=session.get("source_pdf_bytes") or b"", filetype="pdf")
                    if 0 <= page_num - 1 < len(nav_doc):
                        for lnk in nav_doc[page_num - 1].get_links():
                            if lnk.get("kind") == pymupdf.LINK_GOTO and lnk.get("page") is not None:
                                goto_links.append(lnk)
                    nav_doc.close()
                except Exception:
                    goto_links = []

                def _overlaps_link(bx: tuple[float, float, float, float]) -> Optional[int]:
                    bx0, by0, bx1, by1 = bx
                    for lnk in goto_links:
                        r = lnk.get("from")
                        if r is None:
                            continue
                        overlap_x = min(bx1, r.x1) - max(bx0, r.x0)
                        overlap_y = min(by1, r.y1) - max(by0, r.y0)
                        if overlap_x > 1 and overlap_y > 1:
                            return int(lnk["page"]) + 1
                    return None

                if page_ir is not None:
                    for b in page_ir.blocks:
                        try:
                            bx0, by0, bx1, by1 = b.bbox
                        except Exception:
                            continue
                        nav_target = _overlaps_link((float(bx0), float(by0), float(bx1), float(by1)))
                        if nav_target is None:
                            m_toc = re.match(r"^(.*?)[.\s…·]{3,}\s*(\d{1,4})\s*$", b.text.strip())
                            if m_toc:
                                nav_target = int(m_toc.group(2))
                        blocks_out.append({
                            "id": b.block_id,
                            "kind": b.block_type,
                            "bbox": {
                                "x": float(bx0),
                                "y": float(by0),
                                "w": float(bx1 - bx0),
                                "h": float(by1 - by0),
                            },
                            "pageW": page_w,
                            "pageH": page_h,
                            "sourceText": b.text,
                            "translatedText": b.text,
                            "fontScale": 1.0,
                            "preserved": True,
                            **({"uri": f"#page={nav_target}"} if nav_target else {}),
                        })
                self._send_json({
                    "page": page_num,
                    "pageW": page_w,
                    "pageH": page_h,
                    "blocks": blocks_out,
                })
                return

            try:
                req_dpi_str = query.get("dpi", ["150"])[0]
                try:
                    render_dpi = max(48, min(300, int(req_dpi_str)))
                except ValueError:
                    render_dpi = 150

                # Select source or translated document bytes
                single_page_stream = None
                if preview_type == "translated":
                    req_lang = query.get("lang", [""])[0].strip().lower()
                    sess_lang = str(session.get("target_lang") or "").strip().lower()
                    if req_lang and sess_lang and req_lang != sess_lang:
                        self._send_json(
                            {"error": f"Translated document for '{req_lang}' not yet ready", "status": "processing"},
                            status=404,
                        )
                        return
                    single_page_stream = (session.get("translated_page_pdfs") or {}).get(page_num)
                    if session.get("is_translating") and single_page_stream is None:
                        self._send_json(
                            {"error": f"Page {page_num} is currently being translated", "status": "processing"},
                            status=404,
                        )
                        return
                    target_bytes = single_page_stream or session.get("translated_pdf_bytes")
                    if not target_bytes:
                        self._send_json({"error": "Translated document not yet ready", "status": "processing"}, status=404)
                        return
                else:
                    target_bytes = session.get("source_pdf_bytes")
                    if not target_bytes:
                        self._send_json({"error": "Source document missing"}, status=404)
                        return

                bytes_digest = hashlib.sha1(target_bytes[:16384] + target_bytes[-16384:]).hexdigest()[:12]
                tgt_lang_tag = str(session.get("target_lang") or "") if preview_type == "translated" else "src"
                cache_key = (str(session.get("doc_id") or doc_id), preview_type, tgt_lang_tag, page_num, render_dpi, bytes_digest)
                with _LOCK:
                    cached_png = _PREVIEW_CACHE.get(cache_key)
                if cached_png is not None:
                    self._send_image(cached_png, "image/png")
                    return

                with _PDF_RENDER_LOCK:
                    if single_page_stream is not None:
                        pdf_doc = pymupdf.open(stream=single_page_stream, filetype="pdf")
                        try:
                            pix = pdf_doc[0].get_pixmap(dpi=render_dpi)
                            img_data = pix.tobytes("png")
                        finally:
                            pdf_doc.close()
                    else:
                        doc_cache_attr = "_cached_trans_doc" if preview_type == "translated" else "_cached_src_doc"
                        pdf_doc = session.get(doc_cache_attr)
                        if pdf_doc is None or getattr(pdf_doc, "is_closed", True):
                            pdf_doc = pymupdf.open(stream=target_bytes, filetype="pdf")
                            session[doc_cache_attr] = pdf_doc
                        page_idx = min(len(pdf_doc) - 1, max(0, page_num - 1))
                        page = pdf_doc[page_idx]
                        pix = page.get_pixmap(dpi=render_dpi)
                        img_data = pix.tobytes("png")

                with _LOCK:
                    if len(_PREVIEW_CACHE) >= MAX_PREVIEW_CACHE:
                        oldest_key = next(iter(_PREVIEW_CACHE))
                        del _PREVIEW_CACHE[oldest_key]
                    _PREVIEW_CACHE[cache_key] = img_data

                self._send_image(img_data, "image/png")
            except Exception as e:
                self._send_json({"error": f"Failed to render page: {e}"}, status=500)
            return

        # 3. Translation progress & status tracking
        if path in ("/api/progress", "/progress", "/api/status", "/status"):
            doc_id = query.get("id", [""])[0]
            session = _get_or_recover_session(doc_id)

            if not session:
                self._send_json({"error": "Document session not found"}, status=404)
                return

            prog = dict(session.get("progress", {
                "current_page": 0,
                "total_pages": session.get("page_count", 0),
                "status": "idle",
            }))
            prog["target_lang"] = session.get("target_lang", "vi")
            prog["job_id"] = session.get("active_job_id", prog.get("job_id", ""))
            if "integrity" not in prog and "integrity" in session and prog.get("status") != "processing":
                prog["integrity"] = session["integrity"]
            if path in ("/api/status", "/status"):
                page_q = max(1, int(query.get("page", ["1"])[0] or "1"))
                pr = (session.get("page_results") or {}).get(page_q, {})
                prog["document"] = {
                    "id": session.get("doc_id", doc_id),
                    "name": session.get("filename", "Document.pdf"),
                    "pageCount": session.get("page_count", 1),
                    "detectedLang": session.get("detected_lang", "en"),
                    "targetLang": session.get("target_lang", "vi"),
                    "status": "translated" if session.get("translated_pdf_bytes") else "ready",
                }
                prog["blocks"] = pr.get("blocks", [])
            self._send_json(prog)
            return

        # 4. Download translated PDF file
        if path in ("/api/download", "/download"):
            doc_id = query.get("id", [""])[0]
            session = _get_or_recover_session(doc_id)

            if not session:
                self._send_json({"error": "Document session not found"}, status=404)
                return
            export_fmt = query.get("format", ["pdf"])[0].lower().strip()
            if export_fmt in ("md", "markdown"):
                from layoutlingua.processing.markdown_export import export_document_markdown

                doc_ir_obj = session.get("doc_ir") or _ensure_session_doc_ir(session)
                md_text = export_document_markdown(
                    doc_ir=doc_ir_obj,
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

        # 5. Query models from Gemini or any OpenAI-compatible / Local LLM provider
        if path in ("/api/models", "/api/fetch-models"):
            provider_param = query.get("provider", [""])[0].strip().lower()
            api_key = query.get("api_key", [""])[0].strip()

            if provider_param == "gemini":
                if not api_key:
                    self._send_json(
                        {"models": [], "status": "error", "error": "Gemini API key is required to list available models."},
                        status=400,
                    )
                    return
                try:
                    from layoutlingua.translation.gemini import GeminiTranslationProvider

                    gem = GeminiTranslationProvider(api_key=api_key, profile_or_model="auto")
                    models = gem.list_remote_models()
                    recommended = gem.resolve_best_available_model(preferred_hint="flash")
                    self._send_json({
                        "models": models,
                        "recommended": recommended or "gemini-2.5-flash",
                        "status": "ok",
                    })
                    return
                except Exception as ge:
                    self._send_json({
                        "models": [],
                        "status": "error",
                        "error": f"Failed to fetch Gemini models: {ge}",
                    })
                    return

            raw_base_url = query.get("base_url", ["https://api.openai.com/v1"])[0].rstrip("/")

            try:
                base_url = _validate_provider_base_url(raw_base_url)
            except ValueError as ve:
                self._send_json(
                    {"models": [], "status": "error", "error": str(ve)},
                    status=400,
                )
                return

            models_url = f"{base_url}/models"
            try:
                headers = {"User-Agent": "LayoutLingua/2.0"}
                if api_key and api_key != "ollama":
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

        # 5b. Query Argos offline engine status & installed language packs
        if path in ("/api/argos/status", "/argos/status"):
            try:
                from layoutlingua.translation.argos.manager import ArgosModelManager

                mgr = ArgosModelManager()
                runtime_ok = mgr.is_runtime_available()
                installed = [
                    {
                        "from_code": m.from_code,
                        "to_code": m.to_code,
                        "package_name": m.package_name,
                        "version": m.version,
                    }
                    for m in mgr.list_installed_models()
                ]
                available = [
                    {
                        "from_code": m.from_code,
                        "to_code": m.to_code,
                        "package_name": m.package_name,
                        "is_installed": m.is_installed,
                    }
                    for m in mgr.list_available_models()
                ]
                self._send_json({
                    "status": "ok",
                    "runtime_available": runtime_ok,
                    "installed_models": installed,
                    "available_models": available,
                })
            except Exception as e:
                self._send_json({"status": "error", "error": str(e)}, status=500)
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
                        "if ($env:LL_INITIAL_DIR -and (Test-Path -LiteralPath $env:LL_INITIAL_DIR)) { "
                        "$f.SelectedPath = $env:LL_INITIAL_DIR }; "
                        "$f.Description = 'Select Destination Folder for LayoutLingua Export'; "
                        "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
                    )
                    res = subprocess.run(
                        ["powershell", "-STA", "-NoProfile", "-Command", ps_cmd],
                        env={**os.environ, "LL_INITIAL_DIR": str(initial)},
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

        # 8. Serve built Desktop UI assets from dist/ when running standalone
        if not path.startswith("/api/"):
            import mimetypes

            base_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
            dist_dir = base_root / "dist"
            if dist_dir.is_dir():
                rel_req = path.lstrip("/") or "index.html"
                candidate_file = (dist_dir / rel_req).resolve()
                # Security guard: ensure resolved path stays inside dist_dir
                if str(candidate_file).startswith(str(dist_dir.resolve())) and candidate_file.is_file():
                    target_file = candidate_file
                else:
                    target_file = dist_dir / "index.html"

                if target_file.is_file():
                    mime_type, _ = mimetypes.guess_type(str(target_file))
                    if target_file.suffix.lower() == ".js":
                        mime_type = "application/javascript; charset=utf-8"
                    elif target_file.suffix.lower() == ".css":
                        mime_type = "text/css; charset=utf-8"
                    elif target_file.suffix.lower() == ".html":
                        mime_type = "text/html; charset=utf-8"
                    elif target_file.suffix.lower() == ".svg":
                        mime_type = "image/svg+xml"

                    raw_bytes = target_file.read_bytes()
                    if target_file.name == "index.html":
                        html_str = raw_bytes.decode("utf-8", errors="replace")
                        desktop_flag = "<script>window.__LAYOUTLINGUA_DESKTOP__=true;</script>"
                        if "</head>" in html_str and "__LAYOUTLINGUA_DESKTOP__" not in html_str:
                            html_str = html_str.replace("</head>", f"{desktop_flag}</head>", 1)
                            raw_bytes = html_str.encode("utf-8")

                    try:
                        self.send_response(200)
                        self._send_cors_headers()
                        self.send_header("Content-Type", mime_type or "application/octet-stream")
                        self.send_header("Content-Length", str(len(raw_bytes)))
                        self.end_headers()
                        self.wfile.write(raw_bytes)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
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

        if content_length > MAX_UPLOAD_BYTES:
            self._send_json({"error": "Payload exceeds maximum allowed upload size (100 MB)."}, status=413)
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

                # Detect source language across 17 languages (scripts + stopwords)
                sample_text = ""
                for p in doc[: min(5, len(doc))]:
                    sample_text += p.get_text() + " "

                from layoutlingua.processing.text_sanitizer import detect_language_from_text
                detected_lang = detect_language_from_text(sample_text)

                # Deterministic document identity: honor sanitized client-provided id, else hash of content
                requested_doc_id = _sanitize_doc_id(
                    urllib.parse.unquote(self.headers.get("X-Doc-Id", "") or "")
                )
                content_hash_id = hashlib.sha256(pdf_bytes).hexdigest()[:12]
                lookup_id = requested_doc_id or content_hash_id

                # Reuse an existing persisted session for the same document (same id/filename,
                # same size and multi-page) so reopening never duplicates translation work
                existing = _find_persisted_session(lookup_id, filename)
                if (
                    existing
                    and existing.get("parser_version") == PARSER_VERSION
                    and existing.get("page_count") == page_count
                    and page_count > 1
                    and len(existing.get("source_pdf_bytes") or b"") == len(pdf_bytes)
                ):
                    self._send_json({
                        "id": existing.get("doc_id", lookup_id),
                        "name": existing.get("filename", filename),
                        "size": len(pdf_bytes),
                        "page_count": existing.get("page_count", page_count),
                        "word_count": total_words,
                        "detected_lang": existing.get("detected_lang", detected_lang),
                        "is_scanned": existing.get("is_scanned", is_scanned),
                        "scan_warning": existing.get("scan_warning", ""),
                        "pages": pages_info,
                    })
                    return

                doc_id = lookup_id

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
                        "parser_version": PARSER_VERSION,
                        "filename": filename,
                        "source_pdf_bytes": pdf_bytes,
                        "doc_ir": doc_ir,
                        "page_count": page_count,
                        "translated_pdf_bytes": None,
                        "translated_page_pdfs": {},
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
                    new_session_ref = _SESSIONS[doc_id]
                _persist_session_to_disk(new_session_ref)

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

                # Same-language runs are almost certainly a misconfiguration and
                # would silently replace every page with a no-op copy (destroying
                # an existing translation). Fail loudly instead.
                req_target = str(req_json.get("target_lang", "")).strip().lower()
                req_source = str(req_json.get("source_lang", "")).strip().lower()
                effective_source = req_source if req_source and req_source != "auto" else str(session.get("detected_lang", "en")).lower()
                if req_target and req_target == effective_source:
                    self._send_json(
                        {
                            "error": (
                                f"Target language ({req_target}) matches the document language. "
                                "Pick a different target language in the language selector - a same-language "
                                "run would replace the document with an untranslated copy."
                            )
                        },
                        status=400,
                    )
                    return

                job_id = uuid.uuid4().hex[:12]
                effective_target = req_target or str(session.get("target_lang") or "vi").lower()

                with _LOCK:
                    if (
                        session.get("is_translating")
                        and not session.get("cancel_requested")
                        and str(session.get("target_lang") or "").lower() == effective_target
                        and session.get("active_job_id")
                    ):
                        self._send_json({
                            "status": "processing",
                            "doc_id": doc_id,
                            "job_id": session.get("active_job_id"),
                            "target_lang": effective_target,
                            "message": "Translation already in progress",
                        })
                        return

                    session["active_job_id"] = job_id
                    session["is_translating"] = True
                    session["cancel_requested"] = False
                    session["target_lang"] = effective_target
                    # Clear previous run's translated artifacts so the UI never displays stale pages from a prior target language
                    old_cached_doc = session.pop("_cached_trans_doc", None)
                    if old_cached_doc is not None and not getattr(old_cached_doc, "is_closed", True):
                        try:
                            old_cached_doc.close()
                        except Exception:
                            pass
                    session["translated_pdf_bytes"] = None
                    session["translated_page_pdfs"] = {}
                    session["page_results"] = {}
                    session["translated_segments"] = {}
                    session["issues"] = []
                    session.pop("integrity", None)
                    session["_disk_mtime"] = 0.0
                    canonical_id = str(session.get("doc_id") or doc_id)
                    stale_keys = [k for k in _PREVIEW_CACHE if k[0] == canonical_id and k[1] == "translated"]
                    for k in stale_keys:
                        del _PREVIEW_CACHE[k]
                    total_pages = len(session["doc_ir"].pages) if session.get("doc_ir") else session.get("page_count", 1)
                    session["progress"] = {
                        "job_id": job_id,
                        "target_lang": effective_target,
                        "stage_index": 0,
                        "current_page": 0,
                        "total_pages": total_pages,
                        "status": "processing",
                        "speed": 0,
                        "eta_seconds": 60,
                        "message": "Initializing background neural translation worker...",
                    }

                _clear_disk_translated_artifacts(canonical_id)

                worker_th = threading.Thread(
                    target=_run_translation_worker,
                    args=(doc_id, req_json, job_id),
                    daemon=True,
                )
                worker_th.start()

                self._send_json({
                    "status": "processing",
                    "doc_id": doc_id,
                    "job_id": job_id,
                    "target_lang": effective_target,
                    "total_pages": total_pages,
                    "message": "Translation job started",
                })
            except Exception as e:
                import traceback

                traceback.print_exc()
                self._send_json({"error": f"Failed to start translation: {e}"}, status=500)
            return

        # 2b. Cancel an active translation job (pages already translated are kept)
        if path in ("/api/cancel", "/cancel"):
            try:
                cancel_body = json.loads(post_body.decode("utf-8")) if post_body else {}
            except Exception:
                cancel_body = {}
            cancel_doc_id = str(cancel_body.get("doc_id") or "")
            with _LOCK:
                cancel_session = _SESSIONS.get(cancel_doc_id)
                if cancel_session is not None:
                    cancel_session["cancel_requested"] = True
                    cancel_session["is_translating"] = False
            self._send_json({"status": "cancelled"})
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

                session = _get_or_recover_session(doc_id)

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

                # Windows OneDrive folder redirection fallback (TS parity): if the
                # resolved path does not exist, ~/OneDrive/<basename> wins when it does.
                if not os.path.isdir(dest_dir):
                    one_drive_candidate = os.path.join(
                        os.path.expanduser("~"), "OneDrive", os.path.basename(dest_dir.rstrip("/\\"))
                    )
                    if os.path.isdir(one_drive_candidate):
                        dest_dir = one_drive_candidate

                norm_dir = os.path.normpath(os.path.abspath(dest_dir))
                if not _is_safe_export_directory(norm_dir):
                    self._send_json(
                        {"error": "Export directory must be inside your user home or workspace directory."},
                        status=403,
                    )
                    return
                os.makedirs(norm_dir, exist_ok=True)

                clean_filename = re.sub(r'[\r\n/\\:*?"<>|]', '_', file_name)

                # Generate content
                if export_fmt in ("md", "markdown"):
                    from layoutlingua.processing.markdown_export import export_document_markdown

                    doc_ir_obj = session.get("doc_ir") or _ensure_session_doc_ir(session)
                    md_text = export_document_markdown(
                        doc_ir=doc_ir_obj,
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
                if target_p and sys.platform == "win32":
                    norm = os.path.normpath(os.path.abspath(target_p))
                    if _is_safe_export_directory(norm):
                        if os.path.isfile(norm):
                            subprocess.Popen(["explorer.exe", f"/select,{norm}"])
                        elif os.path.isdir(norm) and hasattr(os, "startfile"):
                            os.startfile(norm)
                self._send_json({"status": "ok"})
            except Exception as e:
                self._send_json({"error": f"Failed to open folder: {e}"}, status=500)
            return

        # 5. Test translation provider connectivity & placeholder preservation
        if path in ("/api/test-provider", "/test-provider"):
            try:
                req_json = json.loads(post_body.decode("utf-8")) if post_body else {}
            except Exception:
                req_json = {}

            t0 = time.time()
            try:
                provider_inst = _instantiate_provider(req_json)
                src_lang = str(req_json.get("source_lang") or "en").strip() or "en"
                if src_lang == "auto":
                    src_lang = "en"
                tgt_lang = str(req_json.get("target_lang") or "vi").strip() or "vi"
                if tgt_lang == src_lang:
                    tgt_lang = "vi" if src_lang != "vi" else "en"

                from layoutlingua.processing.formula.models import TextSegment
                from layoutlingua.translation.models import BatchTranslationRequest

                sample_seg = TextSegment(
                    segment_id="test_1",
                    raw_text="Theorem 1: Let x = 0.",
                    masked_text="Theorem 1: Let <b0></b0>.",
                    tokens=[],
                    span_ids=[],
                )
                batch_req = BatchTranslationRequest(
                    batch_id="test_batch",
                    segments=(sample_seg,),
                    source_language=src_lang,
                    target_language=tgt_lang,
                )
                batch_res = provider_inst.translate_batch(batch_req)
                translated = batch_res.translations.get("test_1", "")
                latency_ms = int(round((time.time() - t0) * 1000))
                if not translated:
                    raise ValueError("Provider returned an empty translation response.")

                self._send_json({
                    "status": "ok",
                    "provider": provider_inst.name,
                    "model": provider_inst.model,
                    "sample_input": sample_seg.masked_text,
                    "sample_output": translated,
                    "formula_preserved": "<b0></b0>" in translated,
                    "latency_ms": latency_ms,
                    "message": f"Connected to {provider_inst.name} ({provider_inst.model}) in {latency_ms} ms",
                })
            except Exception as err:
                latency_ms = int(round((time.time() - t0) * 1000))
                self._send_json({
                    "status": "error",
                    "error_type": type(err).__name__,
                    "latency_ms": latency_ms,
                    "message": str(err),
                })
            return

        # 6. Install Argos offline runtime and/or language packages
        if path in ("/api/argos/install", "/argos/install"):
            try:
                req_json = json.loads(post_body.decode("utf-8")) if post_body else {}
            except Exception:
                req_json = {}

            try:
                import importlib
                from layoutlingua.translation.argos.manager import ArgosModelManager

                mgr = ArgosModelManager()
                install_runtime = bool(req_json.get("install_runtime", True))
                from_code = str(req_json.get("from_code") or "").strip()
                to_code = str(req_json.get("to_code") or "").strip()

                if not mgr.is_runtime_available() and install_runtime:
                    pip_res = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "argostranslate"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    importlib.invalidate_caches()
                    if pip_res.returncode != 0 and not mgr.is_runtime_available():
                        err_out = (pip_res.stderr or pip_res.stdout or "pip install failed").strip()[-400:]
                        raise RuntimeError(f"Failed to install argostranslate runtime: {err_out}")

                installed_route_desc = ""
                if from_code and to_code:
                    route = mgr.plan_route(from_code, to_code)
                    if route is None:
                        raise ValueError(
                            f"No offline translation route available for '{from_code}' -> '{to_code}' in Argos catalog."
                        )
                    mgr.ensure_route_installed(route)
                    installed_route_desc = route.describe()

                installed = [
                    {
                        "from_code": m.from_code,
                        "to_code": m.to_code,
                        "package_name": m.package_name,
                        "version": m.version,
                    }
                    for m in mgr.list_installed_models()
                ]
                self._send_json({
                    "status": "ok",
                    "runtime_available": mgr.is_runtime_available(),
                    "installed_models": installed,
                    "route": installed_route_desc,
                    "message": (
                        f"Offline package installed ({installed_route_desc})."
                        if installed_route_desc
                        else "Argos offline translation runtime is ready."
                    ),
                })
            except Exception as err:
                self._send_json({
                    "status": "error",
                    "message": str(err),
                }, status=400)
            return

        self._send_json({"error": f"Unknown POST endpoint: {path}"}, status=404)



def start_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Start the LayoutLingua API server."""
    ThreadingHTTPServer.request_queue_size = 128
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), LayoutLinguaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[LayoutLingua] Server running at http://{host}:{port}/")
    return server


def main() -> None:
    """Run the LayoutLingua server as a standalone process."""
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PYTHON_ENGINE_PORT") or os.environ.get("PORT") or "8765")
    ThreadingHTTPServer.request_queue_size = 128
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), LayoutLinguaHandler)
    print(f"[LayoutLingua] Local API Server listening on http://{host}:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LayoutLingua] Server stopped.")


if __name__ == "__main__":
    main()
