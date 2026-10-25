"""Google Web / RPC translation provider for high-quality, zero-key natural language translation."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List

from layoutlingua.translation.errors import ProviderUnavailableError, RateLimitError
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
    """Fix any accidental spaces or malformations inserted into formula preservation tokens by MT engines."""
    # 1. ⟦LL_FORMULA_0⟧
    res = re.sub(r"⟦\s*LL_FORMULA_(\d+)\s*⟧", r"⟦LL_FORMULA_\1⟧", text)
    # 2. Complete standard tag pairs: <b0></b0> (case-insensitive)
    res = re.sub(r"<\s*b\s*(\d+)\s*>\s*<\s*/\s*b\s*\1\s*>", r"<b\1></b\1>", res, flags=re.IGNORECASE)
    # 3. Google Translate mangled tags like <b>0></b> or <b0></b> or <b0/>
    res = re.sub(r"<\s*b\s*>\s*(\d+)\s*>\s*<\s*/\s*b\s*>", r"<b\1></b\1>", res, flags=re.IGNORECASE)
    res = re.sub(r"<\s*b\s*(\d+)\s*>\s*<\s*/\s*>", r"<b\1></b\1>", res, flags=re.IGNORECASE)
    res = re.sub(r"<\s*b\s*(\d+)\s*/>", r"<b\1></b\1>", res, flags=re.IGNORECASE)
    # Protect well-formed <bN></bN> with a unique sentinel
    res = re.sub(r"<b(\d+)></b\1>", r"⟦VT_\1⟧", res, flags=re.IGNORECASE)
    # Any remaining stray <bN> or </bN> is converted to sentinel
    res = re.sub(r"<\s*/?\s*b\s*(\d+)\s*>", r"⟦VT_\1⟧", res, flags=re.IGNORECASE)
    # Restore sentinels to canonical <bN></bN>
    res = re.sub(r"⟦VT_(\d+)⟧", r"<b\1></b\1>", res)
    # 4. Collapse consecutive duplicate tokens
    res = re.sub(r"(<b\d+></b\d+>)(?:\s*\1)+", r"\1", res)
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
        # Pool of Google endpoints & clients. The `at` client with the Android
        # Translate app UA is the most token-stable combination (pdf2zh pattern):
        # it preserves spacing around inline formula placeholders far better than
        # the web gtx client, which glues words and corrupts Vietnamese diacritics
        # on masked segments. dict-chrome-ex uses extension quota which bypasses
        # web gtx rate-limits.
        at_mirrors = [
            "https://translate.google.com/translate_a/single?client=at&dt=t",
            "https://translate.google.com.vn/translate_a/single?client=at&dt=t",
            "https://translate.google.de/translate_a/single?client=at&dt=t",
            "https://translate.google.co.jp/translate_a/single?client=at&dt=t",
        ]
        android_ua = "AndroidTranslate/6.29.0.05.421280910 (Linux; U; Android 11; Pixel 5)"

        last_err: Exception | None = None
        rate_limited_count = 0

        post_data = urllib.parse.urlencode({
            "sl": s_lang,
            "tl": t_lang,
            "dt": "t",
            "q": chunk,
        }).encode("utf-8")

        parsed_result = None

        # Tier 1: client=at mirrors with the Android Translate UA (TS-parity)
        for endpoint in at_mirrors:
            req = urllib.request.Request(
                endpoint,
                data=post_data,
                headers={
                    "User-Agent": android_ua,
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    parts: List[str] = []
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                        for item in data[0]:
                            if isinstance(item, list) and len(item) > 0 and item[0]:
                                parts.append(str(item[0]))
                    text = "".join(parts)
                    if text.strip():
                        return _sanitize_translated_tokens(text)
            except urllib.error.HTTPError as he:
                last_err = he
                if he.code in (429, 403):
                    rate_limited_count += 1
            except Exception as exc:
                last_err = exc

        # Tier 2: googleapis gtx GET (single URL-encoded request)
        try:
            url = (
                "https://translate.googleapis.com/translate_a/single?client=gtx"
                f"&sl={urllib.parse.quote(s_lang)}&tl={urllib.parse.quote(t_lang)}"
                f"&dt=t&q={urllib.parse.quote(chunk)}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": android_ua, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                    parts = [str(item[0]) for item in data[0] if isinstance(item, list) and item[0]]
                    text = "".join(parts)
                    if text.strip():
                        return _sanitize_translated_tokens(text)
        except Exception as exc:
            last_err = exc

        # Tier 3: legacy form-POST pool
        endpoints = [
            ("translate.googleapis.com", "gtx"),
            ("translate.googleapis.com", "dict-chrome-ex"),
            ("translate.google.com", "gtx"),
            ("translate.google.com", "dict-chrome-ex"),
        ]

        for host, client in endpoints:
            url = f"https://{host}/translate_a/single?client={client}"
            req = urllib.request.Request(
                url,
                data=post_data,
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                },
            )
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
                except urllib.error.HTTPError as he:
                    last_err = he
                    if he.code in (429, 403):
                        rate_limited_count += 1
                        # Break immediately to try next endpoint in the pool
                        break
                    if attempt < self._max_retries:
                        time.sleep(0.3 * (attempt + 1))
                except Exception as e:
                    last_err = e
                    if attempt < self._max_retries:
                        time.sleep(0.3 * (attempt + 1))

        if rate_limited_count >= len(endpoints):
            raise RateLimitError(
                "Google Translate free RPC rate limit reached (HTTP 429). "
                "The public free endpoint temporarily blocked requests from this IP. "
                "Please switch to an API provider (OpenAI, Gemini, DeepSeek, Groq) in Settings."
            )

        raise ProviderUnavailableError(f"Google RPC network error after retries: {last_err}")

    def _normalize_lang_code(self, code: str, default: str = "auto") -> str:
        """Normalize language name or code to standard 2-letter ISO code."""
        if not code or code in ("auto", ""):
            return default
        c = code.lower().strip()
        lang_map = {
            "vietnamese": "vi",
            "chinese": "zh",
            "zh-cn": "zh",
            "zh-tw": "zh",
            "japanese": "ja",
            "german": "de",
            "french": "fr",
            "spanish": "es",
            "english": "en",
            "korean": "ko",
            "russian": "ru",
        }
        return lang_map.get(c, c[:2] if len(c) > 2 else c)

    def _translate_single(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not text.strip():
            return text

        s_lang = self._normalize_lang_code(src_lang, "auto")
        t_lang = self._normalize_lang_code(tgt_lang, "vi")

        chunks = _split_into_chunks(text)
        translated_chunks: List[str] = []

        for ch in chunks:
            translated_part = self._fetch_single_chunk(ch, s_lang, t_lang)
            translated_chunks.append(translated_part)

        full_translated = " ".join(translated_chunks) if len(translated_chunks) > 1 else translated_chunks[0]
        return _sanitize_translated_tokens(full_translated)

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        translations: Dict[str, str] = {}
        s_lang = self._normalize_lang_code(request.source_language, "auto")
        t_lang = self._normalize_lang_code(request.target_language, "vi")

        # One segment per request. Packing multiple segments with a delimiter
        # corrupts formula placeholders: Google mangles or substitutes the
        # <bN></bN> tags of every segment after the first (verified A/B), which
        # is the root cause of shattered inline formulas. Segment-level requests
        # preserve the placeholders exactly (A/B verified). The rate limiter in
        # TranslationService paces the extra round-trips.
        for seg in request.segments:
            raw_text = seg.masked_text
            if not raw_text.strip():
                translations[seg.segment_id] = raw_text
                continue
            try:
                translations[seg.segment_id] = self._translate_single(raw_text, s_lang, t_lang)
            except RateLimitError:
                raise
            except Exception:
                # One more retry after a brief pause; fail-closed to the masked source
                try:
                    time.sleep(0.5)
                    translations[seg.segment_id] = self._translate_single(raw_text, s_lang, t_lang)
                except Exception:
                    translations[seg.segment_id] = raw_text

        return BatchTranslationResult(translations=translations)
