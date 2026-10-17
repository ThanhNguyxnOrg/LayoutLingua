"""Unit tests for running header, footer, and page number de-noising."""

from layoutlingua.core.ir import GlyphSpan, PageGeometry, PageIR, TextBlock
from layoutlingua.processing.header_footer import detect_running_headers_footers


def _make_page(page_num: int, blocks_spec: list[tuple[str, float, float, float, float, str]]) -> PageIR:
    geom = PageGeometry(width=600.0, height=800.0)
    blocks: list[TextBlock] = []
    for block_id, x0, y0, x1, y1, text in blocks_spec:
        span = GlyphSpan(
            span_id=f"s_{block_id}",
            text=text,
            bbox=(x0, y0, x1, y1),
            font_name="Helvetica",
            font_size=9.0,
            color="#000000",
        )
        blocks.append(TextBlock(block_id=block_id, bbox=(x0, y0, x1, y1), spans=[span]))
    return PageIR(page_number=page_num, geometry=geom, blocks=blocks)


def test_detect_recurring_headers_and_page_numbers():
    # Page 1
    p1 = _make_page(1, [
        ("h1", 50, 20, 550, 40, "IEEE Transactions on Neural Networks"),
        ("body1", 50, 200, 550, 300, "This is the introduction text."),
        ("pnum1", 280, 770, 320, 790, "1"),
    ])

    # Page 2
    p2 = _make_page(2, [
        ("h2", 50, 20, 550, 40, "IEEE Transactions on Neural Networks"),
        ("body2", 50, 200, 550, 300, "This is the methodology section."),
        ("pnum2", 280, 770, 320, 790, "2"),
    ])

    # Page 3
    p3 = _make_page(3, [
        ("h3", 50, 20, 550, 40, "IEEE Transactions on Neural Networks"),
        ("body3", 50, 200, 550, 300, "This is the conclusion section."),
        ("pnum3", 280, 770, 320, 790, "3"),
    ])

    suppressed = detect_running_headers_footers([p1, p2, p3])

    # Headers and page numbers should be flagged
    assert "h1" in suppressed
    assert "h2" in suppressed
    assert "h3" in suppressed
    assert "pnum1" in suppressed
    assert "pnum2" in suppressed
    assert "pnum3" in suppressed

    # Body paragraphs must NEVER be suppressed
    assert "body1" not in suppressed
    assert "body2" not in suppressed
    assert "body3" not in suppressed


def test_unique_header_not_suppressed():
    # If a block in the header area appears only on 1 page (like an article Title), do not suppress
    p1 = _make_page(1, [
        ("title", 50, 30, 550, 60, "A Novel Architecture for Document Translation"),
        ("body", 50, 200, 550, 300, "Abstract content."),
    ])
    p2 = _make_page(2, [
        ("body2", 50, 200, 550, 300, "Page 2 content."),
    ])

    suppressed = detect_running_headers_footers([p1, p2], min_repetition=2)
    assert "title" not in suppressed
    assert "body" not in suppressed
