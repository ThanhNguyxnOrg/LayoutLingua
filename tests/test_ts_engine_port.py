from __future__ import annotations

import os
import tempfile

import pymupdf as fitz

from layoutlingua.core.parser import parse_pdf
from layoutlingua.processing.formula.word_tokens import vflag_pdf2zh
from layoutlingua.processing.normalizers.legacy_vietnamese import decode_vni_to_unicode
from layoutlingua.processing.text_sanitizer import detect_language_from_text
from layoutlingua.typesetting.engine import TypesetEngine
from layoutlingua.typesetting.models import TypesetOptions
from layoutlingua.typesetting.protection import (
    ExclusionZone,
    ExclusionZoneType,
    clip_clearance_rects_against_formulas,
)


def test_pdf2zh_vflag_classifier():
    # TeX / math fonts should be flagged as formula
    assert vflag_pdf2zh("CMMI10", "x") is True
    assert vflag_pdf2zh("CMSY10", "+") is True
    assert vflag_pdf2zh("MSBM10", "R") is True
    # Unmapped CID glyph should be flagged as formula
    assert vflag_pdf2zh("Times-Roman", "(cid:123)") is True
    # Math operators and Greek characters should be flagged as formula
    assert vflag_pdf2zh("Times-Roman", "∑") is True
    assert vflag_pdf2zh("Times-Roman", "α") is True
    assert vflag_pdf2zh("Times-Roman", "=") is True
    # Regular Latin prose in standard font should NOT be flagged as formula
    assert vflag_pdf2zh("TimesNewRomanPSMT", "A") is False
    assert vflag_pdf2zh("DejaVuSerif", "t") is False


def test_clearance_rect_formula_edge_clipping():
    # Minor boundary padding contact with an adjacent inline formula is cleanly clipped
    prose_rects = [(50.0, 100.0, 122.0, 114.0)]
    formula_zones = [
        ExclusionZone(
            zone_id="f1",
            zone_type=ExclusionZoneType.FORMULA,
            bbox=(120.0, 99.0, 155.0, 115.0),
            confidence=0.95,
        )
    ]
    clipped = clip_clearance_rects_against_formulas(prose_rects, formula_zones)
    assert len(clipped) == 1
    assert clipped[0][2] <= 120.0


def test_typeset_engine_subline_formula_preservation():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (56, 90),
        "Abstract: We introduce a layout-aware document translation pipeline.",
        fontsize=12,
        fontname="tiro",
    )
    page.insert_text((56, 130), "E = mc^2", fontsize=11, fontname="tiit")
    pdf_bytes = doc.tobytes()
    doc.close()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        doc_ir = parse_pdf(tmp_path)
    finally:
        os.remove(tmp_path)
    assert len(doc_ir.pages) == 1
    page_ir = doc_ir.pages[0]

    translated_segments = {
        b.block_id: "[VI] Tóm tắt: Chúng tôi giới thiệu hệ thống dịch tài liệu bảo toàn bố cục."
        for b in page_ir.blocks
        if b.block_type != "formula" and "Abstract" in b.text
    }

    engine = TypesetEngine(options=TypesetOptions(min_font_scale=0.70))
    res = engine.typeset(
        original_pdf=pdf_bytes,
        document_ir=doc_ir,
        translated_segments=translated_segments,
    )
    assert res.fitting_report.replaced_blocks >= 1

    out_doc = fitz.open(stream=res.pdf_bytes, filetype="pdf")
    rendered_text = out_doc[0].get_text("text")
    out_doc.close()
    assert "[VI]" in rendered_text
    assert "mc" in rendered_text or "E" in rendered_text


def test_detect_language_across_scripts_and_stopwords():
    assert detect_language_from_text("Bài toán quy hoạch tuyến tính và bất đẳng thức") == "vi"
    assert detect_language_from_text("The quick brown fox jumps over the lazy dog with from that") == "en"
    assert detect_language_from_text("Nous présentons une méthode pour la traduction dans les documents") == "fr"
    assert detect_language_from_text("日本語のテキストを翻訳するシステムです") == "ja"
    assert detect_language_from_text("한국어 문서 레이아웃 번역 엔진") == "ko"
    assert detect_language_from_text("Система перевода научных документов с сохранением формул") == "ru"


def test_vni_circumflex_and_horn_ordering():
    # Ensure oâ -> ô is not overwritten by bare VNI ô -> ơ
    decoded = decode_vni_to_unicode("Caùc boä phaän phoái hôïp toát")
    assert "phối" in decoded
    assert "hợp" in decoded
    assert "tốt" in decoded
