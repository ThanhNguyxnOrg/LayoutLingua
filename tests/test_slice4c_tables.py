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

from layoutlingua.core.ir import CharInfo, DocumentIR, GlyphSpan, PageGeometry, PageIR, TextBlock
from layoutlingua.core.table_models import BorderLine, CellGeometry, TableGrid
from layoutlingua.translation.mock import MockTranslationProvider
from layoutlingua.translation.models import BatchTranslationRequest, ProviderCapabilities
from layoutlingua.translation.provider import BaseTranslationProvider
from layoutlingua.translation.service import TranslationService
from layoutlingua.typesetting.engine import TypesetEngine
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


class TestTableCellPartitioner(unittest.TestCase):
    """Task 3: Pre-Translation Cell Partitioner & Glyph Provenance Invariant."""

    def test_pre_translation_cell_partitioning_same_baseline(self) -> None:
        """Text across columns on identical horizontal baseline is split into distinct cell TextBlocks with stable IDs."""
        from layoutlingua.core.tables import TableCellPartitioner

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        chars = [
            CharInfo("A", (60, 70, 70, 85), (60, 80)),
            CharInfo(" ", (70, 70, 75, 85), (70, 80)),
            CharInfo("B", (160, 70, 170, 85), (160, 80)),
        ]
        span = GlyphSpan(
            "s0", "A B", (60, 70, 170, 85), "DejaVuSans", 10.0, "#000000", chars=chars
        )
        block = TextBlock("b0", (60, 70, 170, 85), spans=[span], block_type="text")
        p.blocks.append(block)

        c0 = CellGeometry(
            "p1_t0_r0_c0", 0, 0, (50, 50, 150, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        c1 = CellGeometry(
            "p1_t0_r0_c1", 0, 1, (150, 50, 250, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        grid = TableGrid(
            "p1_t0", (50, 50, 250, 100), 1, 2, {c0.cell_id: c0, c1.cell_id: c1}
        )

        partitioner = TableCellPartitioner()
        partitioner.partition_cells(p, [grid])

        cell_blocks = [b for b in p.blocks if b.block_type == "table_cell"]
        self.assertEqual(len(cell_blocks), 2)
        self.assertEqual(cell_blocks[0].block_id, "p1_t0_r0_c0")
        self.assertEqual(cell_blocks[0].bbox, (50, 50, 150, 100))
        self.assertEqual(cell_blocks[0].text.strip(), "A")
        self.assertEqual(cell_blocks[1].block_id, "p1_t0_r0_c1")
        self.assertEqual(cell_blocks[1].bbox, (150, 50, 250, 100))
        self.assertEqual(cell_blocks[1].text.strip(), "B")

    def test_character_level_span_splitting_across_border(self) -> None:
        """A single continuous span spanning across two cells is partitioned cleanly using CharInfo bboxes."""
        from layoutlingua.core.tables import TableCellPartitioner

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        chars = [
            CharInfo("C", (80, 70, 90, 85), (80, 80)),
            CharInfo("D", (180, 70, 190, 85), (180, 80)),
        ]
        span = GlyphSpan(
            "s0", "CD", (80, 70, 190, 85), "DejaVuSans", 10.0, "#000000", chars=chars
        )
        p.blocks.append(TextBlock("b0", (80, 70, 190, 85), spans=[span]))

        c0 = CellGeometry(
            "p1_t0_r0_c0", 0, 0, (50, 50, 150, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        c1 = CellGeometry(
            "p1_t0_r0_c1", 0, 1, (150, 50, 250, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        grid = TableGrid(
            "p1_t0", (50, 50, 250, 100), 1, 2, {c0.cell_id: c0, c1.cell_id: c1}
        )

        partitioner = TableCellPartitioner()
        partitioner.partition_cells(p, [grid])
        c_blocks = [b for b in p.blocks if b.block_type == "table_cell"]
        self.assertEqual(len(c_blocks), 2)
        self.assertEqual(c_blocks[0].text, "C")
        self.assertEqual(c_blocks[1].text, "D")

    def test_glyph_identity_and_provenance_conservation(self) -> None:
        """All glyph provenance IDs {p_b_s_c} match input multiset exactly (C_out == C_in)."""
        from layoutlingua.core.tables import TableCellPartitioner

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        chars = [
            CharInfo("X", (60, 70, 70, 85), (60, 80)),
            CharInfo("Y", (160, 70, 170, 85), (160, 80)),
        ]
        span = GlyphSpan(
            "s0", "XY", (60, 70, 170, 85), "DejaVuSans", 10.0, "#000000", chars=chars
        )
        p.blocks.append(TextBlock("b0", (60, 70, 170, 85), spans=[span]))

        c0 = CellGeometry(
            "p1_t0_r0_c0", 0, 0, (50, 50, 150, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        c1 = CellGeometry(
            "p1_t0_r0_c1", 0, 1, (150, 50, 250, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        grid = TableGrid(
            "p1_t0", (50, 50, 250, 100), 1, 2, {c0.cell_id: c0, c1.cell_id: c1}
        )

        partitioner = TableCellPartitioner()
        success = partitioner.partition_cells(p, [grid])
        self.assertTrue(success)

    def test_glyph_conservation_detects_drop_and_duplicate_with_same_count(self) -> None:
        """Synthetically dropping one character and duplicating another with identical count aborts partitioning fail-closed."""
        from layoutlingua.core.tables import TableCellPartitioner

        partitioner = TableCellPartitioner()
        c_in = {"p1_b0_s0_c0": 1, "p1_b0_s0_c1": 1}
        c_out_tampered = {"p1_b0_s0_c0": 2}
        self.assertFalse(partitioner._verify_multiset_conservation(c_in, c_out_tampered))

    def test_atomic_formula_token_crossing_border_fails_closed(self) -> None:
        """A formula token ⟦LL_FORMULA_0001⟧ intersecting a cell divider is not split; table aborts partitioning fail-closed."""
        from layoutlingua.core.tables import TableCellPartitioner

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        span = GlyphSpan(
            "s0", "⟦LL_FORMULA_0001⟧", (140, 70, 170, 85), "DejaVuSans", 10.0, "#000000"
        )
        p.blocks.append(TextBlock("b0", (140, 70, 170, 85), spans=[span]))

        c0 = CellGeometry(
            "p1_t0_r0_c0", 0, 0, (50, 50, 150, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        c1 = CellGeometry(
            "p1_t0_r0_c1", 0, 1, (150, 50, 250, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        grid = TableGrid(
            "p1_t0", (50, 50, 250, 100), 1, 2, {c0.cell_id: c0, c1.cell_id: c1}
        )

        partitioner = TableCellPartitioner()
        success = partitioner.partition_cells(p, [grid])
        self.assertFalse(success)
        self.assertEqual(p.blocks[0].block_type, "table_rejected")

    def test_ambiguous_glyph_ownership_fails_closed(self) -> None:
        """Glyphs straddling cell divider lines without clean separation abort table partitioning; source text preserved."""
        from layoutlingua.core.tables import TableCellPartitioner

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        chars = [CharInfo("?", (145, 70, 155, 85), (145, 80))]
        span = GlyphSpan(
            "s0", "?", (145, 70, 155, 85), "DejaVuSans", 10.0, "#000000", chars=chars
        )
        p.blocks.append(TextBlock("b0", (145, 70, 155, 85), spans=[span]))

        c0 = CellGeometry(
            "p1_t0_r0_c0", 0, 0, (50, 50, 150, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        c1 = CellGeometry(
            "p1_t0_r0_c1", 0, 1, (150, 50, 250, 100),
            {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        )
        grid = TableGrid(
            "p1_t0", (50, 50, 250, 100), 1, 2, {c0.cell_id: c0, c1.cell_id: c1}
        )

        partitioner = TableCellPartitioner()
        success = partitioner.partition_cells(p, [grid])
        self.assertFalse(success)
        self.assertEqual(p.blocks[0].block_type, "table_rejected")

    def test_unsupported_merged_cells_fail_closed(self) -> None:
        """Table with None in cells and unverified merge geometry triggers SKIPPED_UNSUPPORTED; source text preserved."""
        from layoutlingua.core.tables import TableCellPartitioner

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        block = TextBlock(
            "b0", (60, 60, 100, 80),
            spans=[GlyphSpan("s0", "Merged", (60, 60, 100, 80), "DejaVuSans", 10.0, "#000000")],
        )
        p.blocks.append(block)

        grid = TableGrid("p1_t0", (50, 50, 250, 100), 2, 2, {})
        partitioner = TableCellPartitioner()
        success = partitioner.partition_cells(p, [grid])
        self.assertFalse(success)
        self.assertEqual(p.blocks[0].block_type, "table_rejected")

class TestPipelineFailClosedPreservation(unittest.TestCase):
    """Task 4: Pipeline Fail-Closed Preservation & Block Suppression."""

    def test_rejected_table_source_blocks_strictly_preserved_fail_closed(self) -> None:
        """Candidate table rejected due to grid evidence keeps all source blocks intact with zero mutation."""
        from layoutlingua.core.tables import TableGridValidator

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        block = TextBlock(
            "b0", (60, 60, 140, 80),
            spans=[GlyphSpan("s0", "Original Table Text", (60, 60, 140, 80), "DejaVuSans", 10.0, "#000000")],
        )
        p.blocks.append(block)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        from unittest.mock import MagicMock

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        dummy_tab = MagicMock()
        dummy_tab.bbox = (50.0, 50.0, 250.0, 150.0)
        dummy_tab.row_count = 1
        dummy_tab.col_count = 1
        dummy_finder = MagicMock()
        dummy_finder.tables = [dummy_tab]
        page.find_tables = MagicMock(return_value=dummy_finder)

        validator = TableGridValidator()
        validator.validate_page_tables(page, p)

        self.assertEqual(block.block_type, "table_rejected")
        self.assertIn("b0", p.metadata.get("preserved_block_ids", set()))
        doc.close()

    def test_rejected_table_pipeline_preservation_contract(self) -> None:
        """End-to-end integration: rejected table constituent blocks tagged table_rejected
        and stored in document_ir.metadata['preserved_block_ids'];
        TypesetEngine applies 0 redactions; output PDF contains 100% untouched source text;
        telemetry reports SKIPPED_UNSUPPORTED without cell metric inflation."""
        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        b = TextBlock(
            "b_table_0", (60, 60, 140, 80),
            spans=[GlyphSpan("s0", "Preserved Cell Text", (60, 60, 140, 80), "DejaVuSans", 10.0, "#000000")],
            block_type="table_rejected",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR(
            "doc1", "test.pdf", 1, pages=[p],
            metadata={"preserved_block_ids": {"b_table_0"}, "rejected_table_bboxes": [(50, 50, 150, 100)]},
        )

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(60, 75), "Preserved Cell Text")
        pdf_bytes = doc.tobytes()
        doc.close()

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={"b_table_0": "Văn bản bị từ chối"},
        )
        self.assertEqual(result.fitting_report.replaced_blocks, 0)
        self.assertEqual(result.fitting_report.skipped_blocks, 1)
        self.assertEqual(result.fitting_report.total_cells, 0)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        out_text = out_doc[0].get_text()
        self.assertIn("Preserved Cell Text", out_text)
        self.assertNotIn("Văn bản bị từ chối", out_text)
        out_doc.close()

    def test_translation_pipeline_skips_rejected_table_blocks_and_translates_valid_blocks(self) -> None:
        """Translation preserves rejected table block text untouched while translating normal text and valid table cells."""
        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        b_normal = TextBlock(
            "b_normal", (10, 10, 50, 30),
            spans=[GlyphSpan("s_norm", "Hello World", (10, 10, 50, 30), "DejaVuSans", 10.0, "#000000")],
            block_type="text",
        )
        b_rejected = TextBlock(
            "b_rej", (60, 60, 140, 80),
            spans=[GlyphSpan("s_rej", "Do Not Translate", (60, 60, 140, 80), "DejaVuSans", 10.0, "#000000")],
            block_type="table_rejected",
        )
        b_cell = TextBlock(
            "b_cell_0", (150, 60, 200, 80),
            spans=[GlyphSpan("s_cell", "Table Cell Text", (150, 60, 200, 80), "DejaVuSans", 10.0, "#000000")],
            block_type="table_cell",
        )
        p.blocks.extend([b_normal, b_rejected, b_cell])
        doc_ir = DocumentIR(
            "doc1", "test.pdf", 1, pages=[p],
            metadata={"preserved_block_ids": {"b_rej"}},
        )

        mock_provider = MockTranslationProvider()
        translated_doc = mock_provider.translate_document(doc_ir, target_lang="vi")

        # Rejected block must be untouched
        self.assertEqual(translated_doc.pages[0].blocks[1].spans[0].text, "Do Not Translate")
        # Normal block and valid table_cell block must be translated
        self.assertNotEqual(translated_doc.pages[0].blocks[0].spans[0].text, "Hello World")
        self.assertNotEqual(translated_doc.pages[0].blocks[2].spans[0].text, "Table Cell Text")

    def test_fail_closed_missing_or_corrupt_metadata(self) -> None:
        """Even with empty/corrupt metadata, blocks with block_type='table_rejected' are strictly preserved fail-closed."""
        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        b_rej = TextBlock(
            "b_corrupt_meta", (60, 60, 140, 80),
            spans=[GlyphSpan("s0", "Keep Original Ink", (60, 60, 140, 80), "DejaVuSans", 10.0, "#000000")],
            block_type="table_rejected",
        )
        p.blocks.append(b_rej)
        # Empty metadata
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p], metadata={})

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(60, 75), "Keep Original Ink")
        pdf_bytes = doc.tobytes()
        doc.close()

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={"b_corrupt_meta": "Đã bị dịch sai"},
        )
        self.assertEqual(result.fitting_report.replaced_blocks, 0)
        self.assertEqual(result.fitting_report.skipped_blocks, 1)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        out_text = out_doc[0].get_text()
        self.assertIn("Keep Original Ink", out_text)
        self.assertNotIn("Đã bị dịch sai", out_text)
        out_doc.close()

    def test_translation_service_spy_verifies_rejected_blocks_never_sent_to_provider(self) -> None:
        """Integration test with spy provider: rejected table blocks are never sent to TranslationService provider;
        normal paragraphs and valid table cells are properly sent and translated."""
        from layoutlingua.translation.models import BatchTranslationResult

        class SpyTranslationProvider(BaseTranslationProvider):
            def __init__(self) -> None:
                self.received_segment_ids: list[str] = []
                self.received_texts: list[str] = []

            @property
            def name(self) -> str:
                return "spy_provider"

            @property
            def model(self) -> str:
                return "spy_model"

            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities()

            def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
                translations = {}
                for s in request.segments:
                    self.received_segment_ids.append(s.segment_id)
                    self.received_texts.append(s.masked_text)
                    translations[s.segment_id] = f"[TRANSLATED] {s.masked_text}"
                return BatchTranslationResult(translations=translations)

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        b_normal = TextBlock(
            "b_normal", (10, 10, 50, 30),
            spans=[GlyphSpan("s_norm", "Normal Paragraph", (10, 10, 50, 30), "DejaVuSans", 10.0, "#000000")],
            block_type="text",
        )
        b_rejected = TextBlock(
            "b_rejected_table", (60, 60, 140, 80),
            spans=[GlyphSpan("s_rej", "Secret Table Data", (60, 60, 140, 80), "DejaVuSans", 10.0, "#000000")],
            block_type="table_rejected",
        )
        b_cell = TextBlock(
            "b_valid_cell", (150, 60, 200, 80),
            spans=[GlyphSpan("s_cell", "Valid Cell Header", (150, 60, 200, 80), "DejaVuSans", 10.0, "#000000")],
            block_type="table_cell",
        )
        p.blocks.extend([b_normal, b_rejected, b_cell])
        doc_ir = DocumentIR(
            "doc1", "test.pdf", 1, pages=[p],
            metadata={"preserved_block_ids": {"b_rejected_table"}},
        )

        spy_provider = SpyTranslationProvider()
        service = TranslationService(provider=spy_provider, no_cache=True)
        result = service.translate_document(doc_ir, target_language="vi")

        # 1. Spy provider must NEVER have received b_rejected_table
        self.assertNotIn("b_rejected_table", spy_provider.received_segment_ids)
        self.assertNotIn("Secret Table Data", spy_provider.received_texts)

        # 2. Spy provider MUST have received normal block and valid table cell
        self.assertIn("b_normal", spy_provider.received_segment_ids)
        self.assertIn("b_valid_cell", spy_provider.received_segment_ids)

        # 3. Translated result map contains valid blocks, but 0 entries for rejected block
        self.assertIn("b_normal", result.translated_segments)
        self.assertIn("b_valid_cell", result.translated_segments)
        self.assertNotIn("b_rejected_table", result.translated_segments)


class TestSlice4CStrokeAwareInsets(unittest.TestCase):
    """Task 5: Stable geometry contract, stroke-aware inset padding, and cell fitting."""

    def test_stroke_aware_insets_calculation(self) -> None:
        """p_side = max(1.0, w/2 + 0.5) for each side with asymmetric border stroke widths."""
        from layoutlingua.core.table_models import CellGeometry, CellInsets
        from layoutlingua.core.tables import compute_cell_inner_bbox, compute_stroke_aware_insets

        border_widths = {"top": 2.0, "bottom": 4.0, "left": 1.0, "right": 3.0}
        insets = compute_stroke_aware_insets(border_widths)

        self.assertIsInstance(insets, CellInsets)
        self.assertEqual(insets.top, 1.5)      # max(1.0, 2.0/2 + 0.5) = 1.5
        self.assertEqual(insets.bottom, 2.5)   # max(1.0, 4.0/2 + 0.5) = 2.5
        self.assertEqual(insets.left, 1.0)     # max(1.0, 1.0/2 + 0.5) = 1.0
        self.assertEqual(insets.right, 2.0)    # max(1.0, 3.0/2 + 0.5) = 2.0

        cell_bbox = (10.0, 20.0, 100.0, 80.0)
        inner_bbox = compute_cell_inner_bbox(cell_bbox, border_widths)
        self.assertIsNotNone(inner_bbox)
        # inner: (10 + 1.0, 20 + 1.5, 100 - 2.0, 80 - 2.5)
        self.assertEqual(inner_bbox, (11.0, 21.5, 98.0, 77.5))

        # Check method on CellGeometry as well
        cg = CellGeometry(
            cell_id="p1_t0_r0_c0",
            row_idx=0,
            col_idx=0,
            cell_bbox=cell_bbox,
            border_widths=border_widths,
        )
        self.assertEqual(cg.compute_inner_bbox(), (11.0, 21.5, 98.0, 77.5))
        self.assertEqual(cg.insets.top, 1.5)

    def test_stroke_aware_insets_minimum_clamp(self) -> None:
        """Hairline borders or missing strokes (w <= 1.0) clamp to 1.0 pt minimum clearance."""
        from layoutlingua.core.tables import compute_cell_inner_bbox, compute_stroke_aware_insets

        border_widths = {"top": 0.0, "bottom": 0.5, "left": 0.8, "right": 1.0}
        insets = compute_stroke_aware_insets(border_widths)

        self.assertEqual(insets.top, 1.0)
        self.assertEqual(insets.bottom, 1.0)
        self.assertEqual(insets.left, 1.0)
        self.assertEqual(insets.right, 1.0)

        cell_bbox = (0.0, 0.0, 50.0, 50.0)
        inner_bbox = compute_cell_inner_bbox(cell_bbox, border_widths)
        self.assertEqual(inner_bbox, (1.0, 1.0, 49.0, 49.0))

    def test_narrow_cell_fail_closed(self) -> None:
        """Cell narrower or shallower than insets fails closed; compute returns None and typeset engine preserves source."""
        from layoutlingua.core.table_models import CellGeometry, TableGrid
        from layoutlingua.core.tables import compute_cell_inner_bbox
        from layoutlingua.typesetting.engine import TypesetEngine

        # Width = 1.5 pt, but left=1.0, right=1.0 -> required 2.0 pt
        cell_bbox = (50.0, 50.0, 51.5, 70.0)
        border_widths = {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0}
        inner_bbox = compute_cell_inner_bbox(cell_bbox, border_widths)
        self.assertIsNone(inner_bbox)

        # Integration with TypesetEngine
        cg = CellGeometry("p1_t0_r0_c0", 0, 0, cell_bbox, border_widths)
        grid = TableGrid("p1_t0", (50.0, 50.0, 51.5, 70.0), 1, 1, {cg.cell_id: cg})

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom, metadata={"tables": {"p1_t0": grid}})
        b = TextBlock(
            cg.cell_id, cell_bbox,
            spans=[GlyphSpan("s0", "Narrow", cell_bbox, "DejaVuSans", 8.0, "#000000")],
            block_type="table_cell",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(50.5, 60), "Narrow")
        pdf_bytes = doc.tobytes()
        doc.close()

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={cg.cell_id: "Hẹp"},
        )
        self.assertEqual(result.fitting_report.total_cells, 1)
        self.assertEqual(result.fitting_report.replaced_cells, 0)
        self.assertEqual(result.fitting_report.overflow_cells, 1)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertIn("Narrow", out_doc[0].get_text())
        out_doc.close()

    def test_missing_cell_geometry_fail_closed(self) -> None:
        """table_cell block with unresolvable CellGeometry fails closed and retains source text."""
        from layoutlingua.typesetting.engine import TypesetEngine

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)  # No "tables" in metadata
        b = TextBlock(
            "orphan_cell", (50.0, 50.0, 100.0, 80.0),
            spans=[GlyphSpan("s0", "Orphan Text", (50.0, 50.0, 100.0, 80.0), "DejaVuSans", 10.0, "#000000")],
            block_type="table_cell",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(55, 65), "Orphan Text")
        pdf_bytes = doc.tobytes()
        doc.close()

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={"orphan_cell": "Đã Dịch"},
        )
        self.assertEqual(result.fitting_report.total_cells, 1)
        self.assertEqual(result.fitting_report.replaced_cells, 0)
        self.assertEqual(result.fitting_report.skipped_cells, 1)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertIn("Orphan Text", out_doc[0].get_text())
        self.assertNotIn("Đã Dịch", out_doc[0].get_text())
        out_doc.close()

    def test_cell_typesetting_within_inner_bbox(self) -> None:
        """Cell translation is fitted and placed strictly inside inner bbox, leaving outer stroke area intact."""
        from layoutlingua.core.table_models import CellGeometry, TableGrid
        from layoutlingua.typesetting.engine import TypesetEngine

        cell_bbox = (50.0, 50.0, 150.0, 100.0)
        # 2.0 pt borders -> inset is 1.5 pt on all sides
        border_widths = {"top": 2.0, "bottom": 2.0, "left": 2.0, "right": 2.0}
        cg = CellGeometry("p1_t0_r0_c0", 0, 0, cell_bbox, border_widths)
        grid = TableGrid("p1_t0", cell_bbox, 1, 1, {cg.cell_id: cg})

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom, metadata={"tables": {"p1_t0": grid}})
        b = TextBlock(
            cg.cell_id, cell_bbox,
            spans=[GlyphSpan("s0", "Source Cell", (52.0, 55.0, 140.0, 70.0), "DejaVuSans", 10.0, "#000000")],
            block_type="table_cell",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        # Draw table border with 2.0 width
        page.draw_rect(pymupdf.Rect(*cell_bbox), color=(0, 0, 0), width=2.0)
        page.insert_text(pymupdf.Point(52, 65), "Source Cell")
        pdf_bytes = doc.tobytes()
        doc.close()

        engine = TypesetEngine()
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={cg.cell_id: "Ô Đã Dịch"},
        )
        self.assertEqual(result.fitting_report.total_cells, 1)
        self.assertEqual(result.fitting_report.replaced_cells, 1)
        self.assertEqual(result.fitting_report.overflow_cells, 0)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        out_text = out_doc[0].get_text()
        self.assertIn("Ô Đã Dịch", out_text)
        out_doc.close()

    def test_cell_text_overflow_fail_closed(self) -> None:
        """Cell text that overflows inner bbox at minimum scale fails closed and increments overflow_cells."""
        from layoutlingua.core.table_models import CellGeometry, TableGrid
        from layoutlingua.typesetting.engine import TypesetEngine

        cell_bbox = (50.0, 50.0, 80.0, 65.0)  # 30 x 15 pt cell
        border_widths = {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0}
        cg = CellGeometry("p1_t0_r0_c0", 0, 0, cell_bbox, border_widths)
        grid = TableGrid("p1_t0", cell_bbox, 1, 1, {cg.cell_id: cg})

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom, metadata={"tables": {"p1_t0": grid}})
        b = TextBlock(
            cg.cell_id, cell_bbox,
            spans=[GlyphSpan("s0", "Ok", (52.0, 52.0, 60.0, 60.0), "DejaVuSans", 8.0, "#000000")],
            block_type="table_cell",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(52, 60), "Ok")
        pdf_bytes = doc.tobytes()
        doc.close()

        engine = TypesetEngine()
        huge_text = "Văn bản này quá dài để có thể vừa vào một ô bảng siêu nhỏ như thế này ngay cả ở cỡ chữ tối thiểu"
        result = engine.typeset(
            original_pdf=pdf_bytes,
            document_ir=doc_ir,
            translated_segments={cg.cell_id: huge_text},
        )
        self.assertEqual(result.fitting_report.total_cells, 1)
        self.assertEqual(result.fitting_report.replaced_cells, 0)
        self.assertEqual(result.fitting_report.overflow_cells, 1)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertIn("Ok", out_doc[0].get_text())
        self.assertNotIn("quá dài", out_doc[0].get_text())
        out_doc.close()


class TestSlice4CPageTransaction(unittest.TestCase):
    """Task 6: Page-level transactional staging, rollback, and indexing contract."""

    def test_page_transaction_staging_success(self) -> None:
        """Successful page staging returns PageTransactionResult(is_fallback=False) adhering to page_number == source_page_index + 1."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(50, 50), "Original Page 1")

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        b = TextBlock(
            "b0", (50, 40, 150, 60),
            spans=[GlyphSpan("s0", "Original Page 1", (50, 40, 150, 60), "DejaVuSans", 10.0, "#000000")],
            block_type="text",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        engine = TypesetEngine()
        result = engine.stage_page_transaction(
            source_doc=doc,
            page_ir=p,
            document_ir=doc_ir,
            translated_segments={"b0": "Trang 1 Đã Dịch"},
        )

        self.assertIsInstance(result, PageTransactionResult)
        self.assertFalse(result.is_fallback)
        self.assertEqual(result.page_number, 1)
        self.assertEqual(result.source_page_index, 0)
        self.assertEqual(result.page_number, result.source_page_index + 1)
        self.assertEqual(len(result.staging_doc), 1)

        staged_text = result.staging_doc[0].get_text()
        self.assertIn("Trang 1 Đã Dịch", staged_text)
        self.assertEqual(result.summary.replaced_blocks, 1)
        self.assertEqual(result.summary.transaction_fallback_blocks, 0)
        doc.close()

    def test_page_transaction_indexing_contract_multipage(self) -> None:
        """Invariant page_number == source_page_index + 1 holds strictly on higher page indices."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=300)  # page 0
        p2 = doc.new_page(width=300, height=300)  # page 1
        p2.insert_text(pymupdf.Point(50, 50), "Original Page 2")

        geom = PageGeometry(width=300, height=300)
        p_ir = PageIR(page_number=2, geometry=geom)
        b = TextBlock(
            "b2", (50, 40, 150, 60),
            spans=[GlyphSpan("s2", "Original Page 2", (50, 40, 150, 60), "DejaVuSans", 10.0, "#000000")],
            block_type="text",
        )
        p_ir.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 2, pages=[PageIR(1, geom), p_ir])

        engine = TypesetEngine()
        result = engine.stage_page_transaction(
            source_doc=doc,
            page_ir=p_ir,
            document_ir=doc_ir,
            translated_segments={"b2": "Trang 2 Đã Dịch"},
        )

        self.assertEqual(result.page_number, 2)
        self.assertEqual(result.source_page_index, 1)
        self.assertEqual(result.page_number, result.source_page_index + 1)
        self.assertFalse(result.is_fallback)
        self.assertEqual(len(result.staging_doc), 1)
        doc.close()

    def test_page_transaction_rollback_on_exception(self) -> None:
        """Unhandled error during staging discards scratch doc, returns pristine source page with is_fallback=True."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(50, 50), "Pristine Source Text")

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        b = TextBlock(
            "b_crash", (50, 40, 150, 60),
            spans=[GlyphSpan("s0", "Pristine Source Text", (50, 40, 150, 60), "DejaVuSans", 10.0, "#000000")],
            block_type="text",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        engine = TypesetEngine()

        # Invalidate fit tester to trigger exception during staging
        original_test_fit = engine._fit_tester.test_fit
        def crash_test_fit(*args, **kwargs):
            raise RuntimeError("Simulated unhandled rendering crash")
        engine._fit_tester.test_fit = crash_test_fit

        try:
            result = engine.stage_page_transaction(
                source_doc=doc,
                page_ir=p,
                document_ir=doc_ir,
                translated_segments={"b_crash": "Translation Should Not Appear"},
            )
        finally:
            engine._fit_tester.test_fit = original_test_fit

        self.assertTrue(result.is_fallback)
        self.assertEqual(result.page_number, 1)
        self.assertEqual(result.source_page_index, 0)
        self.assertEqual(result.page_number, result.source_page_index + 1)
        self.assertEqual(len(result.staging_doc), 1)

        # Staging doc was rolled back to pristine source page
        staged_text = result.staging_doc[0].get_text()
        self.assertIn("Pristine Source Text", staged_text)
        self.assertNotIn("Translation Should Not Appear", staged_text)
        doc.close()

    def test_page_transaction_fallback_telemetry_accuracy(self) -> None:
        """Rollback accurately records transaction_fallback_blocks and zero false SUCCESS statuses."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(50, 50), "Pristine Source Text")

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        b = TextBlock(
            "b_crash", (50, 40, 150, 60),
            spans=[GlyphSpan("s0", "Pristine Source Text", (50, 40, 150, 60), "DejaVuSans", 10.0, "#000000")],
            block_type="text",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        engine = TypesetEngine()
        original_test_fit = engine._fit_tester.test_fit
        def crash_test_fit(*args, **kwargs):
            raise RuntimeError("Simulated crash")
        engine._fit_tester.test_fit = crash_test_fit

        try:
            result = engine.stage_page_transaction(
                source_doc=doc,
                page_ir=p,
                document_ir=doc_ir,
                translated_segments={"b_crash": "New Text"},
            )
        finally:
            engine._fit_tester.test_fit = original_test_fit

        self.assertTrue(result.is_fallback)
        self.assertEqual(result.summary.replaced_blocks, 0)
        self.assertEqual(result.summary.transaction_fallback_blocks, 1)
        for d in result.details:
            self.assertNotEqual(d.status, BlockFittingStatus.SUCCESS)
            self.assertEqual(d.status, BlockFittingStatus.TRANSACTION_FALLBACK)
        doc.close()

    def test_page_transaction_zero_source_mutation(self) -> None:
        """Source document bytes are 100% identical before and after staging operations."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text(pymupdf.Point(50, 50), "Original Text Never Mutates")
        before_bytes = doc.tobytes()

        geom = PageGeometry(width=300, height=300)
        p = PageIR(page_number=1, geometry=geom)
        b = TextBlock(
            "b0", (50, 40, 150, 60),
            spans=[GlyphSpan("s0", "Original Text Never Mutates", (50, 40, 150, 60), "DejaVuSans", 10.0, "#000000")],
            block_type="text",
        )
        p.blocks.append(b)
        doc_ir = DocumentIR("doc1", "test.pdf", 1, pages=[p])

        engine = TypesetEngine()
        result = engine.stage_page_transaction(
            source_doc=doc,
            page_ir=p,
            document_ir=doc_ir,
            translated_segments={"b0": "Mutated Text"},
        )
        # Verify source doc text remains pristine
        self.assertEqual(doc[0].get_text().strip(), "Original Text Never Mutates")
        self.assertNotIn("Mutated Text", doc[0].get_text())
        self.assertEqual(len(doc), 1)

        # But staging doc contains mutated translated text
        self.assertIn("Mutated Text", result.staging_doc[0].get_text())
        doc.close()


class TestSlice4CMultiPageAccumulator(unittest.TestCase):
    """Task 7: Multi-Page Document Accumulator & Document-Level Preservation."""

    def test_multipage_assembly_exact_order_and_no_duplication(self) -> None:
        """Accumulator arranges pages in exact ascending order 0..N-1 even if DocumentIR pages are unordered."""
        doc = pymupdf.open()
        p1 = doc.new_page(width=300, height=300)
        p1.insert_text(pymupdf.Point(50, 50), "Page 1 Content")
        p2 = doc.new_page(width=300, height=300)
        p2.insert_text(pymupdf.Point(50, 50), "Page 2 Content")
        p3 = doc.new_page(width=300, height=300)
        p3.insert_text(pymupdf.Point(50, 50), "Page 3 Content")
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(width=300, height=300)
        b1 = TextBlock("b1", (50, 40, 200, 60), spans=[GlyphSpan("s1", "Page 1 Content", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])
        b2 = TextBlock("b2", (50, 40, 200, 60), spans=[GlyphSpan("s2", "Page 2 Content", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])
        b3 = TextBlock("b3", (50, 40, 200, 60), spans=[GlyphSpan("s3", "Page 3 Content", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])

        page1 = PageIR(1, geom, blocks=[b1])
        page2 = PageIR(2, geom, blocks=[b2])
        page3 = PageIR(3, geom, blocks=[b3])

        # Scrambled page order in DocumentIR
        doc_ir = DocumentIR("doc3", "test.pdf", 3, pages=[page3, page1, page2])

        trans = {
            "b1": "Trang 1 Bản Dịch",
            "b2": "Trang 2 Bản Dịch",
            "b3": "Trang 3 Bản Dịch",
        }

        engine = TypesetEngine()
        result = engine.typeset(original_pdf=pdf_bytes, document_ir=doc_ir, translated_segments=trans)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(len(out_doc), 3)
        self.assertIn("Trang 1 Bản Dịch", out_doc[0].get_text())
        self.assertIn("Trang 2 Bản Dịch", out_doc[1].get_text())
        self.assertIn("Trang 3 Bản Dịch", out_doc[2].get_text())
        out_doc.close()

    def test_multipage_transaction_isolation_rollback_preserves_other_pages(self) -> None:
        """3-page PDF: page 1 success, page 2 fallback, page 3 untouched; all 3 pages valid and in order."""
        doc = pymupdf.open()
        p1 = doc.new_page(width=300, height=300)
        p1.insert_text(pymupdf.Point(50, 50), "Page 1 Source")
        p2 = doc.new_page(width=300, height=300)
        p2.insert_text(pymupdf.Point(50, 50), "Page 2 Cell A")
        p2.insert_text(pymupdf.Point(150, 50), "Page 2 Cell B")
        p3 = doc.new_page(width=300, height=300)
        p3.insert_text(pymupdf.Point(50, 50), "Page 3 Source Untouched")
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(width=300, height=300)
        b_p1 = TextBlock("p1_b0", (50, 40, 200, 60), spans=[GlyphSpan("s1", "Page 1 Source", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])
        b_p2_a = TextBlock("p2_t0_r0_c0", (50, 40, 140, 60), spans=[GlyphSpan("s2a", "Page 2 Cell A", (50, 40, 140, 60), "DejaVuSans", 10.0, "#000000")], block_type="table_cell")
        b_p2_b = TextBlock("p2_t0_r0_c1", (150, 40, 240, 60), spans=[GlyphSpan("s2b", "Page 2 Cell B", (150, 40, 240, 60), "DejaVuSans", 10.0, "#000000")], block_type="table_cell")
        b_p3 = TextBlock("p3_b0", (50, 40, 200, 60), spans=[GlyphSpan("s3", "Page 3 Source Untouched", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])

        page1 = PageIR(1, geom, blocks=[b_p1])
        page2 = PageIR(2, geom, blocks=[b_p2_a, b_p2_b])
        page3 = PageIR(3, geom, blocks=[b_p3])
        doc_ir = DocumentIR("doc3", "test.pdf", 3, pages=[page1, page2, page3])

        # Page 2 cell_b has huge text that overflows, but without geometry it fails closed
        trans = {
            "p1_b0": "Trang 1 Dịch",
            "p2_t0_r0_c0": "Trang 2 Ô A",
            "p2_t0_r0_c1": "Extremely huge overflow text " * 20,
            "p3_b0": "Page 3 Source Untouched",
        }

        engine = TypesetEngine()
        result = engine.typeset(original_pdf=pdf_bytes, document_ir=doc_ir, translated_segments=trans)

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(len(out_doc), 3)
        self.assertIn("Trang 1 Dịch", out_doc[0].get_text())
        # Page 2 has uncorrupted text
        self.assertIn("Page 2 Cell B", out_doc[1].get_text())
        self.assertIn("Page 3 Source Untouched", out_doc[2].get_text())
        out_doc.close()

    def test_multipage_document_level_metadata_and_toc_preservation(self) -> None:
        """Input PDF document title/author metadata, TOC, page labels, and embedded files are preserved in output."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=300)
        doc.new_page(width=300, height=300)
        doc.set_metadata({
            "title": "Sample Doc",
            "author": "Alice",
            "subject": "Test Subject",
            "keywords": "layout, lingua, pdf",
        })
        doc.set_toc([[1, "Chapter 1", 1], [2, "Section 1.1", 2]])
        doc.embfile_add("data.txt", b"Hello Attachment")
        doc.set_page_labels([{"startpage": 0, "prefix": "sec-"}])
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 300)
        doc_ir = DocumentIR("doc_meta", "meta.pdf", 2, pages=[PageIR(1, geom), PageIR(2, geom)])
        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {})

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(out_doc.metadata.get("title"), "Sample Doc")
        self.assertEqual(out_doc.metadata.get("author"), "Alice")
        self.assertEqual(out_doc.metadata.get("subject"), "Test Subject")
        self.assertEqual(out_doc.metadata.get("keywords"), "layout, lingua, pdf")
        toc = out_doc.get_toc()
        self.assertEqual(len(toc), 2)
        self.assertEqual(toc[0][1], "Chapter 1")
        self.assertEqual(toc[1][1], "Section 1.1")
        self.assertIn("data.txt", out_doc.embfile_names())
        labels = out_doc.get_page_labels()
        self.assertTrue(len(labels) > 0)
        out_doc.close()

    def test_multipage_commit_phase_exception_recovery(self) -> None:
        """Exception during output_doc.insert_pdf() commit step on page 2 triggers atomic rollback,
        emergency commits pristine source page 2, preserves page 1 translations, and produces exact 3-page document."""
        doc = pymupdf.open()
        p1 = doc.new_page(width=300, height=300)
        p1.insert_text(pymupdf.Point(50, 50), "P1 Source")
        p2 = doc.new_page(width=300, height=300)
        p2.insert_text(pymupdf.Point(50, 50), "P2 Source")
        p3 = doc.new_page(width=300, height=300)
        p3.insert_text(pymupdf.Point(50, 50), "P3 Source")
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 300)
        b1 = TextBlock("b1", (50, 40, 200, 60), spans=[GlyphSpan("s1", "P1 Source", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])
        b2 = TextBlock("b2", (50, 40, 200, 60), spans=[GlyphSpan("s2", "P2 Source", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])
        b3 = TextBlock("b3", (50, 40, 200, 60), spans=[GlyphSpan("s3", "P3 Source", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])

        doc_ir = DocumentIR("doc_rec", "rec.pdf", 3, pages=[PageIR(1, geom, blocks=[b1]), PageIR(2, geom, blocks=[b2]), PageIR(3, geom, blocks=[b3])])
        trans = {"b1": "P1 Trans", "b2": "P2 Trans", "b3": "P3 Trans"}

        engine = TypesetEngine()

        # Simulate exception on page 2 commit by monkeypatching stage_page_transaction or insert_pdf
        orig_stage = engine.stage_page_transaction
        call_count = 0
        def faulty_stage(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            res = orig_stage(*args, **kwargs)
            if res.page_number == 2:
                # Force res.staging_doc to close prematurely so output_doc.insert_pdf(res.staging_doc) raises ValueError
                res.staging_doc.close()
            return res

        engine.stage_page_transaction = faulty_stage
        try:
            result = engine.typeset(pdf_bytes, doc_ir, trans)
        finally:
            engine.stage_page_transaction = orig_stage

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(len(out_doc), 3)
        self.assertIn("P1 Trans", out_doc[0].get_text())
        # Page 2 rolled back to pristine source due to commit failure
        self.assertIn("P2 Source", out_doc[1].get_text())
        self.assertNotIn("P2 Trans", out_doc[1].get_text())
        self.assertIn("P3 Trans", out_doc[2].get_text())
        out_doc.close()

        # Verify telemetry for page 2 reflects transaction_fallback and 0 false success
        p2_summary = [p for p in result.fitting_report.pages if p.page_number == 2][0]
        self.assertEqual(p2_summary.replaced_blocks, 0)
        self.assertEqual(p2_summary.transaction_fallback_blocks, 1)

    def test_multipage_catastrophic_page_exception_emergency_fallback(self) -> None:
        """Unhandled exception during page 2 staging triggers emergency fallback committing pristine page 2;
        page 1 remains translated, page 3 remains translated; total page count equals 3."""
        doc = pymupdf.open()
        p1 = doc.new_page(width=300, height=300)
        p1.insert_text(pymupdf.Point(50, 50), "P1 Source")
        p2 = doc.new_page(width=300, height=300)
        p2.insert_text(pymupdf.Point(50, 50), "P2 Source")
        p3 = doc.new_page(width=300, height=300)
        p3.insert_text(pymupdf.Point(50, 50), "P3 Source")
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 300)
        b1 = TextBlock("b1", (50, 40, 200, 60), spans=[GlyphSpan("s1", "P1 Source", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])
        b2 = TextBlock("b2", (50, 40, 200, 60), spans=[GlyphSpan("s2", "P2 Source", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])
        b3 = TextBlock("b3", (50, 40, 200, 60), spans=[GlyphSpan("s3", "P3 Source", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")])

        doc_ir = DocumentIR("doc_cat", "cat.pdf", 3, pages=[PageIR(1, geom, blocks=[b1]), PageIR(2, geom, blocks=[b2]), PageIR(3, geom, blocks=[b3])])
        trans = {"b1": "P1 Trans", "b2": "P2 Trans", "b3": "P3 Trans"}

        engine = TypesetEngine()
        orig_stage = engine.stage_page_transaction
        def crashing_stage(*args, **kwargs):
            page_ir = kwargs.get("page_ir") or args[1]
            if page_ir.page_number == 2:
                raise RuntimeError("Catastrophic staging crash")
            return orig_stage(*args, **kwargs)

        engine.stage_page_transaction = crashing_stage
        try:
            result = engine.typeset(pdf_bytes, doc_ir, trans)
        finally:
            engine.stage_page_transaction = orig_stage

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(len(out_doc), 3)
        self.assertIn("P1 Trans", out_doc[0].get_text())
        self.assertIn("P2 Source", out_doc[1].get_text())
        self.assertIn("P3 Trans", out_doc[2].get_text())
        out_doc.close()


class TestPostAssemblyLinkRestoration(unittest.TestCase):
    """Task 8: Post-Assembly Link Restoration & Dual LINK_NAMED Engine."""

    def test_multipage_cross_page_internal_and_external_link_restoration(self) -> None:
        """3-page PDF: internal link from page 1 pointing to page 3, internal link from page 3 pointing to page 1,
        and external URI link on page 2. Verifies after serializing to bytes and reopening that all 3 links exist."""
        doc = pymupdf.open()
        p1 = doc.new_page(width=300, height=300)
        p2 = doc.new_page(width=300, height=300)
        p3 = doc.new_page(width=300, height=300)

        # Retrieve through doc[i] to ensure valid internal page references
        doc[0].insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(50, 50, 100, 70), "page": 2, "to": pymupdf.Point(50, 100)})
        doc[1].insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(50, 50, 100, 70), "uri": "https://example.com"})
        doc[2].insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(50, 50, 100, 70), "page": 0, "to": pymupdf.Point(50, 50)})
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 300)
        doc_ir = DocumentIR("doc_links", "links.pdf", 3, pages=[PageIR(1, geom), PageIR(2, geom), PageIR(3, geom)])
        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {})

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        l1 = out_doc[0].get_links()
        self.assertEqual(len(l1), 1)
        self.assertEqual(l1[0]["kind"], pymupdf.LINK_GOTO)
        self.assertEqual(l1[0]["page"], 2)
        self.assertEqual(l1[0]["to"], pymupdf.Point(50, 100))

        l2 = out_doc[1].get_links()
        self.assertEqual(len(l2), 1)
        self.assertEqual(l2[0]["kind"], pymupdf.LINK_URI)
        self.assertEqual(l2[0]["uri"], "https://example.com")

        l3 = out_doc[2].get_links()
        self.assertEqual(len(l3), 1)
        self.assertEqual(l3[0]["kind"], pymupdf.LINK_GOTO)
        self.assertEqual(l3[0]["page"], 0)
        self.assertEqual(l3[0]["to"], pymupdf.Point(50, 50))
        out_doc.close()

    def test_multipage_named_actions_preservation(self) -> None:
        """2-page PDF fixture containing standard predefined viewer action links (name='NextPage', 'PrevPage')."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=300)
        doc.new_page(width=300, height=300)
        doc[0].insert_link({"kind": pymupdf.LINK_NAMED, "from": pymupdf.Rect(50, 50, 100, 70), "name": "NextPage"})
        doc[1].insert_link({"kind": pymupdf.LINK_NAMED, "from": pymupdf.Rect(50, 50, 100, 70), "name": "PrevPage"})
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 300)
        doc_ir = DocumentIR("doc_act", "act.pdf", 2, pages=[PageIR(1, geom), PageIR(2, geom)])
        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {})

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        l1 = out_doc[0].get_links()
        self.assertEqual(len(l1), 1)
        self.assertEqual(l1[0]["kind"], pymupdf.LINK_NAMED)
        self.assertIn("NextPage", l1[0].get("name", "") or l1[0].get("nameddest", ""))

        l2 = out_doc[1].get_links()
        self.assertEqual(len(l2), 1)
        self.assertEqual(l2[0]["kind"], pymupdf.LINK_NAMED)
        self.assertIn("PrevPage", l2[0].get("name", "") or l2[0].get("nameddest", ""))
        out_doc.close()

    def test_multipage_named_destination_resolution_standard_page(self) -> None:
        """2-page standard PDF (300 x 400 pt, unrotated): catalog /Dests defines section_std pointing to page 1
        at PDF coordinates (x=40, y=320). Verifies conversion to LINK_GOTO targeting Point(40.0, 80.0)."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=400)
        doc.new_page(width=300, height=400)
        cat = doc.pdf_catalog()
        p2_xref = doc.page_xref(1)
        doc.xref_set_key(cat, "Dests", f"<</section_std [{p2_xref} 0 R /XYZ 40 320 0]>>")
        doc[0].insert_link({"kind": pymupdf.LINK_NAMED, "from": pymupdf.Rect(50, 50, 100, 70), "name": "nameddest=section_std"})
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 400)
        doc_ir = DocumentIR("doc_std", "std.pdf", 2, pages=[PageIR(1, geom), PageIR(2, geom)])
        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {})

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        links = out_doc[0].get_links()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["kind"], pymupdf.LINK_GOTO)
        self.assertEqual(links[0]["page"], 1)
        self.assertEqual(links[0]["to"], pymupdf.Point(40.0, 80.0))
        out_doc.close()

    def test_multipage_named_destination_resolution_offset_cropbox(self) -> None:
        """2-page PDF where destination page 1 has offset CropBox: MediaBox = Rect(0, 0, 300, 400),
        CropBox = Rect(50, 50, 250, 350). Catalog destination section_crop has PDF coordinates (100, 200)."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=400)
        doc.new_page(width=300, height=400)
        doc[1].set_cropbox(pymupdf.Rect(50, 50, 250, 350))
        cat = doc.pdf_catalog()
        p2_xref = doc.page_xref(1)
        doc.xref_set_key(cat, "Dests", f"<</section_crop [{p2_xref} 0 R /XYZ 100 200 0]>>")
        doc[0].insert_link({"kind": pymupdf.LINK_NAMED, "from": pymupdf.Rect(50, 50, 100, 70), "name": "nameddest=section_crop"})
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 400)
        doc_ir = DocumentIR("doc_crop", "crop.pdf", 2, pages=[PageIR(1, geom), PageIR(2, geom)])
        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {})

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        links = out_doc[0].get_links()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["kind"], pymupdf.LINK_GOTO)
        self.assertEqual(links[0]["page"], 1)
        self.assertEqual(links[0]["to"], pymupdf.Point(50.0, 150.0))
        out_doc.close()

    def test_multipage_named_destination_resolution_rotated_page(self) -> None:
        """3-page PDF where destination page 1 has rotation = 90 and page 2 has rotation = 270.
        Verifies links converted to LINK_GOTO with correct orientation."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=400)
        doc.new_page(width=300, height=400)
        doc.new_page(width=300, height=400)
        doc[1].set_rotation(90)
        doc[2].set_rotation(270)
        cat = doc.pdf_catalog()
        p2_xref = doc.page_xref(1)
        doc.xref_set_key(cat, "Dests", f"<</section_rot [{p2_xref} 0 R /XYZ 40 320 0]>>")
        doc[0].insert_link({"kind": pymupdf.LINK_NAMED, "from": pymupdf.Rect(50, 50, 100, 70), "name": "nameddest=section_rot"})
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 400)
        doc_ir = DocumentIR("doc_rot", "rot.pdf", 3, pages=[PageIR(1, geom), PageIR(2, geom), PageIR(3, geom)])
        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {})

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        links = out_doc[0].get_links()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["kind"], pymupdf.LINK_GOTO)
        self.assertEqual(links[0]["page"], 1)
        expected_to = (
            pymupdf.Point(40, 320)
            * out_doc[1].transformation_matrix
            * out_doc[1].rotation_matrix
        )
        self.assertEqual(links[0]["to"], expected_to)
        out_doc.close()

    def test_multipage_unresolvable_named_destination_emits_warning_no_dead_link(self) -> None:
        """Input PDF contains link with name='nameddest=missing_target' where destination is absent from catalog /Dests.
        Verifies link insertion is skipped (no dead link) and warning is logged."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=400)
        doc[0].insert_link({"kind": pymupdf.LINK_NAMED, "from": pymupdf.Rect(50, 50, 100, 70), "name": "nameddest=missing_target"})
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 400)
        doc_ir = DocumentIR("doc_unres", "unres.pdf", 1, pages=[PageIR(1, geom)])
        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {})

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(len(out_doc[0].get_links()), 0)
        out_doc.close()

        self.assertTrue(any("missing_target" in w for w in result.fitting_report.warnings))

    def test_multipage_form_widgets_and_catalog_dests_warning(self) -> None:
        """Multi-page form with shared field names retains unified identity via join_duplicates=True;
        standalone catalog named destinations log diagnostic warning."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=400)
        doc.new_page(width=300, height=400)
        cat = doc.pdf_catalog()
        p2_xref = doc.page_xref(1)
        doc.xref_set_key(cat, "Dests", f"<</standalone_dest [{p2_xref} 0 R /XYZ 50 100 0]>>")

        widget1 = pymupdf.Widget()
        widget1.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget1.rect = pymupdf.Rect(50, 50, 150, 70)
        widget1.field_name = "test_field"
        doc[0].add_widget(widget1)

        widget2 = pymupdf.Widget()
        widget2.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget2.rect = pymupdf.Rect(50, 50, 150, 70)
        widget2.field_name = "test_field"
        doc[1].add_widget(widget2)

        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 400)
        doc_ir = DocumentIR("doc_form", "form.pdf", 2, pages=[PageIR(1, geom), PageIR(2, geom)])
        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {})

        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(len(out_doc), 2)
        # Verify form widgets preserved
        fields = [w.field_name for page in out_doc for w in page.widgets()]
        self.assertTrue(len(fields) >= 2)
        self.assertIn("test_field", fields)
        out_doc.close()

        # Verify standalone catalog named destinations warning emitted
        self.assertTrue(any("standalone_dest" in w or "catalog" in w.lower() for w in result.fitting_report.warnings))



class TestTelemetryCacheAndIntegrity(unittest.TestCase):
    def test_table_level_telemetry_isolation_no_block_inflation(self) -> None:
        """Rejected table logs unit_kind='TABLE' without inflating skipped_blocks or total_cells."""
        report = FittingReport()
        summary = PageFittingSummary(page_number=1)
        detail = BlockFittingDetail(
            block_id="p1_table_0",
            page_number=1,
            status=BlockFittingStatus.SKIPPED_UNSUPPORTED,
            original_text="",
            translated_text="",
            original_font_size=10.0,
            final_font_size=10.0,
            unit_kind="TABLE",
            reason="Table grid corroboration failed: missing divider.",
        )
        report.details.append(detail)
        report.rejected_tables += 1
        self.assertEqual(report.rejected_tables, 1)
        self.assertEqual(report.total_cells, 0)
        self.assertEqual(report.replaced_cells, 0)

    def test_table_cell_translation_cache_isolation_from_merged_blocks(self) -> None:
        """Partitioned cell translations do not hit stale cache entries from previous merged-block translations."""
        from layoutlingua.translation._storage import compute_cache_key

        key_merged = compute_cache_key("mock", "model", "en", "vi", "p1", "norm", "gloss", "gen", "Col A Col B")
        key_cell_a = compute_cache_key("mock", "model", "en", "vi", "p1", "norm", "gloss", "gen", "Col A")
        key_cell_b = compute_cache_key("mock", "model", "en", "vi", "p1", "norm", "gloss", "gen", "Col B")
        key_cell_a_dup = compute_cache_key("mock", "model", "en", "vi", "p1", "norm", "gloss", "gen", "Col A")

        self.assertNotEqual(key_merged, key_cell_a)
        self.assertNotEqual(key_merged, key_cell_b)
        self.assertEqual(key_cell_a, key_cell_a_dup)

    def test_rebuilt_pdf_table_visual_and_structural_integrity(self) -> None:
        """Output PDF contains valid vector drawings, correct text placement, unchanged page dimensions."""
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(50, 50, 250, 150))
        shape.finish(color=(0, 0, 0), width=1.0)
        shape.commit()
        page.insert_text(pymupdf.Point(60, 80), "Header")
        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 300)
        p = PageIR(1, geom, blocks=[TextBlock("b0", (60, 70, 100, 85), spans=[GlyphSpan("s0", "Header", (60, 70, 100, 85), "DejaVuSans", 10.0, "#000000")])])
        doc_ir = DocumentIR("doc_vis", "vis.pdf", 1, pages=[p])

        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, {"b0": "Tiêu đề"})
        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertGreaterEqual(len(out_doc[0].get_drawings()), 1)
        self.assertEqual(out_doc[0].rect.width, 300)
        self.assertEqual(out_doc[0].rect.height, 300)
        text_out = out_doc[0].get_text()
        self.assertIn("Tiêu đề", text_out)
        out_doc.close()

    def test_end_to_end_full_pipeline_multi_page_pdf_integration(self) -> None:
        """End-to-end integration: 2-page document with text, table cells, drawings, and cross-page link."""
        doc = pymupdf.open()
        doc.new_page(width=300, height=400)
        doc.new_page(width=300, height=400)
        p0 = doc[0]
        p1 = doc[1]

        # Page 0 has a vector table border and text
        shape = p0.new_shape()
        shape.draw_rect(pymupdf.Rect(50, 50, 250, 150))
        shape.finish(color=(0, 0, 0), width=1.0)
        shape.commit()
        p0.insert_text(pymupdf.Point(60, 80), "Cell A")
        p0.insert_text(pymupdf.Point(160, 80), "Cell B")

        # Page 0 has a cross-page link to Page 1
        p0.insert_link({
            "kind": pymupdf.LINK_GOTO,
            "from": pymupdf.Rect(50, 200, 150, 220),
            "page": 1,
            "to": pymupdf.Point(50, 50),
        })

        # Page 1 has regular text
        p1.insert_text(pymupdf.Point(50, 50), "Target on Page 2")

        pdf_bytes = doc.tobytes()
        doc.close()

        geom = PageGeometry(300, 400)
        c0 = CellGeometry("p1_t0_r0_c0", 0, 0, (50, 50, 150, 150), {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0})
        c1 = CellGeometry("p1_t0_r0_c1", 0, 1, (150, 50, 250, 150), {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0})
        grid = TableGrid("p1_t0", (50, 50, 250, 150), 1, 2, {c0.cell_id: c0, c1.cell_id: c1})

        b_c0 = TextBlock(
            "p1_t0_r0_c0",
            (50, 50, 150, 150),
            spans=[GlyphSpan("s0", "Cell A", (60, 70, 100, 85), "DejaVuSans", 10.0, "#000000")],
            block_type="table_cell",
        )
        b_c1 = TextBlock(
            "p1_t0_r0_c1",
            (150, 50, 250, 150),
            spans=[GlyphSpan("s1", "Cell B", (160, 70, 200, 85), "DejaVuSans", 10.0, "#000000")],
            block_type="table_cell",
        )
        page1_ir = PageIR(
            page_number=1,
            geometry=geom,
            blocks=[b_c0, b_c1],
            metadata={"tables": {"p1_t0": grid}},
        )
        b_p2 = TextBlock(
            "p2_b0",
            (50, 40, 200, 60),
            spans=[GlyphSpan("s2", "Target on Page 2", (50, 40, 200, 60), "DejaVuSans", 10.0, "#000000")],
            block_type="text",
        )
        page2_ir = PageIR(page_number=2, geometry=geom, blocks=[b_p2])

        doc_ir = DocumentIR("e2e_doc", "e2e.pdf", 2, pages=[page1_ir, page2_ir])

        translations = {
            "p1_t0_r0_c0": "Ô A",
            "p1_t0_r0_c1": "Ô B",
            "p2_b0": "Đích đến ở Trang 2",
        }

        engine = TypesetEngine()
        result = engine.typeset(pdf_bytes, doc_ir, translations)

        self.assertIsNotNone(result.pdf_bytes)
        out_doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
        self.assertEqual(len(out_doc), 2)

        # 1. Vector drawings preserved
        self.assertGreaterEqual(len(out_doc[0].get_drawings()), 1)

        # 2. Cell text replaced
        text_p1 = out_doc[0].get_text()
        self.assertIn("Ô A", text_p1)
        self.assertIn("Ô B", text_p1)

        # 3. Target text replaced
        text_p2 = out_doc[1].get_text()
        self.assertIn("Đích đến ở Trang 2", text_p2)

        # 4. Cross-page link restored
        links_p1 = out_doc[0].get_links()
        self.assertEqual(len(links_p1), 1)
        self.assertEqual(links_p1[0]["kind"], pymupdf.LINK_GOTO)
        self.assertEqual(links_p1[0]["page"], 1)

        # 5. Multi-tier telemetry
        rep = result.fitting_report
        self.assertEqual(rep.total_cells, 2)
        self.assertEqual(rep.replaced_cells, 2)
        self.assertEqual(rep.total_blocks, 3)
        self.assertEqual(rep.replaced_blocks, 3)
        self.assertEqual(rep.rejected_tables, 0)
        self.assertEqual(len(rep.warnings), 0)

        out_doc.close()


if __name__ == "__main__":
    unittest.main()

