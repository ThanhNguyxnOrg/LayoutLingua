"""Unit tests for the Global Glossary Manager."""

import json
import tempfile
import unittest
from pathlib import Path
from pdf2zh.glossary import GlossaryManager


class TestGlossaryManager(unittest.TestCase):
    def test_add_and_substitute_terms(self):
        mgr = GlossaryManager({
            "attention mechanism": "cơ chế chú ý",
            "transformer": "mô hình Transformer",
        })
        text = "The attention mechanism in the transformer architecture improves translation."
        masked, token_map = mgr.pre_mask_terms(text)
        self.assertIn("<g0>", masked)
        self.assertIn("<g1>", masked)

        # Simulate translation with preserved tokens
        translated = "Kiến trúc <g1> sử dụng <g0> để cải thiện chất lượng."
        restored = mgr.post_restore_terms(translated, token_map)
        self.assertIn("cơ chế chú ý", restored)
        self.assertIn("mô hình Transformer", restored)

    def test_longest_match_priority(self):
        # Longest match "deep learning" should take precedence over "learning"
        mgr = GlossaryManager({
            "learning": "học hỏi",
            "deep learning": "học sâu",
        })
        text = "Modern deep learning techniques surpass classical learning."
        masked, token_map = mgr.pre_mask_terms(text)
        restored = mgr.post_restore_terms(masked, token_map)
        self.assertIn("học sâu", restored)
        self.assertIn("học hỏi", restored)

    def test_load_from_json_and_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # JSON file
            json_file = Path(tmpdir) / "glossary.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump({"eigenvalue": "giá trị riêng", "manifold": "đa tạp"}, f)

            mgr = GlossaryManager()
            count = mgr.load_from_file(json_file)
            self.assertEqual(count, 2)
            self.assertIn("manifold", mgr.entries)

            # CSV file
            csv_file = Path(tmpdir) / "glossary.csv"
            with open(csv_file, "w", encoding="utf-8") as f:
                f.write("gradient,độ dốc\nbackpropagation,lan truyền ngược\n")

            count_csv = mgr.load_from_file(csv_file)
            self.assertEqual(count_csv, 2)
            self.assertIn("gradient", mgr.entries)

    def test_acronym_extraction(self):
        text = "We evaluate CNN, LSTM, and BLEU-4 scores on GPU clusters."
        acronyms = GlossaryManager.extract_document_acronyms(text)
        self.assertIn("CNN", acronyms)
        self.assertIn("LSTM", acronyms)
        self.assertIn("BLEU-4", acronyms)
        self.assertIn("GPU", acronyms)


if __name__ == "__main__":
    unittest.main()
