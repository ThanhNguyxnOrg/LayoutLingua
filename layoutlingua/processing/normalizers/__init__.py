"""Text and encoding normalization sub-package."""

from layoutlingua.processing.normalizers.base import BaseTextNormalizer, NormalizationResult
from layoutlingua.processing.normalizers.legacy_vietnamese import VietnameseLegacyNormalizer
from layoutlingua.processing.normalizers.manager import TextNormalizationManager
from layoutlingua.processing.normalizers.unicode_nfc import UnicodeNFCNormalizer

__all__ = [
    "BaseTextNormalizer",
    "NormalizationResult",
    "VietnameseLegacyNormalizer",
    "UnicodeNFCNormalizer",
    "TextNormalizationManager",
]
