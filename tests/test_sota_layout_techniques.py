"""Unit tests for SOTA layout preservation techniques.

Covers:
1. ElasticDotLeader (LaTeX \\dotfill pattern for Table of Contents lines).
2. HorizontalBaselineFragmentMerger (MinerU & Marker baseline stitching).
"""

from layoutlingua.core.ir import GlyphSpan, TextBlock
from layoutlingua.core.parser import _merge_horizontal_baseline_fragments
from layoutlingua.typesetting.fitting import TextFitTester
from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.models import OverflowCause, TypesetOptions


def test_elastic_dot_leader_adaptation():
    """Verify that a Table of Contents line with 70 dots adapts to fit within a single-line box."""
    fm = FontManager()
    tester = TextFitTester(font_manager=fm)

    # Box width: 250pt, height: 14pt (strictly 1 line of 10pt font, where 70 dots would cause overflow)
    rect = (50.0, 50.0, 300.0, 64.0)
    # Long English title with 70 dots
    toc_text = "2. Permutation with repetition ...................................................................... 9"

    options = TypesetOptions(
        base_lineheight_ratio=1.2,
        min_font_pt=7.0,
        min_font_scale=0.7,
    )

    # Test adapt_dot_leader_if_needed directly
    adapted = tester.adapt_dot_leader_if_needed(toc_text, target_width=250.0, font_size=10.0)
    assert adapted != toc_text
    assert adapted.startswith("2. Permutation with repetition .")
    assert adapted.endswith(" 9")
    # Number of dots should be significantly compacted from 70 (e.g. ~24 dots)
    assert len(adapted) < len(toc_text)
    assert len(adapted) < 70

    # Test that test_fit returns True on the single line box
    fits, font_size, cause, line_count, eff_lh = tester.test_fit(
        rect=rect,
        text=toc_text,
        orig_font_size=10.0,
        options=options,
    )

    assert fits is True
    assert line_count == 1
    assert cause == OverflowCause.NONE


def test_elastic_dot_leader_leaves_normal_text_untouched():
    """Verify that normal sentences, decimals, and trailing ellipses are NOT touched."""
    fm = FontManager()
    tester = TextFitTester(font_manager=fm)

    normal_texts = [
        "This is a normal paragraph sentence.",
        "The value of pi is approximately 3.14159.",
        "Wait a moment...",
        "Section 1.2 Introduction",
    ]

    for t in normal_texts:
        res = tester.adapt_dot_leader_if_needed(t, target_width=400.0, font_size=10.0)
        assert res == t


def test_horizontal_baseline_fragment_merging():
    """Verify that adjacent single-line fragments on the same baseline are coalesced."""
    b1 = TextBlock(
        block_id="p1_b0",
        bbox=(50.0, 100.0, 150.0, 114.0),
        spans=[
            GlyphSpan(
                span_id="s1",
                text="The number of combinations is",
                bbox=(50.0, 100.0, 150.0, 114.0),
                font_name="DejaVuSans",
                font_size=10.0,
                color="#000000",
            )
        ],
        block_type="text",
    )
    b2 = TextBlock(
        block_id="p1_b1",
        bbox=(154.0, 100.2, 230.0, 114.1),
        spans=[
            GlyphSpan(
                span_id="s2",
                text="given by equation (1).",
                bbox=(154.0, 100.2, 230.0, 114.1),
                font_name="DejaVuSans",
                font_size=10.0,
                color="#000000",
            )
        ],
        block_type="text",
    )

    merged = _merge_horizontal_baseline_fragments([b1, b2])
    assert len(merged) == 1
    assert merged[0].block_id == "p1_b0"
    assert "The number of combinations is given by equation (1)." in merged[0].text
    assert merged[0].bbox[0] == 50.0
    assert merged[0].bbox[2] == 230.0


def test_horizontal_baseline_fragment_merging_safeguards_columns():
    """Verify that two-column paragraphs separated by a wide gutter (> 20pt) are NOT merged."""
    col1 = TextBlock(
        block_id="p1_col1",
        bbox=(50.0, 100.0, 200.0, 114.0),
        spans=[
            GlyphSpan(
                span_id="s1",
                text="Left column text.",
                bbox=(50.0, 100.0, 200.0, 114.0),
                font_name="DejaVuSans",
                font_size=10.0,
                color="#000000",
            )
        ],
        block_type="text",
    )
    # Gap is 240.0 - 200.0 = 40pt (wide column gutter)
    col2 = TextBlock(
        block_id="p1_col2",
        bbox=(240.0, 100.0, 390.0, 114.0),
        spans=[
            GlyphSpan(
                span_id="s2",
                text="Right column text.",
                bbox=(240.0, 100.0, 390.0, 114.0),
                font_name="DejaVuSans",
                font_size=10.0,
                color="#000000",
            )
        ],
        block_type="text",
    )

    merged = _merge_horizontal_baseline_fragments([col1, col2])
    # Must remain separate blocks
    assert len(merged) == 2
    assert merged[0].block_id == "p1_col1"
    assert merged[1].block_id == "p1_col2"
