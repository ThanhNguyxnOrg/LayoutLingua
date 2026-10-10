"""Unit tests for Heading and Math connector lookup and TextNormalizerRegistry."""

from __future__ import annotations

import unittest

from layoutlingua.converter import preferred_translation, replace_math_connectors
from layoutlingua.normalizers import (
    TextNormalizerRegistry,
    UnicodeNFCNormalizer,
    VietnameseLegacyNormalizer,
    normalize_text,
)


class HeadingTranslationTests(unittest.TestCase):
    def test_multilingual_toc_headings(self) -> None:
        self.assertEqual(preferred_translation("Mục lục", "en"), "Contents")
        self.assertEqual(preferred_translation("Contents", "de"), "Inhaltsverzeichnis")
        self.assertEqual(preferred_translation("Contents", "fr"), "Sommaire")
        self.assertEqual(preferred_translation("Chỉ mục", "en"), "Index")
        self.assertEqual(preferred_translation("CHỈ MỤC", "en"), "Index")
        self.assertIsNone(preferred_translation("Some Custom Header", "en"))

    def test_math_connectors(self) -> None:
        self.assertEqual(replace_math_connectors("với mọi x", "en"), "for all x")
        self.assertEqual(replace_math_connectors("tồn tại y", "en"), "there exists y")
        self.assertEqual(replace_math_connectors("khi và chỉ khi", "en"), "if and only if")


class TextNormalizerRegistryTests(unittest.TestCase):
    def test_unicode_nfc_normalizer(self) -> None:
        norm = UnicodeNFCNormalizer()
        decomposed = "e\u0301"
        self.assertEqual(norm.normalize(decomposed), "é")

    def test_vietnamese_legacy_normalizer(self) -> None:
        norm = VietnameseLegacyNormalizer()
        self.assertTrue(norm.should_apply("Vôùi moïi x", "VNI-Times"))
        self.assertEqual(norm.normalize("Vôùi"), "Với")
        self.assertEqual(norm.normalize("nghieäm ñuùng"), "nghiệm đúng")
        self.assertEqual(norm.normalize("vo ânghieäm"), "vô nghiệm")
        self.assertEqual(norm.normalize("trong ñoù"), "trong đó")
        self.assertEqual(norm.normalize("trong ño ù"), "trong đó")

    def test_global_normalize_text(self) -> None:
        raw = "Vôùi moïi x trong ño ù"
        cleaned = normalize_text(raw)
        self.assertEqual(cleaned, "Với mọi x trong đó")

    def test_registry_instance(self) -> None:
        reg = TextNormalizerRegistry.get_instance()
        self.assertGreaterEqual(len(reg.normalizers), 2)


if __name__ == "__main__":
    unittest.main()
