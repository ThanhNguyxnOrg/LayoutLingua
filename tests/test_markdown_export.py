"""Unit tests for clean Markdown document export."""

from layoutlingua.core.ir import DocumentIR, PageIR, TextBlock, GlyphSpan, PageGeometry
from layoutlingua.processing.markdown_export import export_document_markdown


def test_export_document_markdown():
    span_title = GlyphSpan(span_id="s1", text="Academic Paper Title", bbox=(0, 0, 100, 20), font_size=19.0, font_name="Helvetica-Bold", color=0, flags=2)
    b1 = TextBlock(block_id="b1", bbox=(0, 0, 100, 20), spans=[span_title])

    span_para = GlyphSpan(span_id="s2", text="This is an introduction paragraph.", bbox=(0, 25, 100, 50), font_size=10.0, font_name="Helvetica", color=0, flags=0)
    b2 = TextBlock(block_id="b2", bbox=(0, 25, 100, 50), spans=[span_para])

    b3 = TextBlock(block_id="b3", bbox=(0, 55, 100, 75), block_type="formula", spans=[
        GlyphSpan(span_id="s3", text="E = mc^2", bbox=(0, 55, 100, 75), font_size=10.0, font_name="Math", color=0)
    ])

    p1 = PageIR(page_number=1, geometry=PageGeometry(width=200, height=300), blocks=[b1, b2, b3])
    doc = DocumentIR(doc_id="d1", filename="test.pdf", page_count=1, pages=[p1])

    trans = {
        "b1": "Tiêu đề Bài báo Khoa học",
        "b2": "Đây là đoạn giới thiệu.",
    }

    md = export_document_markdown(doc, trans)
    assert "# Tiêu đề Bài báo Khoa học" in md
    assert "Đây là đoạn giới thiệu." in md
    assert "E = mc^2" in md