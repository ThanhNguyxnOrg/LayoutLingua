"""Unit tests for the Cross-Page Paragraph Stitcher."""

import unittest
from pdf2zh.stitcher import (
    begins_with_continuation,
    ends_with_sentence_break,
    is_cross_page_continuation,
    split_stitched_translation,
    stitch_cross_page_text,
)


class TestCrossPageStitcher(unittest.TestCase):
    def test_sentence_break_detection(self):
        self.assertTrue(ends_with_sentence_break("This is complete."))
        self.assertTrue(ends_with_sentence_break("Is this complete?"))
        self.assertTrue(ends_with_sentence_break("Theorem 1:"))
        self.assertFalse(ends_with_sentence_break("This continues into the next page"))

    def test_continuation_detection(self):
        self.assertTrue(begins_with_continuation("and therefore the proof holds."))
        self.assertTrue(begins_with_continuation("which satisfies the condition."))
        self.assertFalse(begins_with_continuation("Section 2. Related Work"))
        self.assertFalse(begins_with_continuation("1. Introduction"))

    def test_cross_page_continuation_flow(self):
        tail = "The fundamental mathematical property of the manifold ensures that"
        head = "the coordinate system remains invariant under deformation."
        self.assertTrue(is_cross_page_continuation(tail, head))

        # Distinct paragraphs should NOT be stitched
        tail_period = "The proof is completed as shown in Theorem 1."
        head_new = "In this section, we analyze empirical convergence."
        self.assertFalse(is_cross_page_continuation(tail_period, head_new))

    def test_stitch_and_split(self):
        tail = "The algorithm guarantees that"
        head = "convergence is strictly monotonic."
        stitched = stitch_cross_page_text(tail, head)
        self.assertEqual(
            stitched,
            "The algorithm guarantees that convergence is strictly monotonic.",
        )

        translated = (
            "Thuật toán đảm bảo rằng sự hội tụ là hoàn toàn đơn điệu."
        )
        part1, part2 = split_stitched_translation(
            translated,
            original_tail_len=len(tail),
            original_head_len=len(head),
        )
        self.assertTrue(len(part1) > 0)
        self.assertTrue(len(part2) > 0)
        self.assertEqual(f"{part1} {part2}", translated)


if __name__ == "__main__":
    unittest.main()
