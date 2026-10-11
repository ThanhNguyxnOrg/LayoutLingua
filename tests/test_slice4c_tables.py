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


if __name__ == "__main__":
    unittest.main()
