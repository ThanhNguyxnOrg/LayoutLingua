"""Comprehensive test suite for academic mathematical formula detection and preservation.

Inspired by open-source projects PDFMathTranslate (pdf2zh) and BabelDOC.
Validates:
1. Pure display formulas across diverse branches of mathematics (trigonometry, calculus, algebra, geometry, combinatorics).
2. Greek letters and math operators are classified as formulas rather than natural language prose.
3. Natural language headings, TOC entries, lead-in sentences, and prose containing equations are NOT classified as pure formulas.
4. Spans using TeX/Math fonts are reliably detected as formulas.
"""

from __future__ import annotations

import unittest
from layoutlingua.core.ir import GlyphSpan, TextBlock
from layoutlingua.core.parser import FORMULA_FONT_PATTERN, _is_pure_formula_block
from layoutlingua.processing.formula.isolator import FormulaIsolator


class TestAcademicFormulaPreservation(unittest.TestCase):
    """Test suite validating open-source math formula preservation logic."""

    def setUp(self) -> None:
        self.isolator = FormulaIsolator()

    # -------------------------------------------------------------------------
    # 1. Display Formula Detection Across Math Branches
    # -------------------------------------------------------------------------

    def test_trigonometric_identities_classified_as_formula(self) -> None:
        """Trigonometric formulas with Greek letters, degrees, and signs must be recognized as formulas."""
        trig_formulas = [
            "sin(-α) = -sin α",
            "cos(-α) = cos α",
            "tan(-α) = -tan α",
            "cot(-α) = -cot α",
            "sin(360° ± α) = ±sin α",
            "cos(360° ± α) = cos α",
            "tan(360° ± α) = ±tan α",
            "cot(360° ± α) = ±cot α",
            "sin(180° - α) = sin α",
            "cos(180° - α) = -cos α",
            "tan(α + β) = (tan α + tan β) / (1 - tan α tan β)",
            "sin(2α) = 2 sin α cos α",
            "cos(2α) = cos² α - sin² α = 2cos² α - 1",
        ]
        for expr in trig_formulas:
            span = GlyphSpan(
                span_id="s_trig",
                text=expr,
                bbox=(50.0, 100.0, 300.0, 120.0),
                font_name="Times-Roman",
                font_size=10.0,
                color="#000000",
            )
            self.assertTrue(
                _is_pure_formula_block([span]),
                f"Formula '{expr}' must be detected as a pure formula block.",
            )

    def test_algebra_calculus_combinatorics_formulas(self) -> None:
        """Algebraic, calculus, and combinatorial equations must be recognized as formulas."""
        academic_formulas = [
            "P_n(k1, k2, ..., km) = n! / (k1! k2! ... km!)",
            "(a + b)^n = ∑ C_n^k a^{n-k} b^k",
            "f(x) = √(x^2 + 1)",
            "Δ = b^2 - 4ac",
            "x = (-b ± √Δ) / 2a",
            "S = 1/2 a h_a = abc / 4R = pr",
            "lim_{x -> 0} sin(x)/x = 1",
            "∫ sin(x) dx = -cos(x) + C",
            "a² = b² + c² - 2bc cos A",
            "vec{a} · vec{b} = |vec{a}| |vec{b}| cos θ",
        ]
        for expr in academic_formulas:
            span = GlyphSpan(
                span_id="s_math",
                text=expr,
                bbox=(50.0, 100.0, 350.0, 125.0),
                font_name="Times-Roman",
                font_size=10.0,
                color="#000000",
            )
            self.assertTrue(
                _is_pure_formula_block([span]),
                f"Equation '{expr}' must be detected as a pure formula block.",
            )

    # -------------------------------------------------------------------------
    # 2. TeX and Mathematical Font Pattern Matching
    # -------------------------------------------------------------------------

    def test_formula_font_pattern_coverage(self) -> None:
        """Fonts commonly embedded in academic PDFs for mathematics must match FORMULA_FONT_PATTERN."""
        math_fonts = [
            "CMMI10",
            "CMSY10",
            "CMEX10",
            "MSAM10",
            "MSBM10",
            "MathType5",
            "Times-Italic",
            "NimbusRomNo9L-ReguItal",
            "TeX-CMMI",
            "EUFM10",
            "XYPIC",
            "BLMATH",
            "txsy",
            "rsfs10",
            "wasy10",
        ]
        for font in math_fonts:
            self.assertTrue(
                bool(FORMULA_FONT_PATTERN.search(font)),
                f"Font '{font}' must match FORMULA_FONT_PATTERN.",
            )

    def test_formula_block_with_math_font_identified(self) -> None:
        """Blocks using mathematical fonts must be classified as formula regardless of string length."""
        span = GlyphSpan(
            span_id="s_cmmi",
            text="E = mc^2",
            bbox=(50.0, 100.0, 150.0, 120.0),
            font_name="CMMI10",
            font_size=12.0,
            color="#000000",
        )
        self.assertTrue(_is_pure_formula_block([span]))

    # -------------------------------------------------------------------------
    # 3. Non-Formula Text Discrimination (Headings, Prose, Sentences)
    # -------------------------------------------------------------------------

    def test_headings_and_toc_never_classified_as_formula(self) -> None:
        """Academic document titles, TOC entries, and section headers must NEVER be classified as formulas."""
        prose_blocks = [
            "Mục lục",
            "I. SỐ HỌC VÀ ĐẠI SỐ",
            "2. Hoán vị lặp",
            "3. Chỉnh hợp (không lặp)",
            "f) Đa giác đều n cạnh",
            "Số lượng P_n(...) hoán vị lặp bằng:",
            "Cho hàm số f(x) liên tục trên đoạn [a, b]",
            "Áp dụng công thức S = pr ta tính được bán kính r của đường tròn nội tiếp.",
            "Table of Contents",
            "Chapter 1: Trigonometric Functions and Applications",
            "Theorem 2.1: Let f be a continuous function on [a, b].",
        ]
        for text in prose_blocks:
            span = GlyphSpan(
                span_id="s_prose",
                text=text,
                bbox=(50.0, 100.0, 450.0, 125.0),
                font_name="Times-Roman",
                font_size=12.0,
                color="#000000",
            )
            self.assertFalse(
                _is_pure_formula_block([span]),
                f"Prose / heading '{text}' must NOT be classified as a pure formula.",
            )

    # -------------------------------------------------------------------------
    # 4. Inline Math Span Detection in FormulaIsolator
    # -------------------------------------------------------------------------

    def test_isolator_is_math_span_accuracy(self) -> None:
        """FormulaIsolator.is_math_span must identify math tokens while rejecting natural words."""
        # Math spans
        math_spans = [
            GlyphSpan(span_id="m1", text="sin", bbox=(0, 0, 20, 10), font_name="Times-Italic", font_size=10, color="#000000"),
            GlyphSpan(span_id="m2", text="cos", bbox=(0, 0, 20, 10), font_name="Times-Roman", font_size=10, color="#000000"),
            GlyphSpan(span_id="m3", text="60°", bbox=(0, 0, 20, 10), font_name="Times-Roman", font_size=10, color="#000000"),
            GlyphSpan(span_id="m4", text="±", bbox=(0, 0, 10, 10), font_name="Times-Roman", font_size=10, color="#000000"),
            GlyphSpan(span_id="m5", text="α", bbox=(0, 0, 10, 10), font_name="Times-Roman", font_size=10, color="#000000"),
            GlyphSpan(span_id="m6", text="x²", bbox=(0, 0, 15, 10), font_name="Times-Italic", font_size=10, color="#000000"),
        ]
        for s in math_spans:
            self.assertTrue(self.isolator.is_math_span(s), f"Span '{s.text}' should be recognized as math.")

        # Prose spans
        prose_spans = [
            GlyphSpan(span_id="p1", text="hoán", bbox=(0, 0, 30, 10), font_name="Times-Roman", font_size=10, color="#000000"),
            GlyphSpan(span_id="p2", text="đoạn", bbox=(0, 0, 30, 10), font_name="Times-Roman", font_size=10, color="#000000"),
            GlyphSpan(span_id="p3", text="function", bbox=(0, 0, 50, 10), font_name="Times-Roman", font_size=10, color="#000000"),
            GlyphSpan(span_id="p4", text="tam giác", bbox=(0, 0, 60, 10), font_name="Times-Roman", font_size=10, color="#000000"),
        ]
        for s in prose_spans:
            self.assertFalse(self.isolator.is_math_span(s), f"Span '{s.text}' should NOT be recognized as math.")


if __name__ == "__main__":
    unittest.main()
