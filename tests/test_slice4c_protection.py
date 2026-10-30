"""Tests for Slice 4C.1: Structural Protection and Clearance Planner.

Verifies:
1. Multi-source ExclusionZone extraction (formulas, adjacent text, images, vector art).
2. Tight line-level clearance bounding boxes (<= 0.5 pt padding, not raw block bbox).
3. Background Container vs Forbidden Vector Art classification.
4. Structured COLLISION_FALLBACK telemetry and source text preservation.
5. Mutual candidate clearance conflict resolution.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pymupdf

from layoutlingua.core.ir import CharInfo, DocumentIR, GlyphSpan, LayoutRegion, PageGeometry, PageIR, TextBlock
from layoutlingua.typesetting.engine import TypesetEngine
from layoutlingua.typesetting.models import (
    BlockFittingStatus,
    CollisionDetail,
    TypesetOptions,
)
from layoutlingua.typesetting.protection import (
    ClearancePlan,
    ClearancePlanner,
    ExclusionZone,
    ExclusionZoneType,
    compute_tight_line_clearance_regions,
    is_background_container,
    rects_intersect,
)


class TestSlice4CProtection(unittest.TestCase):
    """Test suite for Slice 4C.1 structural protection and clearance planning."""

    def test_rects_intersect(self) -> None:
        """Verify strict AABB intersection logic with tolerance."""
        r1 = (10.0, 10.0, 50.0, 50.0)
        r2 = (40.0, 40.0, 80.0, 80.0)  # Overlapping
        r3 = (50.0, 50.0, 90.0, 90.0)  # Touching at corner (no area overlap)
        r4 = (60.0, 60.0, 100.0, 100.0)  # Disjoint

        self.assertTrue(rects_intersect(r1, r2))
        self.assertFalse(rects_intersect(r1, r3))
        self.assertFalse(rects_intersect(r1, r4))

    def test_tight_line_clearance_calculation(self) -> None:
        """Verify tight clearance boxes per line/span with max 0.5 pt padding."""
        # Create a 2-line TextBlock with explicit character bboxes
        span1 = GlyphSpan(
            span_id="p1_b0_l0_s0",
            text="Line One",
            bbox=(72.0, 100.0, 150.0, 112.0),
            font_name="DejaVuSans",
            font_size=10.0,
            color="#000000",
            origin=(72.0, 109.0),
            chars=[
                CharInfo(char="L", bbox=(72.0, 100.0, 80.0, 112.0), origin=(72.0, 109.0)),
                CharInfo(char="1", bbox=(80.0, 100.0, 150.0, 112.0), origin=(80.0, 109.0)),
            ],
        )
        span2 = GlyphSpan(
            span_id="p1_b0_l1_s0",
            text="Line Two",
            bbox=(72.0, 120.0, 150.0, 132.0),
            font_name="DejaVuSans",
            font_size=10.0,
            color="#000000",
            origin=(72.0, 129.0),
            chars=[
                CharInfo(char="L", bbox=(72.0, 120.0, 80.0, 132.0), origin=(72.0, 129.0)),
                CharInfo(char="2", bbox=(80.0, 120.0, 150.0, 132.0), origin=(80.0, 129.0)),
            ],
        )
        block = TextBlock(
            block_id="p1_block_0",
            bbox=(72.0, 100.0, 200.0, 140.0),  # Generous block bbox with inter-line gap
            spans=[span1, span2],
            block_type="text",
        )

        padding = 0.5
        line_rects = compute_tight_line_clearance_regions(block, padding=padding)

        # Must produce exactly two distinct line rects, NOT one combined block rect
        self.assertEqual(len(line_rects), 2)

        # Line 1: should be tight around [72, 100, 150, 112] +/- 0.5
        self.assertAlmostEqual(line_rects[0][0], 71.5, places=2)
        self.assertAlmostEqual(line_rects[0][1], 99.5, places=2)
        self.assertAlmostEqual(line_rects[0][2], 150.5, places=2)
        self.assertAlmostEqual(line_rects[0][3], 112.5, places=2)

        # Line 2: should be tight around [72, 120, 150, 132] +/- 0.5
        self.assertAlmostEqual(line_rects[1][0], 71.5, places=2)
        self.assertAlmostEqual(line_rects[1][1], 119.5, places=2)
        self.assertAlmostEqual(line_rects[1][2], 150.5, places=2)
        self.assertAlmostEqual(line_rects[1][3], 132.5, places=2)

        # Crucial invariant: The inter-line space (y = 113 to 119) is NOT in any clearance rect!
        self.assertFalse(any(r[1] <= 116.0 <= r[3] for r in line_rects))

    def test_background_container_classification(self) -> None:
        """Verify Background Container vs Forbidden Vector Art differentiation."""
        block_bbox = (100.0, 100.0, 250.0, 150.0)

        # Case 1: Drawing encloses the block, drawn before text (seqno 1 < text seqno 5)
        container_rect = (95.0, 95.0, 255.0, 155.0)
        self.assertTrue(
            is_background_container(
                drawing_rect=container_rect,
                block_bbox=block_bbox,
                drawing_seqno=1,
                text_seqno=5,
            )
        )

        # Case 2: Drawing encloses the block, but drawn AFTER text (seqno 10 > text seqno 5) -> Foreground overlay!
        self.assertFalse(
            is_background_container(
                drawing_rect=container_rect,
                block_bbox=block_bbox,
                drawing_seqno=10,
                text_seqno=5,
            )
        )

        # Case 3: Drawing does NOT enclose the block (e.g. a divider line or axis intersecting)
        divider_rect = (50.0, 120.0, 300.0, 122.0)
        self.assertFalse(
            is_background_container(
                drawing_rect=divider_rect,
                block_bbox=block_bbox,
                drawing_seqno=1,
                text_seqno=5,
            )
        )

    def test_collision_fallback_with_formula(self) -> None:
        """Verify candidate text colliding with a formula triggers COLLISION_FALLBACK."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        # Draw formula text and normal text
        page.insert_text((72, 100), "Formula: E = mc^2")
        page.insert_text((72, 108), "Text very close to formula")
        pdf_bytes = doc.tobytes()
        doc.close()

        # IR where block_1 is text and block_0 is formula, placed tightly adjacent (overlapping bounds)
        formula_block = TextBlock(
            block_id="p1_block_formula",
            bbox=(72.0, 95.0, 200.0, 105.0),
            spans=[
                GlyphSpan(
                    span_id="s_f",
                    text="E = mc^2",
                    bbox=(72.0, 95.0, 200.0, 105.0),
                    font_name="DejaVuSans",
                    font_size=10.0,
                    color="#000000",
                )
            ],
            block_type="formula",
        )
        text_block = TextBlock(
            block_id="p1_block_candidate",
            bbox=(72.0, 103.0, 250.0, 120.0),  # Overlaps formula by 2 pt
            spans=[
                GlyphSpan(
                    span_id="s_t",
                    text="Text very close to formula",
                    bbox=(72.0, 103.0, 250.0, 120.0),
                    font_name="DejaVuSans",
                    font_size=10.0,
                    color="#000000",
                )
            ],
            block_type="text",
        )

        page_ir = PageIR(
            page_number=1,
            geometry=PageGeometry(width=595, height=842),
            blocks=[formula_block, text_block],
            regions=[
                LayoutRegion(
                    region_id="reg_formula",
                    bbox=(72.0, 95.0, 200.0, 105.0),
                    category="formula",
                )
            ],
        )
        doc_ir = DocumentIR(
            doc_id="doc_formula_coll",
            filename="formula_coll.pdf",
            page_count=1,
            pages=[page_ir],
        )

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={"p1_block_candidate": "Văn bản rất gần công thức toán học"},
        )

        # Invariant: text_block must trigger COLLISION_FALLBACK and source text must be preserved
        self.assertEqual(result.fitting_report.collision_blocks, 1)
        self.assertEqual(result.fitting_report.replaced_blocks, 0)
        self.assertEqual(result.fitting_report.success_rate, 0.0)

        detail = next(d for d in result.fitting_report.details if d.block_id == "p1_block_candidate")
        self.assertEqual(detail.status, BlockFittingStatus.COLLISION_FALLBACK)
        self.assertIsNotNone(detail.collision_detail)
        self.assertEqual(detail.collision_detail.collision_type, ExclusionZoneType.FORMULA.value)

        # Verify output PDF retains the original text
        verify_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        extracted = verify_doc[0].get_text()
        verify_doc.close()
        self.assertIn("Text very close to formula", extracted)

    def test_collision_fallback_with_image(self) -> None:
        """Verify candidate text intersecting a visually placed image triggers COLLISION_FALLBACK."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        # Insert a real image on page
        img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), 0)
        page.insert_image(pymupdf.Rect(100, 100, 200, 200), pixmap=img)
        page.insert_text((110, 150), "Text inside scanned image area")
        pdf_bytes = doc.tobytes()
        doc.close()

        candidate_block = TextBlock(
            block_id="p1_block_ocr_text",
            bbox=(110.0, 140.0, 190.0, 160.0),  # Intersects image at (100, 100, 200, 200)
            spans=[
                GlyphSpan(
                    span_id="s_ocr",
                    text="Text inside scanned image area",
                    bbox=(110.0, 140.0, 190.0, 160.0),
                    font_name="DejaVuSans",
                    font_size=10.0,
                    color="#000000",
                )
            ],
            block_type="text",
        )
        page_ir = PageIR(
            page_number=1,
            geometry=PageGeometry(width=595, height=842),
            blocks=[candidate_block],
        )
        doc_ir = DocumentIR(
            doc_id="doc_img_coll",
            filename="img_coll.pdf",
            page_count=1,
            pages=[page_ir],
        )

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={"p1_block_ocr_text": "Chữ bên trong ảnh quét"},
        )

        self.assertEqual(result.fitting_report.collision_blocks, 1)
        detail = result.fitting_report.details[0]
        self.assertEqual(detail.status, BlockFittingStatus.COLLISION_FALLBACK)
        self.assertIsNotNone(detail.collision_detail)
        self.assertEqual(detail.collision_detail.collision_type, ExclusionZoneType.IMAGE.value)

    def test_collision_fallback_with_divider_vector_art(self) -> None:
        """Verify candidate text intersecting a forbidden vector dividing line triggers COLLISION_FALLBACK."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        # Draw a horizontal rule / divider line cutting across the page
        page.draw_line(pymupdf.Point(50, 150), pymupdf.Point(500, 150), color=(0.5, 0.5, 0.5), width=1.5)
        page.insert_text((72, 145), "Text overlapping horizontal divider rule")
        pdf_bytes = doc.tobytes()
        doc.close()

        # Text block whose tight bounds intersect y = 150
        candidate_block = TextBlock(
            block_id="p1_block_rule_overlap",
            bbox=(72.0, 140.0, 300.0, 155.0),
            spans=[
                GlyphSpan(
                    span_id="s_rule",
                    text="Text overlapping horizontal divider rule",
                    bbox=(72.0, 140.0, 300.0, 155.0),
                    font_name="DejaVuSans",
                    font_size=10.0,
                    color="#000000",
                )
            ],
            block_type="text",
        )
        page_ir = PageIR(
            page_number=1,
            geometry=PageGeometry(width=595, height=842),
            blocks=[candidate_block],
        )
        doc_ir = DocumentIR(
            doc_id="doc_vec_coll",
            filename="vec_coll.pdf",
            page_count=1,
            pages=[page_ir],
        )

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={"p1_block_rule_overlap": "Chữ đè lên đường kẻ phân cách ngang"},
        )

        self.assertEqual(result.fitting_report.collision_blocks, 1)
        detail = result.fitting_report.details[0]
        self.assertEqual(detail.status, BlockFittingStatus.COLLISION_FALLBACK)
        self.assertIsNotNone(detail.collision_detail)
        self.assertEqual(detail.collision_detail.collision_type, ExclusionZoneType.VECTOR_ART.value)

    def test_background_container_is_preserved_and_approved(self) -> None:
        """Verify background container (callout box) is recognized and approved for typesetting."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        # Draw a tinted background rectangle enclosing text
        page.draw_rect(pymupdf.Rect(50, 100, 400, 200), fill=(0.95, 0.95, 0.98), color=(0.8, 0.8, 0.9), width=1.0)
        page.insert_text((72, 140), "Text comfortably inside container card")
        pdf_bytes = doc.tobytes()
        doc.close()

        candidate_block = TextBlock(
            block_id="p1_block_container",
            bbox=(72.0, 125.0, 350.0, 160.0),  # Completely inside (50, 100, 400, 200)
            spans=[
                GlyphSpan(
                    span_id="s_card",
                    text="Text comfortably inside container card",
                    bbox=(72.0, 125.0, 350.0, 160.0),
                    font_name="DejaVuSans",
                    font_size=11.0,
                    color="#000000",
                )
            ],
            block_type="text",
        )
        page_ir = PageIR(
            page_number=1,
            geometry=PageGeometry(width=595, height=842),
            blocks=[candidate_block],
        )
        doc_ir = DocumentIR(
            doc_id="doc_container",
            filename="container.pdf",
            page_count=1,
            pages=[page_ir],
        )

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={"p1_block_container": "Văn bản nằm an toàn bên trong thẻ chứa"},
        )

        # Should be APPROVED and SUCCESS, NOT a collision
        self.assertEqual(result.fitting_report.collision_blocks, 0)
        self.assertEqual(result.fitting_report.replaced_blocks, 1)
        self.assertEqual(result.fitting_report.success_rate, 100.0)

        # Output PDF should retain vector background card
        verify_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        drawings = verify_doc[0].get_drawings()
        extracted = verify_doc[0].get_text()
        verify_doc.close()
        self.assertGreaterEqual(len(drawings), 1)
        self.assertIn("Văn bản nằm an toàn bên trong thẻ chứa", extracted)

    def test_mutual_candidate_clearance_conflict(self) -> None:
        """Verify mutual clearance collision between multiple candidates rejects both safely."""
        # Two candidate blocks on same page whose clearance bounds intersect each other
        block_a = TextBlock(
            block_id="block_a",
            bbox=(100.0, 100.0, 200.0, 120.0),
            spans=[
                GlyphSpan(
                    span_id="s_a",
                    text="Block A text",
                    bbox=(100.0, 100.0, 200.0, 120.0),
                    font_name="DejaVuSans",
                    font_size=10.0,
                    color="#000000",
                )
            ],
            block_type="text",
        )
        block_b = TextBlock(
            block_id="block_b",
            bbox=(150.0, 110.0, 250.0, 130.0),  # Intersects block A
            spans=[
                GlyphSpan(
                    span_id="s_b",
                    text="Block B text",
                    bbox=(150.0, 110.0, 250.0, 130.0),
                    font_name="DejaVuSans",
                    font_size=10.0,
                    color="#000000",
                )
            ],
            block_type="text",
        )

        page_ir = PageIR(
            page_number=1,
            geometry=PageGeometry(width=595, height=842),
            blocks=[block_a, block_b],
        )

        planner = ClearancePlanner(padding_pt=0.5)
        plan = planner.plan_page_clearance(page_ir=page_ir, page=None, candidate_blocks=[block_a, block_b])

        # Both blocks must be rejected due to mutual collision
        self.assertNotIn("block_a", plan.approved_blocks)
        self.assertNotIn("block_b", plan.approved_blocks)
        self.assertIn("block_a", plan.collision_blocks)
        self.assertIn("block_b", plan.collision_blocks)

    def test_inline_code_pill_background_is_approved_and_cleaned(self) -> None:
        """Verify inline <code> rounded-rect pill backgrounds do not trigger false-positive VECTOR_ART collisions."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        # 1. Leading prose before inline code
        page.insert_text((50, 111), "Chu kỳ xung nhịp", fontsize=11)
        # 2. Inline code rounded-rect background pill (borderless fill, height ~15pt)
        page.draw_rect(
            pymupdf.Rect(145, 99, 195, 114),
            fill=(0.953, 0.945, 0.925),
            color=None,
            width=0.0,
        )
        # 3. Inline code span and trailing prose
        page.insert_text((149, 111), "T = 1/f", fontsize=9.5)
        page.insert_text((200, 111), "là nghịch đảo của tần số.", fontsize=11)
        pdf_bytes = doc.tobytes()
        doc.close()

        candidate_block = TextBlock(
            block_id="p1_block_inline_code",
            bbox=(50.0, 99.0, 340.0, 114.0),
            spans=[
                GlyphSpan(
                    span_id="s_lead",
                    text="Chu kỳ xung nhịp ",
                    bbox=(50.0, 100.0, 144.0, 113.0),
                    font_name="DejaVuSans",
                    font_size=11.0,
                    color="#000000",
                ),
                GlyphSpan(
                    span_id="s_code",
                    text="T = 1/f",
                    bbox=(149.0, 101.0, 191.0, 112.0),
                    font_name="DejaVuSansMono",
                    font_size=9.5,
                    color="#000000",
                ),
                GlyphSpan(
                    span_id="s_trail",
                    text=" là nghịch đảo của tần số.",
                    bbox=(200.0, 100.0, 340.0, 113.0),
                    font_name="DejaVuSans",
                    font_size=11.0,
                    color="#000000",
                ),
            ],
            block_type="text",
        )
        page_ir = PageIR(
            page_number=1,
            geometry=PageGeometry(width=595, height=842),
            blocks=[candidate_block],
        )
        doc_ir = DocumentIR(
            doc_id="doc_inline_pill",
            filename="inline_pill.pdf",
            page_count=1,
            pages=[page_ir],
        )

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={
                "p1_block_inline_code": "Clock cycle T = 1/f is the reciprocal of frequency."
            },
        )

        self.assertEqual(result.fitting_report.collision_blocks, 0)
        self.assertEqual(result.fitting_report.replaced_blocks, 1)


if __name__ == "__main__":
    unittest.main()

