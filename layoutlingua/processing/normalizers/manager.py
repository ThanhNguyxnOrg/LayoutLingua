"""Text normalization manager coordinating encoding and Unicode normalizers."""

from __future__ import annotations

from typing import Any

from layoutlingua.core.ir import GlyphSpan
from layoutlingua.processing.normalizers.base import BaseTextNormalizer, NormalizationResult
from layoutlingua.processing.normalizers.legacy_vietnamese import VietnameseLegacyNormalizer
from layoutlingua.processing.normalizers.unicode_nfc import UnicodeNFCNormalizer


class TextNormalizationManager:
    """Coordinates text normalizers in priority sequence.

    Default Pipeline:
    1. VietnameseLegacyNormalizer (Decodes 8-bit VNI/TCVN3 into standard characters)
    2. UnicodeNFCNormalizer (Composes dual diacritics into canonical NFC form)
    """

    def __init__(self, normalizers: list[BaseTextNormalizer] | None = None) -> None:
        if normalizers is not None:
            self.normalizers = list(normalizers)
        else:
            self.normalizers = [
                VietnameseLegacyNormalizer(),
                UnicodeNFCNormalizer(),
            ]

    def normalize_text(
        self,
        text: str,
        font_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NormalizationResult:
        """Run text through all applicable normalizers in order."""
        if not text:
            return NormalizationResult(text="", applied=False)

        current_text = text
        any_applied = False
        detected_encodings: list[str] = []
        all_warnings: list[str] = []

        for norm in self.normalizers:
            if norm.should_apply(current_text, font_name=font_name, metadata=metadata):
                res = norm.normalize(current_text, font_name=font_name, metadata=metadata)
                current_text = res.text
                if res.applied:
                    any_applied = True
                if res.encoding_detected:
                    detected_encodings.append(res.encoding_detected)
                if res.warnings:
                    all_warnings.extend(res.warnings)

        return NormalizationResult(
            text=current_text,
            applied=any_applied,
            encoding_detected=" + ".join(detected_encodings) if detected_encodings else None,
            warnings=all_warnings,
        )

    def normalize_span(self, span: GlyphSpan) -> GlyphSpan:
        """Normalize the text within a GlyphSpan, updating text and recording normalization."""
        res = self.normalize_text(span.text, font_name=span.font_name)
        span.text = res.text
        return span
