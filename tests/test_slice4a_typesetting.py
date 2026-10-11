"""Comprehensive unit and regression tests for Slice 4A Typesetting & Reflow Engine.

Validates:
1. Font asset checksum integrity and 100% Vietnamese composite glyph coverage.
2. Tier 1: PDF Structural validity (re-openable, valid geometry, page count preserved).
3. Tier 2: Text extraction and geometry invariants (Vietnamese text present, formula intact).
4. Tier 2: Adaptive font shrinkage and fail-closed overflow handling (source preserved).
5. Tier 3: Background preservation (tinted boxes & vector borders intact via fill=False).
6. End-to-end integration from Native-text PDF -> Parser -> Mock Provider -> TypesetEngine.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from layoutlingua.core.parser import parse_pdf
from layoutlingua.translation.mock import MockTranslationProvider
from layoutlingua.translation.models import TranslationJob
from layoutlingua.translation.service import TranslationService
from layoutlingua.typesetting import (
    BlockFittingStatus,
    FontManager,
    FontValidationError,
    TypesetEngine,
    TypesetOptions,
)
from layoutlingua.typesetting.fonts import EXPECTED_DEJAVU_SHA256


class TestSlice4ATypesetting(unittest.TestCase):
    """Test suite for Slice 4A TypesetEngine and font fitting."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Font Asset & Checksum Tests
    # -------------------------------------------------------------------------

    def test_font_asset_checksum_and_vietnamese_glyphs(self) -> None:
        """Verify bundled DejaVuSans.ttf exists, has correct SHA-256, and covers all Vietnamese glyphs."""
        manager = FontManager()
        self.assertTrue(manager.font_path.is_file())
        self.assertTrue(manager.verify_checksum(EXPECTED_DEJAVU_SHA256))

        missing = manager.validate_vietnamese_glyphs()
        self.assertEqual(missing, [], "Bundled font must cover all Vietnamese composite glyphs.")

    def test_font_checksum_mismatch_raises_error(self) -> None:
        """Verify that a corrupted font checksum raises FontValidationError."""
        manager = FontManager()
        with self.assertRaises(FontValidationError):
            manager.verify_checksum("invalid_sha256_hash_value_12345")

    # -------------------------------------------------------------------------
    # 2. Synthetic PDF Fixtures
    # -------------------------------------------------------------------------

    def _create_sample_pdf(self) -> bytes:
        """Create a standard native-text PDF with headings, paragraphs, and formulas."""
        doc = pymupdf.open()
        page = doc.new_page(width=595.0, height=842.0)  # A4

        # Title
        page.insert_textbox(
            pymupdf.Rect(50, 50, 500, 90),
            "Document Translation Architecture",
            fontsize=18,
            color=(0.1, 0.1, 0.1),
        )

        # Paragraph
        page.insert_textbox(
            pymupdf.Rect(50, 110, 500, 200),
            "Deep learning systems utilize decoupled intermediate representations for robust processing "
            "across multiple document layouts. They preserve typography and prevent visual distortion.",
            fontsize=11,
            color=(0.2, 0.2, 0.2),
        )

        # Math formula area
        page.insert_textbox(
            pymupdf.Rect(50, 220, 500, 260),
            "E = mc^2",
            fontsize=14,
            color=(0.0, 0.0, 0.5),
        )

        return doc.tobytes()

    def _create_background_fixture_pdf(self) -> bytes:
        """Create a PDF with a tinted background box, vector borders, and text inside."""
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=400)

        # 1. Draw a tinted blue callout box with a navy border
        callout_rect = pymupdf.Rect(40, 40, 360, 200)
        page.draw_rect(callout_rect, color=(0.0, 0.0, 0.6), fill=(0.85, 0.92, 1.0), width=2.0)

        # 2. Insert text inside the tinted callout box
        text_rect = pymupdf.Rect(60, 60, 340, 150)
        page.insert_textbox(
            text_rect,
            "Important note regarding academic research findings.",
            fontsize=12,
            color=(0.0, 0.0, 0.0),
        )

        return doc.tobytes()

    # -------------------------------------------------------------------------
    # 3. Core Typesetting & Background Preservation Tests
    # -------------------------------------------------------------------------

    def test_typeset_basic_replacement_and_structural_validity(self) -> None:
        """Verify Tier 1 & 2: Output PDF is valid, Vietnamese text replaces source, geometry preserved."""
        pdf_bytes = self._create_sample_pdf()
        pdf_file = self.temp_path / "sample.pdf"
        pdf_file.write_bytes(pdf_bytes)

        # Parse IR
        doc_ir = parse_pdf(pdf_file)
        self.assertGreater(len(doc_ir.pages), 0)

        # Target first text block for translation
        first_block = doc_ir.pages[0].blocks[0]
        vietnamese_text = "Kiến trúc Biên dịch Tài liệu Học thuật"
        translations = {first_block.block_id: vietnamese_text}

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        # Tier 1: PDF Structural Check
        self.assertIsInstance(result.pdf_bytes, bytes)
        self.assertGreater(len(result.pdf_bytes), 1000)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(len(out_doc), 1)
        out_page = out_doc[0]
        self.assertAlmostEqual(out_page.rect.width, 595.0, delta=1.0)
        self.assertAlmostEqual(out_page.rect.height, 842.0, delta=1.0)

        # Tier 2: Text Extraction Invariant
        extracted_text = out_page.get_text()
        self.assertIn("Kiến trúc", extracted_text)
        self.assertIn("Học thuật", extracted_text)
        # Original replaced title should not be in the page text
        self.assertNotIn("Document Translation Architecture", extracted_text)

        # Telemetry verification
        self.assertEqual(result.fitting_report.replaced_blocks, 1)
        self.assertEqual(result.fitting_report.overflow_blocks, 0)

    def test_typeset_background_preservation_with_transparent_redaction(self) -> None:
        """Verify Tier 3: fill=False preserves tinted background fill and vector drawing."""
        pdf_bytes = self._create_background_fixture_pdf()
        pdf_file = self.temp_path / "bg_fixture.pdf"
        pdf_file.write_bytes(pdf_bytes)

        doc_ir = parse_pdf(pdf_file)
        first_block = doc_ir.pages[0].blocks[0]
        vietnamese_text = "Ghi chú quan trọng về các phát hiện nghiên cứu học thuật."
        translations = {first_block.block_id: vietnamese_text}

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        out_page = out_doc[0]

        # Verify translated text exists
        self.assertIn("Ghi chú", out_page.get_text())

        # Render to pixmap and verify background tint is preserved
        pix = out_page.get_pixmap()
        # Sample empty space inside the tinted box at (300, 100)
        sample = pix.pixel(300, 100)
        # Target tint: (0.85*255, 0.92*255, 1.0*255) ~ (216, 234, 255)
        # If fill was white (1, 1, 1), sample would be (255, 255, 255)
        self.assertLess(sample[0], 230, "Red channel must remain tinted, not white.")
        self.assertGreater(sample[2], 245, "Blue channel must remain saturated.")

    def test_adaptive_font_shrinkage_fits_expanded_text(self) -> None:
        """Verify that moderately expanded text triggers font reduction and successfully fits."""
        pdf_bytes = self._create_sample_pdf()
        pdf_file = self.temp_path / "sample_shrink.pdf"
        pdf_file.write_bytes(pdf_bytes)

        doc_ir = parse_pdf(pdf_file)
        # Second block is the paragraph
        para_block = doc_ir.pages[0].blocks[1]
        orig_size = max(s.font_size for s in para_block.spans)

        # Longer Vietnamese translation (25% expansion)
        expanded_vn = (
            "Các hệ thống học sâu tiên tiến vận dụng cấu trúc biểu diễn trung gian phân rã "
            "để bảo toàn cấu trúc hình học một cách tối ưu và đáng tin cậy."
        )
        translations = {para_block.block_id: expanded_vn}

        engine = TypesetEngine(options=TypesetOptions(min_font_scale=0.70))
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        self.assertEqual(result.fitting_report.replaced_blocks, 1)
        detail = [d for d in result.fitting_report.details if d.block_id == para_block.block_id][0]
        self.assertEqual(detail.status, BlockFittingStatus.SUCCESS)
        # Font should have been scaled down or kept within bounds
        self.assertLessEqual(detail.final_font_size, orig_size)
        self.assertGreaterEqual(detail.final_font_size, orig_size * 0.70)

    def test_fail_closed_overflow_preserves_source_text(self) -> None:
        """Verify fail-closed invariant: text exceeding capacity even at floor keeps source text."""
        pdf_bytes = self._create_sample_pdf()
        pdf_file = self.temp_path / "sample_overflow.pdf"
        pdf_file.write_bytes(pdf_bytes)

        doc_ir = parse_pdf(pdf_file)
        title_block = doc_ir.pages[0].blocks[0]  # Small box for title

        # Extremely long text that cannot possibly fit in 500x40 box at >= 6pt
        massive_text = "Đây là một đoạn văn bản cực kỳ dài " * 20
        translations = {title_block.block_id: massive_text}

        engine = TypesetEngine(options=TypesetOptions(fail_closed=True, min_font_scale=0.70))
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        # Telemetry must record overflow
        self.assertEqual(result.fitting_report.overflow_blocks, 1)
        self.assertEqual(result.fitting_report.replaced_blocks, 0)

        # Output page must preserve the original title text intact!
        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        page_text = out_doc[0].get_text()
        self.assertIn("Document Translation Architecture", page_text)
        self.assertNotIn("Đây là một đoạn văn bản cực kỳ dài", page_text)

    def test_formula_block_is_preserved_and_skipped(self) -> None:
        """Verify that blocks with block_type='formula' are skipped and preserved intact."""
        pdf_bytes = self._create_sample_pdf()
        pdf_file = self.temp_path / "sample_formula.pdf"
        pdf_file.write_bytes(pdf_bytes)

        doc_ir = parse_pdf(pdf_file)
        # Set third block to formula block type
        formula_block = doc_ir.pages[0].blocks[2]
        formula_block.block_type = "formula"

        translations = {formula_block.block_id: "Công thức E = mc^2 đã dịch"}

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        detail = [d for d in result.fitting_report.details if d.block_id == formula_block.block_id][0]
        self.assertEqual(detail.status, BlockFittingStatus.SKIPPED_FORMULA)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertIn("E = mc^2", out_doc[0].get_text())

    # -------------------------------------------------------------------------
    # 4. End-to-End Vertical Slice Integration Pipeline
    # -------------------------------------------------------------------------

    def test_end_to_end_vertical_slice_pipeline(self) -> None:
        """Verify full loop: Native-text PDF -> parse_pdf -> TranslationService -> TypesetEngine."""
        pdf_bytes = self._create_sample_pdf()
        pdf_file = self.temp_path / "e2e_input.pdf"
        pdf_file.write_bytes(pdf_bytes)

        # 1. Parse PDF into IR
        doc_ir = parse_pdf(pdf_file)
        self.assertGreater(len(doc_ir.pages[0].blocks), 0)

        # 2. Translate segments via TranslationService
        from layoutlingua.processing.formula.models import TextSegment

        job_segments = [
            TextSegment(segment_id=b.block_id, masked_text=b.text, raw_text=b.text)
            for b in doc_ir.pages[0].blocks
            if b.text.strip()
        ]

        # Use Mock provider with deterministic translation map
        mock_provider = MockTranslationProvider()
        mock_provider.translations = {
            doc_ir.pages[0].blocks[0].text: "Kiến trúc Dịch Tài liệu Tự động",
            doc_ir.pages[0].blocks[1].text: "Hệ thống học sâu sử dụng biểu diễn trung gian.",
        }

        db_path = self.temp_path / "trans.sqlite"
        service = TranslationService(provider=mock_provider, db_path=db_path)
        try:
            job = TranslationJob(
                job_id="job_slice4a_e2e",
                document_fingerprint="doc_test_fingerprint_4a",
                source_language="en",
                target_language="vi",
                segments=job_segments,
            )
            job_result = service.translate_job(job)
            self.assertEqual(job_result.status.value, "COMPLETED")

            translations = job_result.translated_segments

            # 3. Typeset & Reflow
            engine = TypesetEngine()
            typeset_result = engine.typeset(
                original_pdf=pdf_bytes,
                document_ir=doc_ir,
                translated_segments=translations,
            )

            # 4. Assertions on output PDF
            self.assertGreater(len(typeset_result.pdf_bytes), 1000)
            self.assertGreaterEqual(typeset_result.fitting_report.replaced_blocks, 2)

            out_doc = pymupdf.open(stream=typeset_result.pdf_bytes, filetype="pdf")
            out_text = out_doc[0].get_text()
            self.assertIn("[VI] Document Translation Architecture", out_text)
            self.assertIn("[VI] Deep learning systems", out_text)
            self.assertIn("E = mc^2", out_text)
        finally:
            service.close()

    # -------------------------------------------------------------------------
    # 5. Regression Tests: Precision, Fallback Integrity & Diacritic Bounds
    # -------------------------------------------------------------------------

    def test_redaction_does_not_corrupt_adjacent_formula_text_or_vector_drawing(self) -> None:
        """Verify selective redaction does not erase tightly adjacent formulas, text, or vector rules."""
        doc = pymupdf.open()
        page = doc.new_page(width=500, height=300)

        # 1. Text block to be replaced (y: 40 to 80)
        page.insert_textbox(pymupdf.Rect(50, 40, 450, 80), "Header Title to Replace", fontsize=14)

        # 2. Vector dividing line right below it (y: 88, only 8 pt away!)
        page.draw_line(pymupdf.Point(50, 88), pymupdf.Point(450, 88), color=(0.85, 0.1, 0.1), width=2.0)

        # 3. Formula block directly below vector line (y: 95 to 130)
        page.insert_textbox(pymupdf.Rect(50, 95, 250, 130), "\\nabla \\times E = -\\partial B/\\partial t", fontsize=11)

        # 4. Adjacent text note horizontally right of formula (x: 260 to 450)
        page.insert_textbox(pymupdf.Rect(260, 95, 450, 130), "Maxwell Faraday Equation", fontsize=11)

        pdf_bytes = doc.tobytes()
        pdf_file = self.temp_path / "adjacent_fixture.pdf"
        pdf_file.write_bytes(pdf_bytes)

        doc_ir = parse_pdf(pdf_file)
        header_block = doc_ir.pages[0].blocks[0]
        translations = {header_block.block_id: "Tiêu đề Header Đã Dịch"}

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        out_page = out_doc[0]
        out_text = out_page.get_text()

        # Invariant 1: Header is translated
        self.assertIn("Tiêu đề Header Đã Dịch", out_text)
        self.assertNotIn("Header Title to Replace", out_text)

        # Invariant 2: Adjacent formula and annotation are 100% intact
        self.assertIn("\\nabla \\times E", out_text)
        self.assertIn("Maxwell Faraday Equation", out_text)

        # Invariant 3: Vector red line is visually preserved (sample pixel at 100, 88)
        pix = out_page.get_pixmap()
        line_pixel = pix.pixel(100, 88)
        # Red line: r channel must be prominent, blue/green low
        self.assertGreater(line_pixel[0], 180, "Red vector line must not be wiped out by redaction.")
        self.assertLess(line_pixel[1], 80, "Green channel should remain low for red line.")

    def test_overflow_fallback_integrity_no_duplicate_or_lost_text(self) -> None:
        """Verify that overflow fallback retains exactly one copy of source text and never duplicates."""
        doc = pymupdf.open()
        page = doc.new_page(width=500, height=300)

        # Block 1 (fits):
        page.insert_textbox(pymupdf.Rect(50, 40, 450, 80), "Short Intro Sentence", fontsize=12)
        # Block 2 (will overflow):
        page.insert_textbox(pymupdf.Rect(50, 100, 450, 130), "Important Conclusion Statement", fontsize=12)

        pdf_bytes = doc.tobytes()
        pdf_file = self.temp_path / "overflow_integrity.pdf"
        pdf_file.write_bytes(pdf_bytes)

        doc_ir = parse_pdf(pdf_file)
        b1 = doc_ir.pages[0].blocks[0]
        b2 = doc_ir.pages[0].blocks[1]

        translations = {
            b1.block_id: "Câu mở đầu ngắn gọn",
            b2.block_id: "Một đoạn văn bản dịch cực kỳ dài bị cố tình lặp lại nhiều lần " * 15,
        }

        engine = TypesetEngine(options=TypesetOptions(fail_closed=True))
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        self.assertEqual(result.fitting_report.replaced_blocks, 1)
        self.assertEqual(result.fitting_report.overflow_blocks, 1)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        out_text = out_doc[0].get_text()

        # Block 1 successfully replaced
        self.assertIn("Câu mở đầu ngắn gọn", out_text)
        self.assertNotIn("Short Intro Sentence", out_text)

        # Block 2 retained source text exactly once
        self.assertEqual(out_text.count("Important Conclusion Statement"), 1)
        # Overflow text must NOT appear on page
        self.assertNotIn("Một đoạn văn bản dịch cực kỳ dài", out_text)

    def test_complex_vietnamese_stacked_diacritics_visual_containment(self) -> None:
        """Verify that complex Vietnamese stacked diacritics (nghiễm, trưởng, ngưỡng, nguyễn) render within bounds."""
        doc = pymupdf.open()
        page = doc.new_page(width=500, height=300)
        orig_en = "Academic research study by author Nguyen Van Truong admiring the rigorous discipline."
        target_rect = pymupdf.Rect(50, 50, 450, 150)
        page.insert_textbox(target_rect, orig_en, fontsize=12)

        pdf_bytes = doc.tobytes()
        pdf_file = self.temp_path / "diacritics_fixture.pdf"
        pdf_file.write_bytes(pdf_bytes)

        doc_ir = parse_pdf(pdf_file)
        block = doc_ir.pages[0].blocks[0]

        complex_vn_text = "Nghiên cứu của tác giả Nguyễn Văn Trưởng ngưỡng mộ sự nghiêm ngặt nghiễm nhiên."
        translations = {block.block_id: complex_vn_text}

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        out_page = out_doc[0]

        # Verify Unicode text extraction
        extracted = out_page.get_text()
        self.assertIn("Nguyễn Văn Trưởng", extracted)
        self.assertIn("ngưỡng mộ", extracted)
        self.assertIn("nghiễm nhiên", extracted)

        # Verify geometric bounding containment of rendered spans
        raw = out_page.get_text("rawdict")
        for b in raw["blocks"]:
            if b.get("type") == 0:
                for line in b.get("lines", []):
                    line_bbox = line["bbox"]
                    # Top of line must not breach above target_rect top
                    self.assertGreaterEqual(line_bbox[1], target_rect.y0 - 2.0)
                    # Bottom of line must not breach target_rect bottom
                    self.assertLessEqual(line_bbox[3], target_rect.y1 + 2.0)


if __name__ == "__main__":
    unittest.main()

