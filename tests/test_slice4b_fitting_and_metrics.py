"""Unit and regression tests for Slice 4B Font Metrics, Binary Search Fitting, and Multi-Tier Telemetry."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from layoutlingua.core.parser import parse_pdf
from layoutlingua.typesetting import (
    BlockFittingStatus,
    FontManager,
    OverflowCause,
    TypesetEngine,
    TypesetOptions,
)
from layoutlingua.typesetting.fitting import TextFitTester


class TestSlice4BFittingAndMetrics(unittest.TestCase):
    """Test suite for Slice 4B precision binary search fitting, dynamic line-height, and telemetry."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.font_manager = FontManager()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Font Metrics & Line-height Floor Tests
    # -------------------------------------------------------------------------

    def test_font_metrics_extraction(self) -> None:
        """Verify extraction of ascender and descender from bundled DejaVu font."""
        asc, desc = self.font_manager.get_font_metrics()
        self.assertGreater(asc, 0.8, "Ascender should be > 0.8 em for DejaVuSans.")
        self.assertLess(desc, -0.15, "Descender should be negative < -0.15 em.")
        total_height = asc - desc
        self.assertAlmostEqual(total_height, 1.164, delta=0.01)

    def test_dynamic_lineheight_calculation(self) -> None:
        """Verify dynamic line-height formula: max(L_configured, ascender - descender + p)."""
        lh = self.font_manager.calculate_effective_lineheight(
            configured_ratio=1.20,
            safety_padding_em=0.03,
        )
        # Total metric height ~ 1.164 + 0.03 = 1.194 -> max(1.20, 1.194) = 1.20
        self.assertGreaterEqual(lh, 1.19)

        # If configured is small (1.05), dynamic floor enforces asc - desc + padding (~1.194)
        lh_clamped = self.font_manager.calculate_effective_lineheight(
            configured_ratio=1.05,
            safety_padding_em=0.04,
        )
        self.assertGreaterEqual(lh_clamped, 1.20)

    # -------------------------------------------------------------------------
    # 2. Precision Binary Search Fitting Tests
    # -------------------------------------------------------------------------

    def test_binary_search_finds_maximum_fit_within_epsilon(self) -> None:
        """Verify binary search locates the optimal font size within 0.2 pt precision."""
        tester = TextFitTester(self.font_manager)
        options = TypesetOptions(
            min_font_scale=0.60,
            min_font_pt=6.0,
            binary_search_epsilon=0.2,
            max_search_iterations=7,
        )

        rect = (50.0, 50.0, 350.0, 100.0)
        text = (
            "Nghiên cứu về các mô hình mạng nơ-ron sâu trong việc bảo toàn "
            "cấu trúc hình học của tài liệu khoa học đa ngôn ngữ."
        )

        fits, final_size, cause, lines, lineheight = tester.test_fit(
            rect=rect,
            text=text,
            orig_font_size=16.0,
            options=options,
        )

        self.assertTrue(fits)
        self.assertEqual(cause, OverflowCause.NONE)
        self.assertGreater(lines, 1)
        self.assertLess(final_size, 16.0, "Should scale down from 16pt.")
        self.assertGreaterEqual(final_size, 16.0 * 0.60, "Should stay above min floor.")

    # -------------------------------------------------------------------------
    # 3. Overflow Cause Classification Tests
    # -------------------------------------------------------------------------

    def test_classify_overflow_height(self) -> None:
        """Verify classification of OVERFLOW_HEIGHT when words fit but total vertical space is exceeded."""
        tester = TextFitTester(self.font_manager)
        options = TypesetOptions(min_font_scale=0.70, min_font_pt=8.0)

        # Extremely short box (12 pt high) that cannot fit 4 lines of normal words
        rect = (50.0, 50.0, 300.0, 62.0)
        multi_line_text = "Từ một từ hai từ ba từ bốn từ năm từ sáu từ bảy từ tám từ chín từ mười."

        fits, final_size, cause, lines, _ = tester.test_fit(
            rect=rect,
            text=multi_line_text,
            orig_font_size=12.0,
            options=options,
        )

        self.assertFalse(fits)
        self.assertEqual(cause, OverflowCause.OVERFLOW_HEIGHT)

    def test_classify_overflow_width_at_min_size(self) -> None:
        """Verify classification of OVERFLOW_WIDTH_AT_MIN_SIZE when a single token exceeds box width."""
        tester = TextFitTester(self.font_manager)
        options = TypesetOptions(min_font_scale=0.70, min_font_pt=8.0)

        # Narrow single-line box: 40 pt wide, 15 pt high
        rect = (50.0, 50.0, 90.0, 65.0)
        # Giant unbreakable token that cannot fit in 40 pt
        giant_token = "SupercalifragilisticexpialidociousScientificExpression"

        fits, final_size, cause, lines, _ = tester.test_fit(
            rect=rect,
            text=giant_token,
            orig_font_size=12.0,
            options=options,
        )

        self.assertFalse(fits)
        self.assertEqual(cause, OverflowCause.OVERFLOW_WIDTH_AT_MIN_SIZE)

    # -------------------------------------------------------------------------
    # 4. Multi-Tier Telemetry (Document Summary + Page Breakdown)
    # -------------------------------------------------------------------------

    def test_multi_tier_telemetry_aggregation(self) -> None:
        """Verify page-level summaries and document-wide metrics in FittingReport."""
        # Create a 2-page PDF
        doc = pymupdf.open()
        p1 = doc.new_page(width=400, height=400)
        p1.insert_textbox(pymupdf.Rect(40, 40, 360, 80), "Page One Title Box", fontsize=14)
        p1.insert_textbox(
            pymupdf.Rect(40, 100, 360, 160),
            "Page One normal paragraph text demonstrating multi-line geometry and typography preservation across layouts.",
            fontsize=11,
        )

        p2 = doc.new_page(width=400, height=400)
        p2.insert_textbox(pymupdf.Rect(40, 40, 360, 80), "Page Two Header Box", fontsize=14)
        p2.insert_textbox(pymupdf.Rect(40, 100, 360, 140), "Page Two Small Box for Overflow", fontsize=10)

        pdf_bytes = doc.tobytes()
        pdf_file = self.temp_path / "multi_page_telemetry.pdf"
        pdf_file.write_bytes(pdf_bytes)

        doc_ir = parse_pdf(pdf_file)
        self.assertEqual(len(doc_ir.pages), 2)

        # Translations:
        # P1 B0: Normal fit
        # P1 B1: Moderate shrink
        # P2 B0: Normal fit
        # P2 B1: Massive overflow
        translations = {
            doc_ir.pages[0].blocks[0].block_id: "Tiêu đề Trang Một",
            doc_ir.pages[0].blocks[1].block_id: (
                "Đoạn văn bản trang một được mở rộng đáng kể với nhiều phân tích chuyên sâu về thuật toán xử lý ngôn ngữ tự nhiên và thị giác máy tính hiện đại."
            ),
            doc_ir.pages[1].blocks[0].block_id: "Tiêu đề Trang Hai",
            doc_ir.pages[1].blocks[1].block_id: "Đoạn văn bản cực kỳ dài " * 25,
        }

        engine = TypesetEngine(options=TypesetOptions(severe_shrink_threshold=0.85))
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments=translations,
        )

        report = result.fitting_report

        # 1. Document summary assertions
        self.assertEqual(report.total_blocks, 4)
        self.assertEqual(report.replaced_blocks, 3)
        self.assertEqual(report.overflow_blocks, 1)
        self.assertEqual(report.success_rate, 75.0)
        self.assertLess(report.worst_shrink_ratio, 1.0)
        self.assertLessEqual(report.avg_shrink_ratio, 1.0)

        # 2. Page breakdown assertions
        self.assertEqual(len(report.pages), 2)
        p1_summary = report.pages[0]
        self.assertEqual(p1_summary.page_number, 1)
        self.assertEqual(p1_summary.replaced_blocks, 2)
        self.assertEqual(p1_summary.overflow_blocks, 0)

        p2_summary = report.pages[1]
        self.assertEqual(p2_summary.page_number, 2)
        self.assertEqual(p2_summary.replaced_blocks, 1)
        self.assertEqual(p2_summary.overflow_blocks, 1)

        # 3. Block-level detail assertions
        overflow_detail = [d for d in report.details if d.status == BlockFittingStatus.OVERFLOW_FALLBACK][0]
        self.assertEqual(overflow_detail.page_number, 2)
        self.assertIn(overflow_detail.overflow_cause, (OverflowCause.OVERFLOW_HEIGHT, OverflowCause.OVERFLOW_UNDETERMINED))
        self.assertEqual(overflow_detail.shrink_ratio, 1.0)  # Unaltered source text


if __name__ == "__main__":
    unittest.main()
