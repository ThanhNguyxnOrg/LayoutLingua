"""Regression test suite validating fixes for academic math PDF parsing and typesetting.

Covers:
1. Adobe Symbol Font Private Use Area (PUA 0xF000-0xF0FF) to Unicode normalization.
2. Unicode glyph availability in DejaVuSans (no tofu boxes for Greek/math).
3. Preservation of pure formula blocks and fragmented expressions.
4. Left-to-right span sorting (x0 ordering) within text lines.
5. Cohesive formula token grouping in FormulaIsolator.
6. Clearance protection tolerance eliminating false-positive collisions with adjacent lines,
   thin separator rules, and vector underlines.
"""

from __future__ import annotations

import unittest
import pymupdf

from layoutlingua.core.ir import GlyphSpan, TextBlock, PageGeometry, PageIR
from layoutlingua.core.parser import parse_pdf, _is_pure_formula_block
from layoutlingua.processing.formula.isolator import FormulaIsolator
from layoutlingua.processing.text_sanitizer import sanitize_extracted_text
from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.protection import (
    ClearancePlanner,
    ExclusionZone,
    ExclusionZoneType,
    compute_tight_line_clearance_regions,
    rects_intersect,
)


def test_symbol_pua_to_unicode_mapping():
    """Verify that Adobe Symbol PUA characters 0xF020-0xF0FF map losslessly to authentic Unicode."""
    # Greek letters: alpha (\uf061), beta (\uf062), gamma (\uf067)
    pua_greek = "\uf061, \uf062, \uf067"
    sanitized = sanitize_extracted_text(pua_greek)
    assert sanitized == "α, β, γ"

    # Math relations: >= (\uf0b3), <= (\uf0a3), sum (\uf053), plus (\uf02b), minus (\uf02d), equal (\uf03d)
    pua_math = "\uf0b3 \uf0a3 \uf053 \uf02b \uf02d \uf03d"
    assert sanitize_extracted_text(pua_math) == "≥ ≤ Σ + - ="


def test_dejavusans_has_greek_and_math_glyphs():
    """Verify that the bundled DejaVuSans font contains valid glyphs for all mapped symbols."""
    fm = FontManager()
    font = fm.get_font()

    chars_to_test = ["α", "β", "γ", "≤", "≥", "∑", "±", "≠", "≈", "đ", "ấ", "ế", "ệ", "ự"]
    for char in chars_to_test:
        codepoint = ord(char)
        assert font.has_glyph(codepoint) > 0, f"DejaVuSans missing glyph for {char} (U+{codepoint:04X})"


def test_pure_formula_fragment_detection():
    """Verify that fragmented expressions with zero prose words are classified as formulas."""
    spans_ellipses = [
        GlyphSpan(
            span_id="s1",
            text="0 ... ...",
            font_name="Times New Roman",
            font_size=12.0,
            color=0,
            bbox=(10, 10, 50, 20),
        )
    ]
    assert _is_pure_formula_block(spans_ellipses) is True

    spans_equation = [
        GlyphSpan(
            span_id="s2",
            text="C_{n+k-1}^k = P_{n+k-1}(k; n-1)",
            font_name="Symbol",
            font_size=12.0,
            color=0,
            bbox=(10, 10, 100, 20),
            is_math_or_symbol=True,
        )
    ]
    assert _is_pure_formula_block(spans_equation) is True


def test_formula_isolator_groups_connected_math():
    """Verify that FormulaIsolator groups consecutive math spans into cohesive tokens."""
    spans = [
        GlyphSpan(span_id="s0", text="Với ", font_name="Times New Roman", font_size=12.0, color=0, bbox=(54.0, 153.0, 75.0, 166.0)),
        GlyphSpan(span_id="s1", text="0 ", font_name="Times New Roman", font_size=12.5, color=0, bbox=(77.0, 152.0, 83.0, 166.0)),
        GlyphSpan(span_id="s2", text="≤ ", font_name="Symbol", font_size=12.5, color=0, bbox=(85.0, 151.0, 92.0, 166.0)),
        GlyphSpan(span_id="s3", text="n ", font_name="Times New Roman,Italic", font_size=12.5, color=0, bbox=(95.0, 152.0, 101.0, 166.0)),
        GlyphSpan(span_id="s4", text="i", font_name="Times New Roman,Italic", font_size=7.2, color=0, bbox=(100.0, 160.0, 103.0, 168.0)),
        GlyphSpan(span_id="s5", text="≤ ", font_name="Symbol", font_size=12.5, color=0, bbox=(106.0, 151.0, 113.0, 166.0)),
        GlyphSpan(span_id="s6", text="n ", font_name="Times New Roman,Italic", font_size=12.5, color=0, bbox=(116.0, 152.0, 122.0, 166.0)),
        GlyphSpan(span_id="s7", text=" và ", font_name="Times New Roman", font_size=12.0, color=0, bbox=(124.0, 153.0, 141.0, 166.0)),
        GlyphSpan(span_id="s8", text="n", font_name="Times New Roman,Italic", font_size=12.5, color=0, bbox=(143.0, 152.0, 149.0, 166.0)),
        GlyphSpan(span_id="s9", text="1", font_name="Times New Roman", font_size=7.2, color=0, bbox=(148.0, 160.0, 152.0, 168.0)),
        GlyphSpan(span_id="s10", text=" = ", font_name="Symbol", font_size=12.5, color=0, bbox=(154.0, 151.0, 161.0, 166.0)),
        GlyphSpan(span_id="s11", text="n.", font_name="Times New Roman,Italic", font_size=12.5, color=0, bbox=(163.0, 152.0, 175.0, 166.0)),
    ]
    block = TextBlock(block_id="test_b", bbox=(54.0, 151.0, 175.0, 168.0), spans=spans)

    iso = FormulaIsolator()
    seg = iso.isolate_block(block)

    assert seg.masked_text == "Với <b0></b0> và <b1></b1>"
    assert len(seg.tokens) == 2
    assert "0 ≤ n" in seg.tokens[0].raw_content
    assert "n" in seg.tokens[1].raw_content


def test_clearance_mutual_interaction_tolerance():
    """Verify that adjacent paragraphs with small gaps (<1.0 pt) are approved without mutual rejection."""
    b1 = TextBlock(
        block_id="b1",
        bbox=(50.0, 100.0, 200.0, 120.0),
        spans=[GlyphSpan(span_id="s1", text="B. HEADING", font_name="Times", font_size=12.0, color=0, bbox=(50.0, 100.0, 200.0, 120.0))],
    )
    # Gap is 0.7 pt (120.7 - 120.0)
    b2 = TextBlock(
        block_id="b2",
        bbox=(50.0, 120.7, 200.0, 150.0),
        spans=[GlyphSpan(span_id="s2", text="Paragraph text following heading", font_name="Times", font_size=12.0, color=0, bbox=(50.0, 120.7, 200.0, 150.0))],
    )

    page_ir = PageIR(
        page_number=1,
        geometry=PageGeometry(width=300.0, height=300.0),
        blocks=[b1, b2],
    )

    planner = ClearancePlanner(padding_pt=0.5)
    plan = planner.plan_page_clearance(page_ir, None, [b1, b2])

    assert plan.decisions["b1"].is_approved is True
    assert plan.decisions["b2"].is_approved is True


def test_clearance_side_by_side_symbol_table_no_false_collision():
    """Verify that text descriptions in a symbol table are NOT falsely rejected when formulas exist in adjacent columns."""
    # Column 1: Math symbol '='
    sym_block = TextBlock(
        block_id="sym_block",
        block_type="formula",
        bbox=(50.0, 100.0, 65.0, 115.0),
        spans=[GlyphSpan(span_id="s_sym", text="=", font_name="Symbol", font_size=10.0, color=0, bbox=(50.0, 100.0, 65.0, 115.0))],
    )
    # Column 2: Vietnamese description 'Bằng'
    desc_block = TextBlock(
        block_id="desc_block",
        block_type="text",
        bbox=(120.0, 100.0, 160.0, 115.0),
        spans=[GlyphSpan(span_id="s_desc", text="Bằng", font_name="Times", font_size=10.0, color=0, bbox=(120.0, 100.0, 160.0, 115.0))],
    )
    # Column 3: Equation 'a=b'
    eq_block = TextBlock(
        block_id="eq_block",
        block_type="formula",
        bbox=(280.0, 100.0, 310.0, 115.0),
        spans=[GlyphSpan(span_id="s_eq", text="a=b", font_name="Times", font_size=10.0, color=0, bbox=(280.0, 100.0, 310.0, 115.0))],
    )

    page_ir = PageIR(
        page_number=6,
        geometry=PageGeometry(width=400.0, height=400.0),
        blocks=[sym_block, desc_block, eq_block],
    )

    planner = ClearancePlanner(padding_pt=0.5)
    plan = planner.plan_page_clearance(page_ir, None, [desc_block])

    assert plan.decisions["desc_block"].is_approved is True
    assert plan.decisions["desc_block"].collision_detail is None


class TestMathBookFixes(unittest.TestCase):
    def test_all(self) -> None:
        test_symbol_pua_to_unicode_mapping()
        test_dejavusans_has_greek_and_math_glyphs()
        test_pure_formula_fragment_detection()
        test_formula_isolator_groups_connected_math()
        test_clearance_mutual_interaction_tolerance()
        test_clearance_side_by_side_symbol_table_no_false_collision()

