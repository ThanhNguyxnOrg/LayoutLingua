"""Unit tests for the Enhanced Formula Protection and Recovery module."""

import unittest
from pdf2zh.formula import (
    extract_placeholder_ids,
    normalize_mt_placeholders,
    validate_formula_integrity,
)


class TestFormulaRecovery(unittest.TestCase):
    def test_normalize_html_escaped_placeholders(self):
        raw = "Phương trình &lt;b12&gt;&lt;/b12&gt; đại diện cho ma trận"
        normalized = normalize_mt_placeholders(raw)
        self.assertEqual(normalized, "Phương trình <b12></b12> đại diện cho ma trận")

    def test_normalize_spaced_placeholder_tags(self):
        raw = "Kết quả < b 42 > < / b 42 > và <  b 99  ></b99>"
        normalized = normalize_mt_placeholders(raw)
        self.assertIn("<b42></b42>", normalized)
        self.assertIn("<b99></b99>", normalized)

    def test_normalize_spaced_style_tags(self):
        raw = "Chữ < s 1 > đậm < / s 1 > và chữ < s 2 > nghiêng < / s 2 >"
        normalized = normalize_mt_placeholders(raw)
        self.assertEqual(normalized, "Chữ <s1> đậm </s1> và chữ <s2> nghiêng </s2>")

    def test_extract_placeholder_ids(self):
        text = "<b1></b1> some text <b4></b4> more text <b99></b99>"
        ids = extract_placeholder_ids(text)
        self.assertEqual(ids, {1, 4, 99})

    def test_validate_formula_integrity(self):
        src = "<b1></b1> text <b2></b2>"
        dst_valid = "văn bản <b2></b2> rồi đến <b1></b1>"  # natural grammar reordering
        valid, msg = validate_formula_integrity(src, dst_valid)
        self.assertTrue(valid)
        self.assertIsNone(msg)

        dst_missing = "văn bản <b1></b1> thiếu b2"
        valid, msg = validate_formula_integrity(src, dst_missing)
        self.assertFalse(valid)
        self.assertIn("Missing formula placeholders", msg)

        dst_unclosed = "văn bản <b1></b1> và <b2>"
        valid, msg = validate_formula_integrity(src, dst_unclosed)
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()
