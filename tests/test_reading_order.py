"""Tests for two-column and multi-column reading order sorting."""

from layoutlingua.core.ir import GlyphSpan, TextBlock
from layoutlingua.processing.reading_order import sort_blocks_reading_order


def _make_block(block_id: str, x0: float, y0: float, x1: float, y1: float, text: str) -> TextBlock:
    span = GlyphSpan(
        span_id=f"s_{block_id}",
        text=text,
        bbox=(x0, y0, x1, y1),
        font_name="Helvetica",
        font_size=10.0,
        color="#000000",
    )
    return TextBlock(block_id=block_id, bbox=(x0, y0, x1, y1), spans=[span])


def test_two_column_reading_order():
    page_w = 600.0
    # Title spanning across entire top
    title = _make_block("title", 50, 40, 550, 80, "Deep Learning Architecture")

    # Left column: x in [50, 280]
    left1 = _make_block("left1", 50, 100, 280, 180, "Left column paragraph 1")
    left2 = _make_block("left2", 50, 200, 280, 300, "Left column paragraph 2")

    # Right column: x in [320, 550]
    right1 = _make_block("right1", 320, 100, 550, 180, "Right column paragraph 1")
    right2 = _make_block("right2", 320, 200, 550, 300, "Right column paragraph 2")

    # Scrambled input stream (e.g. alternating horizontally across columns)
    scrambled = [title, left1, right1, left2, right2]

    sorted_blocks = sort_blocks_reading_order(scrambled, page_width=page_w)
    sorted_ids = [b.block_id for b in sorted_blocks]

    # Human reading order: Title -> Left1 -> Left2 -> Right1 -> Right2
    assert sorted_ids == ["title", "left1", "left2", "right1", "right2"]


def test_single_column_reading_order():
    page_w = 600.0
    b1 = _make_block("b1", 50, 50, 550, 100, "Paragraph 1")
    b2 = _make_block("b2", 50, 120, 550, 180, "Paragraph 2")
    b3 = _make_block("b3", 50, 200, 550, 260, "Paragraph 3")

    # Input out of vertical order
    scrambled = [b2, b1, b3]
    sorted_blocks = sort_blocks_reading_order(scrambled, page_width=page_w)
    assert [b.block_id for b in sorted_blocks] == ["b1", "b2", "b3"]


def test_multi_band_document():
    page_w = 600.0
    # Top full-width banner
    header = _make_block("header", 50, 20, 550, 50, "Conference Header")
    # Band 1: 2-column
    l1 = _make_block("l1", 50, 60, 280, 120, "Intro left 1")
    l2 = _make_block("l2", 50, 130, 280, 180, "Intro left 2")
    r1 = _make_block("r1", 320, 60, 550, 120, "Intro right 1")
    r2 = _make_block("r2", 320, 130, 550, 180, "Intro right 2")
    # Middle full-width figure
    fig = _make_block("fig", 50, 200, 550, 280, "Figure 1: System overview")
    # Band 2: 2-column
    l3 = _make_block("l3", 50, 300, 280, 360, "Method left")
    r3 = _make_block("r3", 320, 300, 550, 360, "Method right")

    scrambled = [r2, l1, header, fig, r3, l2, r1, l3]
    sorted_blocks = sort_blocks_reading_order(scrambled, page_width=page_w)
    sorted_ids = [b.block_id for b in sorted_blocks]

    expected = ["header", "l1", "l2", "r1", "r2", "fig", "l3", "r3"]
    assert sorted_ids == expected
