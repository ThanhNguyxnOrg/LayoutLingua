"""Translation adapters for the preservation-focused PDF core."""

from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
import time
import unicodedata
from collections import Counter
from typing import Any, ClassVar

import requests

from pdf2zh.cache import TranslationCache

logger = logging.getLogger(__name__)

PLACEHOLDER_PATTERN = re.compile(r"</?b\d+>")
INTERNAL_PLACEHOLDER_PATTERN = re.compile(r"\{\s*v([\d\s]+)\}", re.IGNORECASE)
PAIRED_PLACEHOLDER_PATTERN = re.compile(r"<b(\d+)>\s*</b\1>")
STYLE_TAG_PATTERN = re.compile(r"<(/?)s([123])>", re.IGNORECASE)


class FormulaPlaceholderError(ValueError):
    """Raised when a translator damages or reorders protected formula tags."""


class RateLimiter:
    """Leaky-bucket pacing shared across translator threads and documents.

    Worker threads share one translator per document and the GUI translates
    several documents per process, so unpaced GETs from any of them throttle
    the whole run. One shared limiter paces them all with the standard
    library only.
    """

    def __init__(self, max_qps: float = 5.0) -> None:
        self._interval = 1.0 / max_qps
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._interval


_shared_rate_limiter = RateLimiter()

_CIRCUIT_THRESHOLD = 5
_CIRCUIT_COOLDOWN = 60.0
_circuit_lock = threading.Lock()
_consecutive_429s = 0
_circuit_opened_at: float | None = None


class CircuitOpenError(RuntimeError):
    """Raised when too many consecutive 429s tripped the shared breaker."""


def _circuit_allows_request() -> None:
    """Fail fast while the endpoint is known to block this IP."""
    global _consecutive_429s, _circuit_opened_at
    with _circuit_lock:
        if _circuit_opened_at is None:
            return
        if time.monotonic() - _circuit_opened_at >= _CIRCUIT_COOLDOWN:
            _circuit_opened_at = None
            _consecutive_429s = 0
            return
        raise CircuitOpenError("translation endpoint is rate-limiting this IP")


def _circuit_record_success() -> None:
    global _consecutive_429s, _circuit_opened_at
    with _circuit_lock:
        _consecutive_429s = 0
        _circuit_opened_at = None


def _circuit_record_429() -> None:
    global _consecutive_429s, _circuit_opened_at
    with _circuit_lock:
        _consecutive_429s += 1
        if _consecutive_429s >= _CIRCUIT_THRESHOLD:
            _circuit_opened_at = time.monotonic()


class SegmentTooLongError(ValueError):
    """Raised when a segment exceeds what the translation service accepts.

    Upstream truncates to the limit and returns the short answer as if it were
    the whole translation, so the tail of a long paragraph disappears with
    nothing said. A segment carrying formula or style markers is caught later
    by the marker check, but plain prose is silently cut in half. Refusing the
    segment keeps the source text and lets the caller say what happened.
    """


def remove_control_characters(value: str) -> str:
    """Remove control characters that cannot be emitted safely into PDF text."""
    return "".join(character for character in value if unicodedata.category(character)[0] != "C")


NUMBER_ABBREVIATION_PATTERN = re.compile(r"(?<![A-Za-z])no\.(?=\s*\d)")


def normalise_number_abbreviation(text: str) -> str:
    """Capitalise the ``no.`` that means "number" so it is not read as "not".

    "ref. no. 305" came back as "ref. KHONG. 305": lowercase "no." mid-sentence
    reads as the negation, and every engine we can reach makes the same choice.
    The same string capitalised is unambiguous -- "No. 305" translates to
    "So 305" -- and capitalising an abbreviation that already stands for a
    proper noun changes nothing else about the sentence.

    Only ``no.`` directly in front of a number is touched, so ordinary prose
    ("there is no. Then...") is left alone.
    """
    return NUMBER_ABBREVIATION_PATTERN.sub("No.", text)


class BaseTranslator:
    """Cache-aware translator interface consumed by the PDF converter."""

    name = "base"
    lang_map: ClassVar[dict[str, str]] = {}

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        **_: Any,
    ) -> None:
        self.lang_in = self.lang_map.get(lang_in.lower(), lang_in)
        self.lang_out = self.lang_map.get(lang_out.lower(), lang_out)
        self.model = model
        self.ignore_cache = ignore_cache
        self.cache = TranslationCache(
            self.name,
            {
                "lang_in": self.lang_in,
                "lang_out": self.lang_out,
                "model": model,
            },
        )

    def translate(self, text: str, ignore_cache: bool = False) -> str:
        """Translate text, consulting the persistent cache unless bypassed."""
        text = normalise_number_abbreviation(text)
        if not (self.ignore_cache or ignore_cache):
            cached = self.cache.get(text)
            if cached is not None:
                return cached
        translated = self.do_translate(text)
        if not (self.ignore_cache or ignore_cache):
            self.cache.set(text, translated)
        return translated

    def do_translate(self, text: str) -> str:
        """Translate one engine-sized text segment."""
        raise NotImplementedError

    def get_rich_text_left_placeholder(self, identifier: int) -> str:
        return f"<b{identifier}>"

    def get_rich_text_right_placeholder(self, identifier: int) -> str:
        return f"</b{identifier}>"

    def get_formular_placeholder(self, identifier: int) -> str:
        return self.get_rich_text_left_placeholder(identifier) + self.get_rich_text_right_placeholder(identifier)


class GoogleTranslator(BaseTranslator):
    """Translate through Google's mobile web endpoint without an API key."""

    name = "google"
    lang_map: ClassVar[dict[str, str]] = {
        "zh": "zh-CN",
        "zh-cn": "zh-CN",
        "zh-hans": "zh-CN",
        "zh-tw": "zh-TW",
        "zh-hant": "zh-TW",
        "he": "iw",
    }

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            lang_in,
            lang_out,
            model,
            ignore_cache=ignore_cache,
            **kwargs,
        )
        self.session = requests.Session()
        self.endpoint = "https://translate.google.com/m"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            )
        }

    def _throttle(self) -> None:
        _shared_rate_limiter.wait()

    # The /m endpoint carries the text in the query string and rejects more
    # than this; it is the service's limit, not a preference.
    MAXIMUM_SEGMENT_CHARACTERS = 5000

    def do_translate(self, text: str) -> str:
        if len(text) > self.MAXIMUM_SEGMENT_CHARACTERS:
            raise SegmentTooLongError(
                f"segment of {len(text)} characters exceeds the "
                f"{self.MAXIMUM_SEGMENT_CHARACTERS} the service accepts"
            )
        self._throttle()
        _circuit_allows_request()
        response = self.session.get(
            self.endpoint,
            params={"tl": self.lang_out, "sl": self.lang_in, "q": text},
            headers=self.headers,
            timeout=30,
        )
        if response.status_code == 400:
            raise RuntimeError("Google Translate rejected the text segment")
        try:
            response.raise_for_status()
        except requests.HTTPError:
            if response.status_code == 429:
                _circuit_record_429()
            raise
        _circuit_record_success()
        match = re.search(
            r'(?s)class="(?:t0|result-container)">(.*?)<',
            response.text,
        )
        if match is None:
            raise RuntimeError("Google Translate response did not contain a translation result")
        return remove_control_characters(html.unescape(match.group(1)))


class DeepLXTranslator(BaseTranslator):
    """Translate through a self-hosted DeepLX endpoint (no browser scraping).

    DeepLX ignores ``tag_handling``, so formula/style markers may come back
    damaged; the converter's validators still reject such output and keep
    the source text, exactly as with every other engine.
    """

    name = "deeplx"
    lang_map: ClassVar[dict[str, str]] = {
        "zh": "ZH",
        "zh-cn": "ZH",
        "zh-hans": "ZH",
        "zh-tw": "ZH-HANT",
        "zh-hant": "ZH-HANT",
        "en": "EN",
        "pt": "PT",
    }
    source_lang_map: ClassVar[dict[str, str]] = {
        "en": "en",
        "pt": "pt",
        "zh": "zh",
        "zh-cn": "zh",
        "zh-hans": "zh",
        "zh-tw": "zh",
        "zh-hant": "zh",
    }

    # Anonymous oneshot limit enforced by DeepLX itself; refuse overlong
    # segments instead of letting the endpoint truncate them silently.
    MAXIMUM_SEGMENT_CHARACTERS = 1500

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            lang_in,
            lang_out,
            model,
            ignore_cache=ignore_cache,
            **kwargs,
        )
        self.session = requests.Session()
        self.endpoint = os.environ.get(
            "DEEPLX_ENDPOINT", "http://localhost:1188/translate"
        )

    def _target_code(self) -> str:
        return self.lang_map.get(self.lang_out.lower(), self.lang_out.upper())

    def _source_code(self) -> str:
        if self.lang_in.lower() in ("auto", ""):
            return "auto"
        return self.source_lang_map.get(self.lang_in.lower(), self.lang_in.lower())

    def _throttle(self) -> None:
        _shared_rate_limiter.wait()

    def do_translate(self, text: str) -> str:
        if len(text) > self.MAXIMUM_SEGMENT_CHARACTERS:
            raise SegmentTooLongError(
                f"segment of {len(text)} characters exceeds the "
                f"{self.MAXIMUM_SEGMENT_CHARACTERS} the service accepts"
            )
        self._throttle()
        _circuit_allows_request()
        response = self.session.post(
            self.endpoint,
            json={
                "text": text,
                "source_lang": self._source_code(),
                "target_lang": self._target_code(),
            },
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            if response.status_code == 429:
                _circuit_record_429()
            raise
        _circuit_record_success()
        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError("DeepLX response was not JSON") from error
        if not isinstance(payload, dict) or payload.get("code") != 200:
            raise RuntimeError(
                f"DeepLX rejected the text segment: {payload!r:.120}"
                if isinstance(payload, dict)
                else f"DeepLX returned an unexpected payload: {payload!r:.120}"
            )
        return remove_control_characters(str(payload.get("data", "")))


def placeholders(text: str) -> list[str]:
    """Return the formula placeholder tags in order, e.g. ['<b0>', '</b0>']."""
    return PLACEHOLDER_PATTERN.findall(text)


def encode_formula_placeholders(text: str) -> str:
    """Turn converter-internal ``{vN}`` markers into translator-safe tag pairs."""
    return INTERNAL_PLACEHOLDER_PATTERN.sub(
        lambda match: f"<b{int(match.group(1).replace(' ', ''))}></b{int(match.group(1).replace(' ', ''))}>",
        text,
    )


def _formula_placeholder_counts(text: str) -> Counter[str]:
    """Return balanced formula placeholder-pair counts, allowing complete pairs to reorder."""
    stack: list[str] = []
    pairs: Counter[str] = Counter()
    for match in PLACEHOLDER_PATTERN.finditer(text):
        tag = match.group(0)
        closing = tag.startswith("</")
        identifier = re.search(r"\d+", tag).group(0)
        if not closing:
            stack.append(identifier)
            continue
        if not stack or stack[-1] != identifier:
            raise FormulaPlaceholderError("formula placeholders are malformed or cross-nested")
        stack.pop()
        pairs[identifier] += 1
    if stack:
        raise FormulaPlaceholderError("formula placeholders are not closed")
    return pairs


def validate_formula_placeholders(source: str, translated: str) -> None:
    """Require all formula placeholders to be preserved in balanced pairs, allowing natural grammar reordering."""
    if _formula_placeholder_counts(source) != _formula_placeholder_counts(translated):
        raise FormulaPlaceholderError("formula placeholders changed during translation")


def restore_formula_placeholders(source: str, translated: str) -> str:
    """Validate translator output and restore its tags to converter markers."""
    from pdf2zh.formula import normalize_mt_placeholders

    translated = normalize_mt_placeholders(translated)
    encoded_source = encode_formula_placeholders(source)
    validate_formula_placeholders(encoded_source, translated)
    validate_style_tags(encoded_source, translated)
    restored = PAIRED_PLACEHOLDER_PATTERN.sub(
        lambda match: f"{{v{match.group(1)}}}", translated
    )
    if PLACEHOLDER_PATTERN.search(restored):
        raise FormulaPlaceholderError("formula placeholder pair is malformed")
    return restored


def _style_tag_counts(text: str) -> Counter[str]:
    """Return balanced style-pair counts, allowing complete pairs to reorder."""
    stack: list[str] = []
    pairs: Counter[str] = Counter()
    for match in STYLE_TAG_PATTERN.finditer(text):
        closing, identifier = match.groups()
        if not closing:
            stack.append(identifier)
            continue
        if not stack or stack[-1] != identifier:
            raise FormulaPlaceholderError("style tags are malformed or cross-nested")
        stack.pop()
        pairs[identifier] += 1
    if stack:
        raise FormulaPlaceholderError("style tags are not closed")
    return pairs


def validate_style_tags(source: str, translated: str) -> None:
    """Require the same balanced bold/italic runs after translation."""
    if _style_tag_counts(source) != _style_tag_counts(translated):
        raise FormulaPlaceholderError("style tags changed during translation")


def load_segment_table(path: str | None) -> dict[str, str]:
    """Load a source-to-translation table from a JSONL file of {"src", "dst"} records.

    Entries whose translation dropped or reordered a formula placeholder are
    skipped, so the next pass re-emits them instead of silently losing a formula.
    """
    if not path:
        return {}
    table: dict[str, str] = {}
    with open(path, encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                source, translation = record["src"], record["dst"]
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(
                    f"{path} line {number}: expected a JSON object with 'src' and 'dst'"
                ) from error
            if not isinstance(source, str) or not isinstance(translation, str):
                raise ValueError(f"{path} line {number}: 'src' and 'dst' must be strings")
            if not translation:
                continue
            # Old converter versions emitted {vN}; normalise those records so
            # existing handoff files remain usable with the documented tags.
            source = encode_formula_placeholders(source)
            translation = encode_formula_placeholders(translation)
            try:
                validate_formula_placeholders(source, translation)
            except FormulaPlaceholderError:
                logger.warning(
                    "%s line %d: formula placeholders differ between src and dst; "
                    "segment left untranslated",
                    path,
                    number,
                )
                continue
            try:
                validate_style_tags(source, translation)
            except FormulaPlaceholderError:
                logger.warning(
                    "%s line %d: style tags differ between src and dst; "
                    "segment left untranslated",
                    path,
                    number,
                )
                continue
            table[source] = translation
    return table


class HandoffTranslator(BaseTranslator):
    """Translate from a table produced outside the pipeline, such as by an agent.

    Two passes: the first runs with no table and records every segment it could
    not translate, the caller fills those in, and the second runs with the filled
    table to emit the real document.
    """

    name = "handoff"

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        envs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        # Misses fall through untranslated, so the shared cache must never see them
        # or "translation == original" is memoised for every later run.
        super().__init__(lang_in, lang_out, model, ignore_cache=True, **kwargs)
        envs = envs or {}
        self.table = load_segment_table(envs.get("segments_in"))
        self.misses_path = envs.get("segments_out")
        self._seen: set[str] = set()
        self._lock = threading.Lock()
        if self.misses_path:
            open(self.misses_path, "w", encoding="utf-8").close()

    def do_translate(self, text: str) -> str:
        translation = self.table.get(text)
        if translation is not None:
            return translation
        self._record_miss(text)
        return text

    def _record_miss(self, text: str) -> None:
        """Append one untranslated segment, deduplicated, for the caller to fill in."""
        if not self.misses_path:
            return
        with self._lock:
            if text in self._seen:
                return
            self._seen.add(text)
            with open(self.misses_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps({"src": text}, ensure_ascii=False) + "\n")


ENGINES: dict[str, type[BaseTranslator]] = {
    engine.name: engine
    for engine in (GoogleTranslator, DeepLXTranslator, HandoffTranslator)
}
