"""Unit tests for the Adaptive Typesetting and Multi-Space Constraint Solver."""

import unittest
from pdf2zh.typesetting import (
    TypesettingConstraints,
    solve_adaptive_typesetting,
    word_wrap_text,
)


class TestTypesetting(unittest.TestCase):
    def setUp(self):
        # Mock character measurement: average char width = 0.5 * font_size
        self.measure_char = lambda ch, size: size * 0.5

    def test_fit_in_primary_box(self):
        constraints = TypesettingConstraints(
            box_width=200.0,
            box_height=60.0,
            original_font_size=10.0,
        )
        text = "Deep learning models transform technical document translation."
        sol = solve_adaptive_typesetting(text, constraints, self.measure_char)
        self.assertTrue(sol.fits)
        self.assertEqual(sol.scale_ratio, 1.0)
        self.assertEqual(sol.spillover_used, 0.0)

    def test_scale_down_when_text_expands(self):
        constraints = TypesettingConstraints(
            box_width=150.0,
            box_height=50.0,
            original_font_size=12.0,
            min_font_scale=0.70,
        )
        text = "Các mô hình học sâu biến đổi hoàn toàn quy trình dịch tài liệu kỹ thuật phức tạp."
        sol = solve_adaptive_typesetting(text, constraints, self.measure_char)
        self.assertTrue(sol.fits)
        self.assertLessEqual(sol.font_size, 12.0)
        self.assertGreaterEqual(sol.scale_ratio, 0.70)

    def test_babeldoc_issue_89_multi_available_space_spillover(self):
        # Primary box is too short (only 20pt high for 3 lines of text),
        # but available_height_below is 40pt (e.g. whitespace before next section)
        constraints = TypesettingConstraints(
            box_width=150.0,
            box_height=20.0,
            available_height_below=40.0,
            original_font_size=10.0,
        )
        text = "This paragraph overflows the initial tight bounding box and safely spills over into available space below."
        sol = solve_adaptive_typesetting(text, constraints, self.measure_char)
        self.assertTrue(sol.fits)
        self.assertGreater(sol.spillover_used, 0.0)
        self.assertLessEqual(sol.spillover_used, 40.0)

    def test_fail_closed_when_impossible_to_fit(self):
        # A tiny 30x10 box with an enormous paragraph
        constraints = TypesettingConstraints(
            box_width=30.0,
            box_height=10.0,
            available_height_below=0.0,
            original_font_size=10.0,
        )
        text = "An enormous paragraph that cannot possibly fit into a tiny rectangle under any circumstances."
        sol = solve_adaptive_typesetting(text, constraints, self.measure_char)
        self.assertFalse(sol.fits)


if __name__ == "__main__":
    unittest.main()
