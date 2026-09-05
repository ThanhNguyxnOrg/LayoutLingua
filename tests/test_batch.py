"""Unit tests for the Translation Batching module."""

import unittest
from pdf2zh.batch import BATCH_DELIMITER, TranslationBatcher


class TestTranslationBatcher(unittest.TestCase):
    def test_batch_translation_success(self):
        calls = []

        def mock_translate(text: str) -> str:
            calls.append(text)
            # Mock translation: reverse casing or prefix
            parts = text.split(BATCH_DELIMITER.strip())
            return f" {BATCH_DELIMITER.strip()} ".join(f"Dịch: {p.strip()}" for p in parts)

        batcher = TranslationBatcher(translate_func=mock_translate, max_batch_size=5)
        segments = ["Mục một", "Mục hai", "Mục ba"]
        results = batcher.batch_translate_segments(segments)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], "Dịch: Mục một")
        self.assertEqual(results[1], "Dịch: Mục hai")
        self.assertEqual(results[2], "Dịch: Mục ba")
        # All 3 segments should have been batched in a single call
        self.assertEqual(len(calls), 1)

    def test_batch_fallback_on_delimiter_mismatch(self):
        call_count = 0

        def faulty_translate(text: str) -> str:
            nonlocal call_count
            call_count += 1
            if BATCH_DELIMITER.strip() in text:
                # Deliberately destroy delimiter
                return "Bản dịch bị nuốt mất delimiter"
            return f"Dịch đơn: {text}"

        batcher = TranslationBatcher(translate_func=faulty_translate, max_batch_size=3)
        segments = ["Phần 1", "Phần 2"]
        results = batcher.batch_translate_segments(segments)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "Dịch đơn: Phần 1")
        self.assertEqual(results[1], "Dịch đơn: Phần 2")
        # 1 failed batch call + 2 fallback individual calls = 3
        self.assertEqual(call_count, 3)

    def test_large_or_formula_segments_isolated(self):
        calls = []

        def mock_translate(text: str) -> str:
            calls.append(text)
            return f"Trans: {text}"

        batcher = TranslationBatcher(translate_func=mock_translate, max_batch_size=5)
        segments = ["Short A", "Short B with {v0} formula", "Short C"]
        results = batcher.batch_translate_segments(segments)

        self.assertEqual(len(results), 3)
        # Segment with {v0} must not be grouped into a bulk batch
        self.assertTrue(any("{v0}" in c and "Short A" not in c for c in calls))


if __name__ == "__main__":
    unittest.main()
