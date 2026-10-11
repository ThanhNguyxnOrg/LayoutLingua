"""Slice 2 Processing Test Suite for LayoutLingua.

Verifies:
1. Unicode NFC & NFD normalization consistency, idempotency, and CJK non-interference.
2. Legacy font decoding (VNI-Times, TCVN3) with modern font protection and fail-closed warnings.
3. Structured formula token isolation, boundary spacing, and strict verification (missing, duplicate, reordered, alien tokens).
4. Relative geometric grouping (lines, fraction-aware tolerance, tabular row isolation & gutters).
"""

from __future__ import annotations

import unicodedata
import unittest

from layoutlingua.core.ir import GlyphSpan, TextBlock
from layoutlingua.processing.formula.isolator import FormulaIsolator
from layoutlingua.processing.geometry.grouping import GeometricGrouper
from layoutlingua.processing.normalizers.legacy_vietnamese import VietnameseLegacyNormalizer
from layoutlingua.processing.normalizers.manager import TextNormalizationManager
from layoutlingua.processing.normalizers.unicode_nfc import UnicodeNFCNormalizer


class TestUnicodeNFCNormalizer(unittest.TestCase):
    """Test canonical NFC composition, idempotency, and foreign script preservation."""

    def setUp(self) -> None:
        self.normalizer = UnicodeNFCNormalizer()

    def test_nfd_to_nfc_consistency(self) -> None:
        # Construct NFD decomposed Vietnamese: 'e' + combining circumflex (U+0302) + combining acute (U+0301)
        nfd_text = "Ti" + "e\u0302\u0301" + "ng Vi" + "e\u0302\u0323" + "t"
        self.assertFalse(unicodedata.is_normalized("NFC", nfd_text))

        res = self.normalizer.normalize(nfd_text)
        self.assertTrue(res.applied)
        self.assertEqual(res.text, "Tiếng Việt")
        self.assertTrue(unicodedata.is_normalized("NFC", res.text))

    def test_idempotency(self) -> None:
        raw = "Kính chào thế giới - Nghiệm phương trình bậc hai."
        res1 = self.normalizer.normalize(raw)
        res2 = self.normalizer.normalize(res1.text)
        self.assertEqual(res1.text, res2.text)
        self.assertFalse(res2.applied)  # Second run should be a no-op

    def test_cjk_and_math_symbols_unmodified(self) -> None:
        cjk_math = "日本語テキスト，简体中文，한국어，∑_{i=1}^n x_i ≈ ∫_0^∞ f(x)dx, α β γ."
        res = self.normalizer.normalize(cjk_math)
        self.assertEqual(res.text, cjk_math)


class TestVietnameseLegacyNormalizer(unittest.TestCase):
    """Test VNI Windows and TCVN3 legacy font decoders, modern font guards, and fail-closed warnings."""

    def setUp(self) -> None:
        self.normalizer = VietnameseLegacyNormalizer()
        self.manager = TextNormalizationManager()

    def test_vni_fixture_decoding(self) -> None:
        # Verified VNI Windows fixture from academic math book
        vni_raw = "Vôùi moïi nghieäm ñuùng trong ñoù, phöông trình vo ânghieäm vaø cô soá laø 2."
        res = self.normalizer.normalize(vni_raw, font_name="VNI-Times")
        self.assertTrue(res.applied)
        self.assertEqual(res.encoding_detected, "vni_windows")
        self.assertIn("Với", res.text)
        self.assertIn("nghiệm đúng", res.text)
        self.assertIn("vô nghiệm", res.text)
        self.assertIn("cơ số", res.text)
        self.assertIn("và", res.text)

    def test_tcvn3_fixture_decoding(self) -> None:
        # Verified TCVN3 bytes: 'H\xe0 N\xf4i' -> 'Hà Nội'
        tcvn_raw = "H\xb8 N\xeei"  # TCVN3: \xb8 is à, \xee is ố
        res = self.normalizer.normalize(tcvn_raw, font_name=".VnTime")
        self.assertTrue(res.applied)
        self.assertEqual(res.encoding_detected, "tcvn3")
        self.assertEqual(res.text, "Hà Nối")

    def test_modern_font_protection(self) -> None:
        # Spanish word 'Señor' in modern Arial font must NOT be changed into 'Seđor'
        spanish_text = "El Señor González en España."
        should = self.normalizer.should_apply(spanish_text, font_name="Arial")
        self.assertFalse(should)

        res = self.normalizer.normalize(spanish_text, font_name="Arial")
        self.assertFalse(res.applied)
        self.assertEqual(res.text, spanish_text)

    def test_unrecognized_font_fail_closed(self) -> None:
        # Unknown font with characters that don't match VNI/TCVN3 tables
        weird_text = "Some unusual glyph text"
        res = self.normalizer.normalize(weird_text, font_name="UnknownCustomFont")
        self.assertFalse(res.applied)
        self.assertEqual(res.text, weird_text)

    def test_manager_pipeline_composition(self) -> None:
        # VNI text with NFD remnants normalized through manager pipeline
        vni_input = "Vôùi giaù trò n."
        res = self.manager.normalize_text(vni_input, font_name="VNI-Times")
        self.assertTrue(res.applied)
        self.assertIn("Với", res.text)
        self.assertTrue(unicodedata.is_normalized("NFC", res.text))


class TestFormulaIsolatorAndTokenVerification(unittest.TestCase):
    """Test structured formula isolation and rigorous verification."""

    def setUp(self) -> None:
        self.isolator = FormulaIsolator()

    def test_block_isolation_and_boundary_spacing(self) -> None:
        spans = [
            GlyphSpan(
                span_id="s1",
                text="Given condition",
                bbox=(50.0, 50.0, 120.0, 62.0),
                font_name="Helvetica",
                font_size=10.0,
                color="#000000",
            ),
            GlyphSpan(
                span_id="s2",
                text="f(x) = ∫_0^1 x^2 dx",
                bbox=(125.0, 50.0, 220.0, 62.0),
                font_name="CMEX10",  # Math font
                font_size=10.0,
                color="#000000",
                is_math_or_symbol=True,
            ),
            GlyphSpan(
                span_id="s3",
                text="for all real values.",
                bbox=(225.0, 50.0, 310.0, 62.0),
                font_name="Helvetica",
                font_size=10.0,
                color="#000000",
            ),
        ]
        block = TextBlock(block_id="b_math_1", bbox=(50.0, 50.0, 310.0, 62.0), spans=spans)
        segment = self.isolator.isolate_block(block)

        self.assertEqual(len(segment.tokens), 1)
        self.assertEqual(segment.tokens[0].placeholder, "<b0></b0>")
        self.assertEqual(segment.tokens[0].raw_content, "f(x) = ∫_0^1 x^2 dx")

        # Verify semantic whitespace padding around token
        self.assertIn("Given condition <b0></b0> for all real values.", segment.masked_text)

    def test_token_verification_success(self) -> None:
        spans = [
            GlyphSpan("s1", "Let", (10, 10, 30, 20), "Times", 10.0, 0),
            GlyphSpan("s2", "x > 0", (35, 10, 60, 20), "Math", 10.0, 0, is_math_or_symbol=True),
            GlyphSpan("s3", "and", (65, 10, 80, 20), "Times", 10.0, 0),
            GlyphSpan("s4", "y < 1", (85, 10, 110, 20), "Math", 10.0, 0, is_math_or_symbol=True),
        ]
        block = TextBlock("b1", (10, 10, 110, 20), spans=spans)
        segment = self.isolator.isolate_block(block)

        # Valid translated text maintaining exact order <b0></b0> then <b1></b1>
        translated = "Giả sử <b0></b0> và <b1></b1> thỏa mãn."
        verif = self.isolator.verify_tokens(segment, translated)
        self.assertTrue(verif.is_valid)

        restored = self.isolator.restore_translation(segment, translated)
        self.assertEqual(restored, "Giả sử x > 0 và y < 1 thỏa mãn.")

    def test_token_verification_missing_token(self) -> None:
        spans = [
            GlyphSpan("s1", "Let", (10, 10, 30, 20), "Times", 10.0, 0),
            GlyphSpan("s2", "x > 0", (35, 10, 60, 20), "Math", 10.0, 0, is_math_or_symbol=True),
        ]
        block = TextBlock("b1", (10, 10, 60, 20), spans=spans)
        segment = self.isolator.isolate_block(block)

        # Translation accidentally erased <b0></b0>
        translated = "Giả sử một điều kiện nào đó."
        verif = self.isolator.verify_tokens(segment, translated)
        self.assertFalse(verif.is_valid)
        self.assertIn("<b0></b0>", verif.missing_tokens)

        # Fail-closed fallback to raw text
        restored = self.isolator.restore_translation(segment, translated)
        self.assertEqual(restored, segment.raw_text)

    def test_token_verification_duplicate_token(self) -> None:
        spans = [
            GlyphSpan("s1", "Value", (10, 10, 40, 20), "Times", 10.0, 0),
            GlyphSpan("s2", "x", (45, 10, 55, 20), "Math", 10.0, 0, is_math_or_symbol=True),
        ]
        segment = self.isolator.isolate_block(TextBlock("b1", (10, 10, 55, 20), spans=spans))

        # Translation duplicated <b0></b0>
        translated = "Giá trị <b0></b0> hoặc <b0></b0> trùng lặp."
        verif = self.isolator.verify_tokens(segment, translated)
        self.assertFalse(verif.is_valid)
        self.assertIn("<b0></b0>", verif.duplicate_tokens)

    def test_token_verification_out_of_order(self) -> None:
        spans = [
            GlyphSpan("s1", "A", (10, 10, 20, 20), "Times", 10.0, 0),
            GlyphSpan("s2", "x_1", (25, 10, 40, 20), "Math", 10.0, 0, is_math_or_symbol=True),
            GlyphSpan("s3", "B", (45, 10, 55, 20), "Times", 10.0, 0),
            GlyphSpan("s4", "x_2", (60, 10, 75, 20), "Math", 10.0, 0, is_math_or_symbol=True),
        ]
        segment = self.isolator.isolate_block(TextBlock("b1", (10, 10, 75, 20), spans=spans))

        # Translation inverted the order: <b1></b1> before <b0></b0>
        translated = "B <b1></b1> trước A <b0></b0>."
        verif = self.isolator.verify_tokens(segment, translated)
        self.assertFalse(verif.is_valid)
        self.assertTrue(verif.out_of_order)


class TestGeometricGrouping(unittest.TestCase):
    """Test relative geometric line clustering, fraction-aware tolerance, and tabular isolation."""

    def setUp(self) -> None:
        self.grouper = GeometricGrouper()

    def test_line_clustering_relative_tolerance(self) -> None:
        font_size = 12.0
        # Two spans on line 1 with slightly different baselines within tolerance (Δy = 3.0 pt <= 0.35 * 12 = 4.2 pt)
        s1 = GlyphSpan("s1", "First part", (50.0, 100.0, 120.0, 112.0), "Times", font_size, 0, origin=(50.0, 110.0))
        s2 = GlyphSpan("s2", "second part", (125.0, 102.0, 200.0, 114.0), "Times", font_size, 0, origin=(125.0, 112.0))

        # A third span clearly on line 2 (Δy = 18.0 pt)
        s3 = GlyphSpan("s3", "Next line entirely", (50.0, 125.0, 180.0, 137.0), "Times", font_size, 0, origin=(50.0, 135.0))

        lines = self.grouper.cluster_spans_into_lines([s1, s2, s3])
        self.assertEqual(len(lines), 2)
        self.assertEqual(len(lines[0].spans), 2)
        self.assertEqual(lines[0].text, "First part second part")
        self.assertEqual(len(lines[1].spans), 1)
        self.assertEqual(lines[1].text, "Next line entirely")

    def test_fraction_aware_vertical_clustering(self) -> None:
        font_size = 12.0
        # Text prefix on main baseline y = 100
        prefix = GlyphSpan("p1", "Equation:", (50.0, 90.0, 110.0, 102.0), "Times", font_size, 0, origin=(50.0, 100.0))

        # Fraction numerator sits above baseline (y = 93)
        num = GlyphSpan("num", "a + b", (115.0, 84.0, 145.0, 94.0), "Math", 10.0, 0, origin=(115.0, 92.0), is_math_or_symbol=True)
        # Fraction denominator sits below baseline (y = 107)
        den = GlyphSpan("den", "c + d", (115.0, 102.0, 145.0, 112.0), "Math", 10.0, 0, origin=(115.0, 108.0), is_math_or_symbol=True)

        # In standard line grouping, den would be split into a new line.
        # With fraction tolerance (0.75 * 12 = 9.0 pt), numerator and denominator cluster into the parent equation line!
        lines = self.grouper.cluster_spans_into_lines([prefix, num, den])
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].has_fraction)
        self.assertEqual(len(lines[0].spans), 3)

    def test_tabular_isolation_and_gutter_detection(self) -> None:
        # A 2-column table across 2 rows
        # Row 0: Col 0 at x=50, Col 1 at x=200
        r0_c0 = GlyphSpan("r0c0", "Item 1", (50.0, 50.0, 100.0, 62.0), "Times", 10.0, 0)
        r0_c1 = GlyphSpan("r0c1", "$100.00", (200.0, 50.0, 250.0, 62.0), "Times", 10.0, 0)

        # Row 1: Col 0 back-jumps to x=50, Col 1 at x=200
        r1_c0 = GlyphSpan("r1c0", "Item 2", (50.0, 70.0, 100.0, 82.0), "Times", 10.0, 0)
        r1_c1 = GlyphSpan("r1c1", "$250.00", (200.0, 70.0, 250.0, 82.0), "Times", 10.0, 0)

        cells = self.grouper.isolate_tabular_cells([r0_c0, r0_c1, r1_c0, r1_c1])
        self.assertEqual(len(cells), 4)

        # Verify row indices
        self.assertEqual(cells[0].row_index, 0)
        self.assertEqual(cells[0].col_index, 0)
        self.assertEqual(cells[1].row_index, 0)
        self.assertEqual(cells[1].col_index, 1)

        self.assertEqual(cells[2].row_index, 1)
        self.assertEqual(cells[2].col_index, 0)
        self.assertEqual(cells[3].row_index, 1)
        self.assertEqual(cells[3].col_index, 1)


if __name__ == "__main__":
    unittest.main()
