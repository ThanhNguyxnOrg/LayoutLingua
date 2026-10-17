"""Unit and regression tests for typography fidelity, font fitting, and glyph preservation.

Validates:
1. Headings (single-line 14pt-18pt) preserve >= 95% of original font size after translation.
2. Binary search does not collapse font size due to PyMuPDF ink-height bounding box deficit.
3. Zero '?' or '\ufffd' glyph replacement for mathematical symbols (° ± ∓ ≤ ≥ ≈ α β π) with DejaVuSans.
4. Hex color isolation (e.g. blue heading #004b87 vs black paragraph #000000).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from layoutlingua.typesetting import (
    FontManager,
    TypesetEngine,
    TypesetOptions,
)
from layoutlingua.typesetting.fitting import TextFitTester


class TestAcademicTypographyFidelity(unittest.TestCase):
    """Test suite ensuring zero font collapse, zero corrupted math glyphs, and exact colors."""

    def setUp(self) -> None:
        self.font_manager = FontManager()
        self.tester = TextFitTester(self.font_manager)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Heading Font Preservation (No Spurious Shrinkage)
    # -------------------------------------------------------------------------

    def test_single_line_heading_preserves_full_font_size(self) -> None:
        """Single-line headings fitting horizontally must preserve >= 95% of original font size."""
        headings = [
            ("3. Chỉnh hợp (không lặp)", 14.0, (50.0, 100.0, 450.0, 115.0)),
            ("3. Permutation (without repetition)", 14.0, (50.0, 100.0, 450.0, 115.0)),
            ("Mục lục", 16.0, (50.0, 50.0, 450.0, 68.0)),
            ("Table of Contents", 16.0, (50.0, 50.0, 450.0, 68.0)),
            ("f) Đa giác đều n cạnh", 12.0, (50.0, 200.0, 400.0, 213.0)),
        ]
        options = TypesetOptions(min_font_scale=0.60, min_font_pt=6.0)

        for text, orig_size, rect in headings:
            fits, final_size, cause, lines, lineheight = self.tester.test_fit(
                rect=rect,
                text=text,
                orig_font_size=orig_size,
                options=options,
            )
            self.assertTrue(fits, f"Heading '{text}' must fit successfully.")
            self.assertGreaterEqual(
                final_size,
                orig_size * 0.95,
                f"Heading '{text}' collapsed from {orig_size}pt to {final_size}pt (must be >= {orig_size * 0.95}pt).",
            )
            self.assertEqual(lines, 1, f"Heading '{text}' must remain on a single line.")

    def test_ink_bbox_height_deficit_does_not_collapse_font(self) -> None:
        """In PyMuPDF, ink bbox height is often ~10.5pt for 10pt font. Fitting tester must not collapse."""
        # bbox height is 11.0 pt, while font size is 10.0 pt (ink bbox from get_text("blocks"))
        tight_rect = (50.0, 100.0, 500.0, 111.0)
        text = "1. Introduction to Computational Mathematics"
        options = TypesetOptions(min_font_scale=0.60, min_font_pt=6.0)

        fits, final_size, cause, lines, lineheight = self.tester.test_fit(
            rect=tight_rect,
            text=text,
            orig_font_size=10.0,
            options=options,
        )
        self.assertTrue(fits)
        self.assertGreaterEqual(final_size, 9.5, "Font size must not collapse on tight ink bbox.")

    # -------------------------------------------------------------------------
    # 2. Unicode Math Glyphs Preservation (Zero Question Mark '?')
    # -------------------------------------------------------------------------

    def test_unicode_math_symbols_render_without_question_marks(self) -> None:
        """Mathematical symbols and Greek letters rendered with DejaVuSans must NOT produce '?' in PDF."""
        doc = pymupdf.open()
        page = doc.new_page(width=595.0, height=842.0)
        font_path = str(self.font_manager.font_path)
        page.insert_font(fontname="DejaVuSans", fontfile=font_path)

        test_text = (
            "Góc 60° và 360° ± α. "
            "Quan hệ: x ≥ y, a ≤ b, f(x) ≈ g(x), u ≠ v. "
            "Ký hiệu: ∓, π, θ, β, ∑, √Δ."
        )

        rect = pymupdf.Rect(50, 100, 550, 180)
        page.insert_textbox(
            rect,
            test_text,
            fontname="DejaVuSans",
            fontsize=12,
            color=(0, 0, 0),
        )

        out_pdf = self.temp_path / "unicode_math_test.pdf"
        doc.save(str(out_pdf))
        doc.close()

        # Reopen and inspect extracted text
        doc_read = pymupdf.open(str(out_pdf))
        extracted = doc_read[0].get_text()
        doc_read.close()

        # Must NOT contain replacement '?' or '\ufffd'
        self.assertNotIn("?", extracted, "Extracted text must not contain '?' for math glyphs.")
        self.assertNotIn("\ufffd", extracted, "Extracted text must not contain replacement character \\ufffd.")

        # Key symbols must be explicitly present
        for sym in ["60°", "360°", "±", "α", "≥", "≤", "≈", "≠", "∓", "π", "θ", "β", "∑", "√Δ"]:
            self.assertIn(sym, extracted, f"Symbol '{sym}' must be accurately preserved in the rendered PDF.")

    # -------------------------------------------------------------------------
    # 3. Heading Color Isolation
    # -------------------------------------------------------------------------

    def test_heading_color_preservation_and_isolation(self) -> None:
        """Colored headings (#004b87) must retain their exact color without bleeding into black paragraphs."""
        doc = pymupdf.open()
        page = doc.new_page(width=595.0, height=842.0)
        font_path = str(self.font_manager.font_path)
        page.insert_font(fontname="DejaVuSans", fontfile=font_path)

        # Blue heading: #004b87 -> (0.0, 0.294, 0.529)
        blue_rgb = (0.0, 75.0 / 255.0, 135.0 / 255.0)
        page.insert_textbox(
            pymupdf.Rect(50, 50, 500, 80),
            "1. SỐ HỌC VÀ ĐẠI SỐ",
            fontname="DejaVuSans",
            fontsize=14,
            color=blue_rgb,
        )

        # Black body text: #000000 -> (0.0, 0.0, 0.0)
        page.insert_textbox(
            pymupdf.Rect(50, 90, 500, 150),
            "Nội dung phần đại số mô tả các quy tắc đếm cơ bản.",
            fontname="DejaVuSans",
            fontsize=10,
            color=(0.0, 0.0, 0.0),
        )

        out_pdf = self.temp_path / "color_isolation.pdf"
        doc.save(str(out_pdf))
        doc.close()

        # Inspect extracted rawdict
        doc_read = pymupdf.open(str(out_pdf))
        raw_dict = doc_read[0].get_text("rawdict")
        doc_read.close()

        text_blocks = [b for b in raw_dict.get("blocks", []) if b.get("type") == 0]
        self.assertGreaterEqual(len(text_blocks), 2, "Must contain at least 2 distinct text blocks.")

        # Heading span color
        heading_color = text_blocks[0]["lines"][0]["spans"][0]["color"]
        # Body text span color
        body_color = text_blocks[1]["lines"][0]["spans"][0]["color"]

        self.assertNotEqual(
            heading_color,
            body_color,
            "Heading color and body color must be completely isolated.",
        )
        # Heading color sRGB int: (0 << 16) | (75 << 8) | 135 = 19335
        expected_blue_int = (0 << 16) | (75 << 8) | 135
        self.assertEqual(heading_color, expected_blue_int)
        self.assertEqual(body_color, 0)


if __name__ == "__main__":
    unittest.main()
