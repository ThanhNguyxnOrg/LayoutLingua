"""Unit tests for the Structure-Aware Table Engine."""

import unittest
from pdf2zh.tables import (
    TableCell,
    TableGrid,
    compute_table_grits_score,
    fit_cell_text,
    is_cell_numeric_or_identifier,
    reconstruct_table_grid,
)


class TestTableEngine(unittest.TestCase):
    def test_numeric_and_code_protection(self):
        protected_cases = [
            "100%",
            "34.2 ± 1.5",
            "p < 0.001",
            "$25,000",
            "€4.50",
            "N/A",
            "-",
            "F1",
            "0.892",
            "< 0.05",
            "12/24",
        ]
        for val in protected_cases:
            self.assertTrue(
                is_cell_numeric_or_identifier(val),
                f"Expected '{val}' to be protected as numeric/code",
            )

        translatable_cases = [
            "Accuracy",
            "Method Description",
            "Baseline Model",
            "Average latency per request",
            "Tổng thời gian",
        ]
        for val in translatable_cases:
            self.assertFalse(
                is_cell_numeric_or_identifier(val),
                f"Expected '{val}' to be recognized as translatable text",
            )

    def test_grid_reconstruction(self):
        # 2 rows, 2 columns table
        # Row 0 (top): y in [250, 270]
        # Row 1 (bot): y in [220, 240]
        # Col 0 (left): x in [50, 150]
        # Col 1 (right): x in [160, 260]
        raw_cells = [
            (50.0, 250.0, 150.0, 270.0, "Header Col 1"),
            (160.0, 250.0, 260.0, 270.0, "Header Col 2"),
            (50.0, 220.0, 150.0, 240.0, "Data Row 1"),
            (160.0, 220.0, 260.0, 240.0, "98.5%"),
        ]
        table_bbox = (50.0, 220.0, 260.0, 270.0)
        grid = reconstruct_table_grid(raw_cells, table_bbox)

        self.assertEqual(grid.rows, 2)
        self.assertEqual(grid.cols, 2)
        self.assertEqual(len(grid.cells), 4)

        # Check header status
        top_left = grid.get_cell(0, 0)
        self.assertIsNotNone(top_left)
        self.assertTrue(top_left.is_header)
        self.assertFalse(top_left.is_numeric_or_code)

        # Check numeric status
        bot_right = grid.get_cell(1, 1)
        self.assertIsNotNone(bot_right)
        self.assertFalse(bot_right.is_header)
        self.assertTrue(bot_right.is_numeric_or_code)

    def test_cell_fitting(self):
        cell = TableCell(
            id="c1",
            row_idx=0,
            col_idx=0,
            bbox=(50.0, 100.0, 150.0, 130.0),  # width: 100, height: 30
            font_size=10.0,
        )

        def mock_measure(char: str, size: float) -> float:
            return size * 0.5

        # Short text should fit easily
        fits, final_size, lines = fit_cell_text(cell, "Độ chính xác", mock_measure)
        self.assertTrue(fits)
        self.assertGreaterEqual(final_size, 6.5)

        # Excessively long text for a small box should report failure
        long_text = "Đây là một đoạn văn bản vô cùng dài không thể nào nhét vừa vào một ô bảng nhỏ như thế này"
        fits_long, _, _ = fit_cell_text(cell, long_text, mock_measure)
        self.assertFalse(fits_long)

    def test_grits_metric(self):
        raw_cells = [
            (50.0, 250.0, 150.0, 270.0, "Model"),
            (160.0, 250.0, 260.0, 270.0, "F1-Score"),
        ]
        grid1 = reconstruct_table_grid(raw_cells, (50.0, 250.0, 260.0, 270.0))
        grid2 = reconstruct_table_grid(raw_cells, (50.0, 250.0, 260.0, 270.0))

        score = compute_table_grits_score(grid1, grid2)
        self.assertEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
