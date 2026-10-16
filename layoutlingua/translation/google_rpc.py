"""Google Web / RPC translation provider for high-quality, zero-key natural language translation."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Dict, List

from layoutlingua.translation.errors import ProviderUnavailableError
from layoutlingua.translation.models import (
    BatchTranslationRequest,
    BatchTranslationResult,
    ProviderCapabilities,
)
from layoutlingua.translation.provider import BaseTranslationProvider

_TOKEN_CLEANUP = re.compile(r"⟦\s*LL_FORMULA_(\d+)\s*⟧")
_XML_CLEANUP = re.compile(r"<\s*b(\d+)\s*>\s*<\s*/\s*b\1\s*>")
_MAX_CHUNK_CHARS = 3000


def _sanitize_translated_tokens(text: str) -> str:
    """Fix any accidental spaces inserted into formula preservation tokens by MT engines."""
    res = _TOKEN_CLEANUP.sub(r"⟦LL_FORMULA_\1⟧", text)
    res = _XML_CLEANUP.sub(r"<b\1></b\1>", res)
    return res


def _split_into_chunks(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> List[str]:
    """Split long text into sentences or smaller chunks to comply with query length limits."""
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for s in sentences:
        if current_len + len(s) > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [s]
            current_len = len(s)
        else:
            current_chunk.append(s)
            current_len += len(s)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks or [text]


class GoogleRpcTranslationProvider(BaseTranslationProvider):
    """Zero-key online neural translation provider using Google's translation service.

    Translates natural language text directly into authentic target language (e.g. Vietnamese)
    while strictly preserving mathematical formula placeholder tokens and supporting auto-retry.
    """

    def __init__(self, user_agent: str = "Mozilla/5.0", max_retries: int = 2) -> None:
        self._user_agent = user_agent
        self._max_retries = max_retries
        self._capabilities = ProviderCapabilities(
            supports_structured_json=False,
            requires_data_use_consent=False,
            tier="free_online",
            policy_version="1.0",
            max_batch_segments=50,
            max_batch_chars=8000,
            requests_per_minute=300.0,
        )

    @property
    def name(self) -> str:
        return "google_rpc"

    @property
    def model(self) -> str:
        return "google-nmt-web"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    def _fetch_single_chunk(self, chunk: str, s_lang: str, t_lang: str) -> str:
        encoded = urllib.parse.quote(chunk)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={s_lang}&tl={t_lang}&dt=t&q={encoded}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self._user_agent,
                "Accept": "*/*",
            },
        )

        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    parts: List[str] = []
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                        for item in data[0]:
                            if isinstance(item, list) and len(item) > 0 and item[0]:
                                parts.append(str(item[0]))
                    return "".join(parts) if parts else chunk
            except Exception as e:
                last_err = e
                if attempt < self._max_retries:
                    time.sleep(0.4 * (attempt + 1))

        raise ProviderUnavailableError(f"Google RPC network error after retries: {last_err}")

    def _translate_single(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not text.strip():
            return text

        # Map language codes
        s_lang = "auto" if src_lang in ("auto", "") else src_lang
        t_lang = "vi" if tgt_lang in ("vi", "vietnamese") else tgt_lang
        if s_lang == "english":
            s_lang = "en"

        chunks = _split_into_chunks(text)
        translated_chunks: List[str] = []

        for ch in chunks:
            translated_part = self._fetch_single_chunk(ch, s_lang, t_lang)
            translated_chunks.append(translated_part)

        full_translated = " ".join(translated_chunks) if len(translated_chunks) > 1 else translated_chunks[0]
        return _sanitize_translated_tokens(full_translated)

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        translations: Dict[str, str] = {}
        for seg in request.segments:
            raw_text = seg.masked_text
            try:
                translated = self._translate_single(
                    text=raw_text,
                    src_lang=request.source_language,
                    tgt_lang=request.target_language,
                )
                translations[seg.segment_id] = translated
            except Exception:
                # If a single segment fails or network drops, fallback to segment text
                translations[seg.segment_id] = raw_text

        return BatchTranslationResult(
            translations=translations,
        )
