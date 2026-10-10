"""Text normalizer pipeline for extracted PDF text.

Registers universal and language-specific encoding decoders to ensure clean
Unicode NFC text before layout analysis and translation.
"""

from __future__ import annotations

from layoutlingua.normalizers.base import BaseTextNormalizer
from layoutlingua.normalizers.legacy_vietnamese import VietnameseLegacyNormalizer
from layoutlingua.normalizers.unicode_nfc import UnicodeNFCNormalizer


class TextNormalizerRegistry:
    """Registry coordinating all text and encoding normalizers in priority order."""

    def __init__(self) -> None:
        self.normalizers: list[BaseTextNormalizer] = [
            VietnameseLegacyNormalizer(),
            UnicodeNFCNormalizer(),
        ]

    def register(self, normalizer: BaseTextNormalizer, priority: int = -1) -> None:
        if priority < 0 or priority >= len(self.normalizers):
            self.normalizers.append(normalizer)
        else:
            self.normalizers.insert(priority, normalizer)

    def normalize(self, text: str, font_name: str | None = None) -> str:
        """Run all applicable normalizers in order."""
        if not text:
            return text
        result = text
        for normalizer in self.normalizers:
            if normalizer.should_apply(result, font_name):
                result = normalizer.normalize(result)
        return result

    @classmethod
    def get_instance(cls) -> TextNormalizerRegistry:
        """Return the default global singleton registry."""
        return _DEFAULT_REGISTRY


_DEFAULT_REGISTRY = TextNormalizerRegistry()


def normalize_text(text: str, font_name: str | None = None) -> str:
    """Normalize extracted PDF text using the default normalizer registry."""
    return _DEFAULT_REGISTRY.normalize(text, font_name)


__all__ = [
    "BaseTextNormalizer",
    "TextNormalizerRegistry",
    "UnicodeNFCNormalizer",
    "VietnameseLegacyNormalizer",
    "normalize_text",
]
