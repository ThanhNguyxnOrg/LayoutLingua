"""Canonical Unicode NFC normalizer.

Ensures that decomposed Unicode characters (e.g., NFD diacritics common on macOS)
are composed into canonical NFC form, preventing dual-byte diacritic fragmentation.
Maintains strict idempotency: normalize(normalize(text)) == normalize(text).
"""

from __future__ import annotations

import unicodedata
from typing import Any

from layoutlingua.processing.normalizers.base import BaseTextNormalizer, NormalizationResult


class UnicodeNFCNormalizer(BaseTextNormalizer):
    """Normalizes text into Unicode Normalization Form C (NFC)."""

    @property
    def name(self) -> str:
        return "unicode_nfc"

    def should_apply(
        self,
        text: str,
        font_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if not text:
            return False
        # Fast path check: returns True if text is not already in NFC form
        return not unicodedata.is_normalized("NFC", text)

    def normalize(
        self,
        text: str,
        font_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NormalizationResult:
        if not text:
            return NormalizationResult(text=text, applied=False)

        if unicodedata.is_normalized("NFC", text):
            return NormalizationResult(text=text, applied=False)

        normalized = unicodedata.normalize("NFC", text)
        return NormalizationResult(
            text=normalized,
            applied=True,
            encoding_detected="unicode_nfd_to_nfc",
        )
