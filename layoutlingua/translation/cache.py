"""Persistent on-disk segment translation cache for LayoutLingua.

Stores translated prose segments in a local SQLite database indexed by a deterministic
SHA-256 fingerprint (source_lang:target_lang:provider_model:masked_text).
Decouples translation execution from session lifecycles, enabling instant resumption,
rate-limit immunity on retries, and zero redundant API requests.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Tuple

import platformdirs

from layoutlingua.translation.models import (
    BatchTranslationRequest,
    BatchTranslationResult,
    ProviderCapabilities,
    TextSegment,
)
from layoutlingua.translation.provider import BaseTranslationProvider


def get_default_cache_path() -> Path:
    try:
        cache_dir = Path(platformdirs.user_cache_dir("layoutlingua"))
    except Exception:
        cache_dir = Path.home() / ".layoutlingua" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "translations.db"


def compute_segment_fingerprint(
    source_lang: str,
    target_lang: str,
    model_identifier: str,
    masked_text: str,
) -> str:
    key = f"{source_lang.strip().lower()}:{target_lang.strip().lower()}:{model_identifier.strip().lower()}:{masked_text.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class TranslationCache:
    """Thread-safe SQLite-backed translation cache."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else get_default_cache_path()
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS segment_cache (
                        fingerprint TEXT PRIMARY KEY,
                        source_lang TEXT NOT NULL,
                        target_lang TEXT NOT NULL,
                        model_id TEXT NOT NULL,
                        source_text TEXT NOT NULL,
                        translated_text TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cache_lookup ON segment_cache (fingerprint)"
                )
                conn.commit()
            finally:
                conn.close()

    def get_batch(
        self,
        source_lang: str,
        target_lang: str,
        model_identifier: str,
        segments: tuple[TextSegment, ...] | list[TextSegment],
    ) -> tuple[Dict[str, str], List[TextSegment]]:
        """Look up multiple segments.

        Returns:
            (cached_translations, missing_segments)
        """
        if not segments:
            return {}, []

        fp_to_seg: Dict[str, TextSegment] = {}
        for seg in segments:
            if not seg.masked_text.strip():
                continue
            fp = compute_segment_fingerprint(
                source_lang, target_lang, model_identifier, seg.masked_text
            )
            fp_to_seg[fp] = seg

        if not fp_to_seg:
            cached = {seg.segment_id: seg.masked_text for seg in segments}
            return cached, []

        cached_results: Dict[str, str] = {}
        fps = list(fp_to_seg.keys())

        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                chunk_size = 500
                for i in range(0, len(fps), chunk_size):
                    chunk = fps[i : i + chunk_size]
                    placeholders = ",".join("?" for _ in chunk)
                    cur = conn.execute(
                        f"SELECT fingerprint, translated_text FROM segment_cache WHERE fingerprint IN ({placeholders})",
                        chunk,
                    )
                    for fp, trans_text in cur.fetchall():
                        seg = fp_to_seg[fp]
                        cached_results[seg.segment_id] = trans_text
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()

        for seg in segments:
            if not seg.masked_text.strip():
                cached_results[seg.segment_id] = seg.masked_text

        missing = [seg for seg in segments if seg.segment_id not in cached_results]
        return cached_results, missing

    def put_batch(
        self,
        source_lang: str,
        target_lang: str,
        model_identifier: str,
        entries: list[Tuple[TextSegment, str]],
    ) -> None:
        """Insert or update translated segments in bulk."""
        if not entries:
            return

        rows = []
        for seg, trans_text in entries:
            if not seg.masked_text.strip():
                continue
            fp = compute_segment_fingerprint(
                source_lang, target_lang, model_identifier, seg.masked_text
            )
            rows.append(
                (
                    fp,
                    source_lang.strip().lower(),
                    target_lang.strip().lower(),
                    model_identifier.strip().lower(),
                    seg.masked_text,
                    trans_text,
                )
            )

        if not rows:
            return

        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO segment_cache 
                    (fingerprint, source_lang, target_lang, model_id, source_text, translated_text)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()


class CachedTranslationProvider(BaseTranslationProvider):
    """Deep module decorator adding persistent disk caching to any BaseTranslationProvider."""

    def __init__(
        self,
        inner_provider: BaseTranslationProvider,
        cache: TranslationCache | None = None,
    ) -> None:
        self._inner = inner_provider
        self._cache = cache if cache is not None else TranslationCache()
        self.last_cache_hits = 0
        self.last_cache_misses = 0

    @property
    def name(self) -> str:
        return f"cached_{self._inner.name}"

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._inner.capabilities

    def translate_segment(
        self,
        segment_id: str,
        text: str,
        target_lang: str,
        source_lang: str = "auto",
        context_window: str | None = None,
    ) -> str:
        dummy_seg = TextSegment(
            segment_id=segment_id,
            raw_text=text,
            masked_text=text,
            tokens=(),
        )
        req = BatchTranslationRequest(
            batch_id="single",
            source_language=source_lang,
            target_language=target_lang,
            segments=(dummy_seg,),
        )
        res = self.translate_batch(req)
        return res.translations.get(segment_id, text)

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        s_lang = request.source_language or "auto"
        t_lang = request.target_language or "vi"
        m_id = self.model

        cached_trans, missing_segs = self._cache.get_batch(
            source_lang=s_lang,
            target_lang=t_lang,
            model_identifier=m_id,
            segments=request.segments,
        )

        self.last_cache_hits = len(cached_trans)
        self.last_cache_misses = len(missing_segs)

        all_translations = dict(cached_trans)

        if missing_segs:
            miss_req = BatchTranslationRequest(
                batch_id=f"{request.batch_id}_misses",
                source_language=s_lang,
                target_language=t_lang,
                segments=tuple(missing_segs),
            )
            miss_res = self._inner.translate_batch(miss_req)
            all_translations.update(miss_res.translations)

            new_entries = []
            for seg in missing_segs:
                if seg.segment_id in miss_res.translations:
                    new_entries.append((seg, miss_res.translations[seg.segment_id]))

            if new_entries:
                self._cache.put_batch(
                    source_lang=s_lang,
                    target_lang=t_lang,
                    model_identifier=m_id,
                    entries=new_entries,
                )

        return BatchTranslationResult(translations=all_translations)
