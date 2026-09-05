"""Unit tests for the Reading Order Inference module."""

import unittest
from pdf2zh.reading_order import (
    LayoutBox,
    detect_column_gutters,
    infer_reading_order_indices,
    sort_boxes_by_reading_order,
)


class TestReadingOrder(unittest.TestCase):
    def test_single_column_sorting(self):
        boxes = [
            LayoutBox(id="b3", x0=50, y0=500, x1=500, y1=550, text="Paragraph 3"),
            LayoutBox(id="b1", x0=50, y0=700, x1=500, y1=750, text="Paragraph 1"),
            LayoutBox(id="b2", x0=50, y0=600, x1=500, y1=650, text="Paragraph 2"),
        ]
        sorted_boxes = sort_boxes_by_reading_order(boxes, page_width=600, page_height=800)
        sorted_ids = [b.id for b in sorted_boxes]
        self.assertEqual(sorted_ids, ["b1", "b2", "b3"])

    def test_two_column_scientific_paper(self):
        # A 600pt wide page with a title spanning across the top,
        # followed by two columns (left: x in [50, 280], right: x in [320, 550])
        title = LayoutBox(id="title", x0=50, y0=750, x1=550, y1=790, text="Paper Title")
        
        # Left column (descending y1: 700 -> 500 -> 300)
        left_1 = LayoutBox(id="L1", x0=50, y0=650, x1=280, y1=700, text="Left Top")
        left_2 = LayoutBox(id="L2", x0=50, y0=450, x1=280, y1=500, text="Left Mid")
        left_3 = LayoutBox(id="L3", x0=50, y0=250, x1=280, y1=300, text="Left Bot")
        
        # Right column (descending y1: 700 -> 500 -> 300)
        right_1 = LayoutBox(id="R1", x0=320, y0=650, x1=550, y1=700, text="Right Top")
        right_2 = LayoutBox(id="R2", x0=320, y0=450, x1=550, y1=500, text="Right Mid")
        right_3 = LayoutBox(id="R3", x0=320, y0=250, x1=550, y1=300, text="Right Bot")

        # Shuffled list
        boxes = [right_2, left_1, right_1, left_3, title, right_3, left_2]

        gutters = detect_column_gutters(boxes, page_width=600)
        self.assertEqual(len(gutters), 1)
        self.assertTrue(280 <= gutters[0] <= 320)

        sorted_boxes = sort_boxes_by_reading_order(boxes, page_width=600, page_height=800)
        sorted_ids = [b.id for b in sorted_boxes]

        # Expected: title first, then entire left column, then entire right column
        self.assertEqual(sorted_ids[0], "title")
        self.assertEqual(sorted_ids[1:4], ["L1", "L2", "L3"])
        self.assertEqual(sorted_ids[4:7], ["R1", "R2", "R3"])


if __name__ == "__main__":
    unittest.main()
