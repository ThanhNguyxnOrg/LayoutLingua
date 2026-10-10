"""Canonical Unicode NFC normalizer applied universally across all languages."""

from __future__ import annotations

import unicodedata

from layoutlingua.normalizers.base import BaseTextNormalizer


class UnicodeNFCNormalizer(BaseTextNormalizer):
    """Normalizes all extracted text to standard Unicode NFC (composed) form."""

    def should_apply(self, text: str, font_name: str | None = None) -> bool:
        return bool(text)

    def normalize(self, text: str) -> str:
        if not text:
            return text
        return unicodedata.normalize("NFC", text)
