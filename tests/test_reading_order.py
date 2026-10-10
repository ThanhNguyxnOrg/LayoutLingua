"""Unit tests for the Reading Order Inference module."""

import unittest

from layoutlingua.reading_order import (
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

    def test_three_column_borderless_layout(self):
        # A 600pt wide page with 3 columns (e.g. math symbol table)
        # Col 1: [40, 160], Col 2: [200, 350], Col 3: [390, 560]
        c1_1 = LayoutBox(id="C1_1", x0=40, y0=600, x1=160, y1=650, text="Symbol 1")
        c1_2 = LayoutBox(id="C1_2", x0=40, y0=500, x1=160, y1=550, text="Symbol 2")
        c1_3 = LayoutBox(id="C1_3", x0=40, y0=400, x1=160, y1=450, text="Symbol 3")

        c2_1 = LayoutBox(id="C2_1", x0=200, y0=600, x1=350, y1=650, text="Desc 1")
        c2_2 = LayoutBox(id="C2_2", x0=200, y0=500, x1=350, y1=550, text="Desc 2")
        c2_3 = LayoutBox(id="C2_3", x0=200, y0=400, x1=350, y1=450, text="Desc 3")

        c3_1 = LayoutBox(id="C3_1", x0=390, y0=600, x1=560, y1=650, text="Ex 1")
        c3_2 = LayoutBox(id="C3_2", x0=390, y0=500, x1=560, y1=550, text="Ex 2")
        c3_3 = LayoutBox(id="C3_3", x0=390, y0=400, x1=560, y1=450, text="Ex 3")

        boxes = [c2_2, c3_1, c1_3, c1_1, c3_3, c2_1, c1_2, c3_2, c2_3]
        gutters = detect_column_gutters(boxes, page_width=600)
        self.assertEqual(len(gutters), 2)
        self.assertTrue(160 <= gutters[0] <= 200)
        self.assertTrue(350 <= gutters[1] <= 390)

        sorted_boxes = sort_boxes_by_reading_order(boxes, page_width=600, page_height=800)
        sorted_ids = [b.id for b in sorted_boxes]
        self.assertEqual(sorted_ids[0:3], ["C1_1", "C1_2", "C1_3"])
        self.assertEqual(sorted_ids[3:6], ["C2_1", "C2_2", "C2_3"])
        self.assertEqual(sorted_ids[6:9], ["C3_1", "C3_2", "C3_3"])

    def test_spatial_dag_cycle_resilience(self):
        # Even if overlapping anomalous boxes exist, topological sort must safely return all boxes
        b1 = LayoutBox(id="b1", x0=50, y0=400, x1=200, y1=500, text="A")
        b2 = LayoutBox(id="b2", x0=50, y0=450, x1=200, y1=480, text="B")
        indices = infer_reading_order_indices([b1, b2], page_width=600, page_height=800)
        self.assertEqual(len(indices), 2)
        self.assertEqual(set(indices), {0, 1})


if __name__ == "__main__":
    unittest.main()
