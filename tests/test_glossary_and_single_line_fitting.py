"""Regression tests for mathematical polysemy healing and tall single-line box fitting."""

from __future__ import annotations

import pymupdf

from layoutlingua.core.ir import DocumentIR, GlyphSpan, PageGeometry, PageIR, TextBlock
from layoutlingua.translation.glossary import GlossaryManager
from layoutlingua.typesetting.engine import TypesetEngine
from layoutlingua.typesetting.models import BlockFittingStatus, TypesetOptions


def test_math_polysemy_and_glossary_healing_vi_to_en() -> None:
    """Verify domain-specific Vietnamese math terms and MT polysemy drifts are normalized."""
    cases = [
        ("Trung bình điều hòa: ", "Air conditioning average:", "Harmonic mean:"),
        (" nghiệm đúng với mọi ", "The experience is true for everyone", "holds for all"),
        (" nghiệm đúng với ", "Correct experience with", "holds for"),
        ("Nghiệm ", "Experience", "Root"),
        ("vô nghiệm", "no experience", "no solution"),
        ("nghiệm kép; đồ thị cắt trục hoành", "double test; The graph intersects", "double root; The graph intersects"),
        ("Số chỉnh hợp chập k có thể tạo thành", "The number of convolutions k that can be formed", "The number of arrangements k that can be formed"),
        ("Số lượng tổ hợp chập k có thể thành lập", "The number of convolutional combinations k that can be formed", "The number of combinations k that can be formed"),
        ("Tâm sai của parabola ", "The wrong center of the parabola", "eccentricity of the parabola"),
        ("Tham số tiêu của Hyperbola ", "Target parameter of Hyperbola", "Focal parameter of Hyperbola"),
        ("Các cosin chỉ phương của vector ", "The cosine indicates the direction of the vector", "Direction cosines of the vector"),
        ("Hệ số pháp dạng ", "Format coefficients", "Normalizing factor"),
        ("d) Thể tích tạo bởi tiết diện", "d) Volume created by secretions", "d) Volume created by cross-section"),
        ("trong đó", "in measuring buzzing", "where"),
        (" k là số loại", "k is the number of types", "k: number of types"),
        ("3. Chỉnh hợp (không lặp)", "3. Alignment (no repetition)", "3. Arrangements (no repetition)"),
        ("Cấp số nhân · 29", "Exponential · 29", "Geometric progression · 29"),
        ("Viên phân · 38", "Fecal pellets · 38", "Circular segment · 38"),
        ("Hàm lồi", "Convex jaw", "Convex function"),
    ]
    for src, mt, expected in cases:
        out = GlossaryManager.normalize_translation(src, mt, "vi", "en")
        assert expected.lower() in out.lower(), f"Failed for {src!r}: got {out!r}, expected {expected!r}"


def test_vni_floating_diacritics_and_az_range_in_word_tokens() -> None:
    """Verify VNI floating accents across kerning spaces stay attached and 'A-Z' is not classified as math."""
    from layoutlingua.core.ir import CharInfo
    from layoutlingua.processing.formula.isolator import FormulaIsolator

    # 1. 'trong đó' in VNI-Times where ' ' appears before floating accent 'ù'
    chars = [
        CharInfo(char="t", bbox=(55.9, 206.5, 59.3, 222.1), origin=(55.9, 219.0)),
        CharInfo(char="r", bbox=(59.3, 206.5, 63.4, 222.1), origin=(59.3, 219.0)),
        CharInfo(char="o", bbox=(63.4, 206.5, 69.6, 222.1), origin=(63.4, 219.0)),
        CharInfo(char="n", bbox=(69.6, 206.5, 75.7, 222.1), origin=(69.6, 219.0)),
        CharInfo(char="g", bbox=(75.7, 206.5, 81.9, 222.1), origin=(75.7, 219.0)),
        CharInfo(char=" ", bbox=(81.3, 206.5, 84.3, 222.1), origin=(81.3, 219.0)),
        CharInfo(char="ñ", bbox=(83.9, 206.5, 90.1, 222.1), origin=(83.9, 219.0)),
        CharInfo(char="o", bbox=(90.1, 206.5, 96.2, 222.1), origin=(90.1, 219.0)),
        CharInfo(char=" ", bbox=(95.1, 206.5, 98.1, 222.1), origin=(95.1, 219.0)),
        CharInfo(char="ù", bbox=(96.3, 206.5, 96.7, 222.1), origin=(96.3, 219.0)),
    ]
    span = GlyphSpan(
        span_id="s_vni",
        text="trong đó",
        bbox=(55.9, 206.5, 98.1, 222.1),
        font_name="VNI-Times",
        font_size=12.0,
        color=0,
        flags=0,
        chars=tuple(chars),
    )
    block = TextBlock(
        block_id="p28_block_27",
        block_type="text",
        bbox=(55.9, 206.5, 98.1, 222.1),
        spans=[span],
    )
    seg = FormulaIsolator().isolate_block(block)
    assert seg.masked_text == "trong đó"

    # 2. 'Chinh phục chuyên đề toán từ A-Z' should keep 'A-Z' as prose, not a math subtraction token
    az_chars = [
        CharInfo(char=ch, bbox=(100.0 + i * 5.0, 300.0, 104.5 + i * 5.0, 314.0), origin=(100.0 + i * 5.0, 312.0))
        for i, ch in enumerate("Chinh phục chuyên đề toán từ A-Z")
    ]
    az_span = GlyphSpan(
        span_id="s_az",
        text="Chinh phục chuyên đề toán từ A-Z",
        bbox=(100.0, 300.0, 260.0, 314.0),
        font_name="Arial",
        font_size=13.0,
        color=0,
        flags=0,
        chars=tuple(az_chars),
    )
    az_block = TextBlock(
        block_id="p1_block_6",
        block_type="text",
        bbox=(100.0, 300.0, 260.0, 314.0),
        spans=[az_span],
    )
    az_seg = FormulaIsolator().isolate_block(az_block)
    assert az_seg.tokens == []
    assert az_seg.masked_text == "Chinh phục chuyên đề toán từ A-Z"


def test_tall_single_line_box_does_not_overflow_or_over_shrink() -> None:
    """Verify a 1-line block with bbox height ~1.95x font size stays on 1 line without OVERFLOW_FALLBACK."""
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    # Insert a 10pt single line inside a 19.5pt tall bounding box (simulating h=2.6% row in math tables)
    page.insert_text(pymupdf.Point(55, 215), "vô nghiệm", fontsize=10.0)
    pdf_bytes = doc.tobytes()
    doc.close()

    bbox = (55.0, 200.0, 97.0, 219.5)  # w=42pt, h=19.5pt (1.95x of 10pt)
    span = GlyphSpan(
        span_id="p1_s1",
        text="vô nghiệm",
        bbox=bbox,
        font_name="Times-Roman",
        font_size=10.0,
        color=0,
        flags=0,
        origin=(55.0, 215.0),
    )
    block = TextBlock(
        block_id="p1_b1",
        block_type="text",
        bbox=bbox,
        spans=[span],
    )
    # Place an inline formula obstacle to the right so width cannot expand arbitrarily
    formula_bbox = (105.0, 200.0, 250.0, 219.5)
    formula_span = GlyphSpan(
        span_id="p1_s2",
        text="ax^2 + bx + c > 0",
        bbox=formula_bbox,
        font_name="Times-Italic",
        font_size=10.0,
        color=0,
        flags=2,
        origin=(105.0, 215.0),
    )
    formula_block = TextBlock(
        block_id="p1_b2",
        block_type="formula",
        bbox=formula_bbox,
        spans=[formula_span],
    )
    page_ir = PageIR(
        page_number=1,
        geometry=PageGeometry(width=420.0, height=595.0),
        blocks=[block, formula_block],
    )
    doc_ir = DocumentIR(doc_id="test_doc", filename="test.pdf", page_count=1, pages=[page_ir])

    engine = TypesetEngine(options=TypesetOptions(min_font_scale=0.70))
    res = engine.typeset(
        original_pdf=pdf_bytes,
        document_ir=doc_ir,
        translated_segments={"p1_b1": "no solution"},
    )
    detail = next(d for d in res.fitting_report.details if d.block_id == "p1_b1")
    assert detail.status == BlockFittingStatus.SUCCESS
    assert detail.line_count == 1
    assert detail.shrink_ratio >= 0.85
