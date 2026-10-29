"""Unit tests for adaptive text fitting, lineheight micro-compaction, and soft margin absorption."""

from layoutlingua.typesetting.fitting import TextFitTester
from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.models import TypesetOptions, OverflowCause


def test_micro_compaction_and_soft_margin_rescue():
    fm = FontManager()
    tester = TextFitTester(font_manager=fm)

    # Tight rectangle where normal lineheight (1.2x) might overflow slightly at min font size
    rect = (50.0, 50.0, 200.0, 75.0)
    # A sentence in Vietnamese
    text = "Định lý 1: Đối với mọi ma trận vuông và các giá trị riêng tương ứng, bất đẳng thức luôn được thỏa mãn."

    options = TypesetOptions(
        base_lineheight_ratio=1.2,
        min_font_pt=7.0,
        min_font_scale=0.7,
    )

    fits, font_size, cause, lines, eff_lh = tester.test_fit(
        rect=rect,
        text=text,
        orig_font_size=10.0,
        options=options,
    )

    assert fits is True
    assert font_size >= 7.0
    assert cause == OverflowCause.NONE
    assert eff_lh > 0.0