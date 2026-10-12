"""Acceptance tests for Slice 4C.2: Table Cell Isolation & Grid Protection.

Covers:
1. Grid Validation & Vector Primitive Filtering
2. Pipeline Fail-Closed Preservation Contract
3. Pre-Translation Cell Partitioning & Glyph Provenance Invariant
4. Stable Geometry Contract & Stroke-Aware Inset Padding
5. Page-Level Transactional Staging & Rollback
6. Multi-Page Document Accumulator & Document-Level Preservation
7. Telemetry Stratification, Cache Isolation & Visual Integrity
"""

from __future__ import annotations

import unittest
import pymupdf

from layoutlingua.core.ir import PageGeometry, PageIR
from layoutlingua.core.table_models import BorderLine, CellGeometry, TableGrid
from layoutlingua.typesetting.models import (
    BlockFittingDetail,
    BlockFittingStatus,
    FittingReport,
    PageFittingSummary,
    PageTransactionResult,
)


class TestSlice4CTablesSchema(unittest.TestCase):
    """Task 1: Domain models, table geometry, and telemetry schema extensions."""

    def test_table_grid_and_cell_geometry_dataclasses(self) -> None:
        bl = BorderLine(p1=(10.0, 20.0), p2=(60.0, 20.0), width=1.0)
        self.assertEqual(bl.width, 1.0)
        cg = CellGeometry(
            cell_id="p1_t0_r0_c0",
            row_idx=0,
            col_idx=0,
            cell_bbox=(10.0, 20.0, 60.0, 40.0),
            border_widths={"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        self.assertEqual(cg.cell_id, "p1_t0_r0_c0")
        tg = TableGrid(
            table_id="p1_t0",
            bbox=(10.0, 20.0, 110.0, 80.0),
            row_count=2,
            col_count=2,
            cells={cg.cell_id: cg},
        )
        self.assertEqual(tg.table_id, "p1_t0")
        self.assertEqual(len(tg.cells), 1)

    def test_page_ir_metadata_field(self) -> None:
        geom = PageGeometry(width=612.0, height=792.0)
        p = PageIR(page_number=1, geometry=geom)
        self.assertIsInstance(p.metadata, dict)
        p.metadata["tables"] = {}
        self.assertIn("tables", p.metadata)

    def test_block_fitting_status_and_detail_extensions(self) -> None:
        self.assertEqual(BlockFittingStatus.TRANSACTION_FALLBACK.value, "transaction_fallback")
        detail = BlockFittingDetail(
            block_id="p1_t0_r0_c0",
            page_number=1,
            status=BlockFittingStatus.TRANSACTION_FALLBACK,
            original_text="Cell text",
            translated_text="Văn bản",
            original_font_size=10.0,
            final_font_size=10.0,
            unit_kind="CELL",
            table_id="p1_t0",
            row_idx=0,
            col_idx=0,
        )
        self.assertEqual(detail.unit_kind, "CELL")
        self.assertEqual(detail.table_id, "p1_t0")

    def test_page_transaction_result_contract(self) -> None:
        staging_doc = pymupdf.open()
        staging_doc.new_page(width=300, height=300)
        summary = PageFittingSummary(page_number=1)
        res = PageTransactionResult(
            page_number=1,
            source_page_index=0,
            staging_doc=staging_doc,
            is_fallback=False,
            details=[],
            summary=summary,
        )
        self.assertEqual(res.page_number, 1)
        self.assertEqual(res.source_page_index, 0)
        self.assertEqual(res.page_number, res.source_page_index + 1)
        self.assertFalse(res.is_fallback)
        self.assertEqual(len(res.staging_doc), 1)
        staging_doc.close()

    def test_fitting_report_and_page_summary_cell_counters(self) -> None:
        summary = PageFittingSummary(page_number=1)
        self.assertEqual(summary.total_cells, 0)
        self.assertEqual(summary.transaction_fallback_cells, 0)
        self.assertEqual(summary.transaction_fallback_blocks, 0)

        report = FittingReport()
        self.assertEqual(report.total_cells, 0)
        self.assertEqual(report.replaced_cells, 0)
        self.assertEqual(report.overflow_cells, 0)
        self.assertEqual(report.transaction_fallback_cells, 0)
        self.assertEqual(report.transaction_fallback_blocks, 0)
        self.assertEqual(report.total_tables, 0)
        self.assertEqual(report.corroborated_tables, 0)
        self.assertEqual(report.rejected_tables, 0)



class TestTableGridValidator(unittest.TestCase):
    """Task 2: Vector Primitive Filtering & TableGridValidator."""

    def test_table_grid_corroboration_lines_and_rects(self) -> None:
        """2x2 table with borders drawn via 'l' lines and 're' rect edges is validated when edge coverage >= 90%."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(50, 50, 250, 150))
        shape.finish(color=(0, 0, 0), width=1.0)
        shape.draw_line(pymupdf.Point(150, 50), pymupdf.Point(150, 150))
        shape.finish(color=(0, 0, 0), width=1.0)
        shape.draw_line(pymupdf.Point(50, 100), pymupdf.Point(250, 100))
        shape.finish(color=(0, 0, 0), width=1.0)
        shape.commit()

        page.insert_text(pymupdf.Point(60, 80), "Cell 00")
        page.insert_text(pymupdf.Point(160, 80), "Cell 01")
        page.insert_text(pymupdf.Point(60, 130), "Cell 10")
        page.insert_text(pymupdf.Point(160, 130), "Cell 11")

        geom = PageGeometry(width=300, height=300)
        page_ir = PageIR(page_number=1, geometry=geom)
        from layoutlingua.core.tables import TableGridValidator

        validator = TableGridValidator(tolerance_pt=2.0, min_edge_coverage=0.90)
        grids = validator.validate_page_tables(page, page_ir)
        self.assertEqual(len(grids), 1)
        grid = grids[0]
        self.assertEqual(grid.row_count, 2)
        self.assertEqual(grid.col_count, 2)
        self.assertEqual(len(grid.cells), 4)
        doc.close()

    def test_table_grid_corroboration_rejects_weak_evidence(self) -> None:
        """Table missing internal divider or with edge gap > 2.0 pt is rejected -> fail-closed."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(50, 50, 250, 150))  # Outer only, NO internal dividers!
        shape.finish(color=(0, 0, 0), width=1.0)
        shape.commit()
        page.insert_text(pymupdf.Point(60, 80), "Cell 00")
        page.insert_text(pymupdf.Point(160, 80), "Cell 01")

        geom = PageGeometry(width=300, height=300)
        page_ir = PageIR(page_number=1, geometry=geom)
        from layoutlingua.core.tables import TableGridValidator

        validator = TableGridValidator(tolerance_pt=2.0, min_edge_coverage=0.90)
        grids = validator.validate_page_tables(page, page_ir)
        self.assertEqual(len(grids), 0)
        doc.close()

    def test_vector_evidence_rejects_fill_only_rectangles(self) -> None:
        """Drawing with type='f' and no stroke is rejected as a grid line candidate."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(50, 50, 250, 150))
        shape.finish(fill=(0.9, 0.9, 0.9), color=None)  # Pure fill, NO stroke!
        shape.commit()
        page.insert_text(pymupdf.Point(60, 80), "Cell 00")

        geom = PageGeometry(width=300, height=300)
        page_ir = PageIR(page_number=1, geometry=geom)
        from layoutlingua.core.tables import TableGridValidator

        validator = TableGridValidator()
        grids = validator.validate_page_tables(page, page_ir)
        self.assertEqual(len(grids), 0)
        doc.close()

    def test_vector_evidence_rejects_curve_bounding_boxes(self) -> None:
        """Primitive item 'c' (bezier curve) is strictly ignored; its bbox is not used as a straight grid line."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        shape = page.new_shape()
        shape.draw_bezier(
            pymupdf.Point(50, 50),
            pymupdf.Point(100, 100),
            pymupdf.Point(200, 0),
            pymupdf.Point(250, 150),
        )
        shape.finish(color=(0, 0, 0), width=1.0)
        shape.commit()

        geom = PageGeometry(width=300, height=300)
        page_ir = PageIR(page_number=1, geometry=geom)
        from layoutlingua.core.tables import TableGridValidator

        validator = TableGridValidator()
        grids = validator.validate_page_tables(page, page_ir)
        self.assertEqual(len(grids), 0)
        doc.close()

    def test_vector_evidence_mixed_path_line_and_curve(self) -> None:
        """Path with mixed 'l' and 'c' items admits only 'l' segments and filters out 'c'."""
        raw_items = [
            ("l", pymupdf.Point(50, 50), pymupdf.Point(250, 50)),
            (
                "c",
                pymupdf.Point(250, 50),
                pymupdf.Point(260, 60),
                pymupdf.Point(260, 70),
                pymupdf.Point(250, 80),
            ),
            ("l", pymupdf.Point(250, 80), pymupdf.Point(50, 80)),
        ]
        drawing = {"type": "s", "color": (0, 0, 0), "width": 1.0, "items": raw_items}
        from layoutlingua.core.tables import extract_valid_vector_segments

        segments = extract_valid_vector_segments([drawing])
        self.assertEqual(len(segments), 2)

    def test_table_dimension_varieties_1x2_and_2x1(self) -> None:
        """1x2 and 2x1 tables with clear vector borders are recognized and validated."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(50, 50, 250, 100))
        shape.draw_line(pymupdf.Point(150, 50), pymupdf.Point(150, 100))
        shape.finish(color=(0, 0, 0), width=1.0)
        shape.commit()
        page.insert_text(pymupdf.Point(60, 75), "Col 0")
        page.insert_text(pymupdf.Point(160, 75), "Col 1")

        geom = PageGeometry(width=300, height=300)
        page_ir = PageIR(page_number=1, geometry=geom)
        from layoutlingua.core.tables import TableGridValidator

        validator = TableGridValidator()
        grids = validator.validate_page_tables(page, page_ir)
        self.assertEqual(len(grids), 1)
        self.assertEqual(grids[0].row_count, 1)
        self.assertEqual(grids[0].col_count, 2)
        doc.close()


if __name__ == "__main__":
    unittest.main()

