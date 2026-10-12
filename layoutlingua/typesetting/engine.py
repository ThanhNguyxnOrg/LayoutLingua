"""Deep module typesetting engine for LayoutLingua.

Preserves PDF background graphics, selective text clearance with fill=False,
precision binary search font fitting, dynamic line-height, and multi-tier telemetry.
"""

from __future__ import annotations

import pymupdf

from layoutlingua.core.ir import DocumentIR, TextBlock
from layoutlingua.typesetting.fitting import TextFitTester, parse_color
from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.models import (
    BlockFittingDetail,
    BlockFittingStatus,
    CollisionDetail,
    FittingReport,
    OverflowCause,
    PageFittingSummary,
    TypesetOptions,
    TypesetResult,
)
from layoutlingua.typesetting.protection import ClearancePlanner


class TypesetEngine:
    """Deep module coordinating text clearance, font fitting, and PDF document regeneration."""

    def __init__(
        self,
        options: TypesetOptions | None = None,
        font_manager: FontManager | None = None,
    ) -> None:
        self.options = options or TypesetOptions()
        self.font_manager = font_manager or FontManager()
        # Verify font integrity on engine startup
        self.font_manager.verify_checksum()
        self.font_manager.validate_vietnamese_glyphs()
        self._fit_tester = TextFitTester(
            font_manager=self.font_manager,
            font_name=self.options.font_name,
        )
        self._clearance_planner = ClearancePlanner(padding_pt=self.options.clearance_padding_pt)

    def typeset(
        self,
        original_pdf: bytes,
        document_ir: DocumentIR,
        translated_segments: dict[str, str],
    ) -> TypesetResult:
        """Render translated segments into a new PDF preserving layout, formulas, and background art.

        Args:
            original_pdf: Raw byte buffer of the input PDF document.
            document_ir: Extracted Intermediate Representation containing geometric coordinates.
            translated_segments: Map of segment_id / block_id to translated string content.

        Returns:
            TypesetResult containing the regenerated PDF bytes and fitting telemetry.
        """
        if not original_pdf:
            raise ValueError("original_pdf buffer must not be empty.")

        doc = pymupdf.open(stream=original_pdf, filetype="pdf")
        report = FittingReport()

        all_replaced_shrink_ratios: list[float] = []

        for page_ir in document_ir.pages:
            page_idx = page_ir.page_number - 1
            if page_idx >= len(doc):
                continue

            page = doc[page_idx]
            self.font_manager.register_on_page(page, font_name=self.options.font_name)

            page_summary = PageFittingSummary(page_number=page_ir.page_number)
            page_replaced_ratios: list[float] = []

            # 0. Collect preserved block IDs from document and page metadata (fail-closed)
            preserved_ids = set()
            if hasattr(document_ir, "metadata") and isinstance(document_ir.metadata, dict):
                p_ids = document_ir.metadata.get("preserved_block_ids", set())
                if isinstance(p_ids, (set, list, tuple)):
                    preserved_ids.update(p_ids)
            if hasattr(page_ir, "metadata") and isinstance(page_ir.metadata, dict):
                p_ids = page_ir.metadata.get("preserved_block_ids", set())
                if isinstance(p_ids, (set, list, tuple)):
                    preserved_ids.update(p_ids)

            # 1. Identify translation candidate blocks for this page
            candidate_blocks: list[TextBlock] = []
            block_translation_map: dict[str, str] = {}
            for block in page_ir.blocks:
                if block.block_type in ("formula", "table_rejected") or block.block_id in preserved_ids:
                    continue
                trans_text = self._resolve_translated_text(block, translated_segments)
                if trans_text and trans_text.strip() and trans_text.strip() != block.text.strip():
                    candidate_blocks.append(block)
                    block_translation_map[block.block_id] = trans_text

            # 2. Pre-compute read-only clearance plan on pristine page before any redactions
            clearance_plan = self._clearance_planner.plan_page_clearance(
                page_ir=page_ir,
                page=page,
                candidate_blocks=candidate_blocks,
            )

            # Structure: (block, tight_line_rects, translated_text, orig_font_size, dominant_color, final_font_size, lineheight, line_count, target_layout_box, is_cell, grid, cell_geom)
            fitting_plan: list[
                tuple[
                    TextBlock,
                    list[tuple[float, float, float, float]],
                    str,
                    float,
                    tuple[float, float, float],
                    float,
                    float,
                    int,
                    tuple[float, float, float, float],
                    bool,
                    Any,
                    Any,
                ]
            ] = []

            for block in page_ir.blocks:
                report.total_blocks += 1
                page_summary.total_blocks += 1

                is_cell = (block.block_type == "table_cell")
                if is_cell:
                    report.total_cells += 1
                    page_summary.total_cells += 1

                # 3. Formula preservation check
                if block.block_type == "formula":
                    report.skipped_blocks += 1
                    page_summary.skipped_blocks += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SKIPPED_FORMULA,
                            original_text=block.text,
                            translated_text="",
                            original_font_size=10.0,
                            final_font_size=10.0,
                            shrink_ratio=1.0,
                            bbox=block.bbox,
                            reason="Formula block preserved intact without translation mutation.",
                        )
                    )
                    continue

                # 3b. Preserved / Rejected table block check (fail-closed)
                if block.block_type == "table_rejected" or block.block_id in preserved_ids:
                    report.skipped_blocks += 1
                    page_summary.skipped_blocks += 1
                    if is_cell:
                        report.skipped_cells += 1
                        page_summary.skipped_cells += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SKIPPED_UNSUPPORTED,
                            original_text=block.text,
                            translated_text="",
                            original_font_size=10.0,
                            final_font_size=10.0,
                            shrink_ratio=1.0,
                            bbox=block.bbox,
                            unit_kind="CELL" if is_cell else "BLOCK",
                            reason="Preserved source text: constituent block of rejected table.",
                        )
                    )
                    continue

                # 3c. Table cell geometry and stroke-aware insets resolution (Task 5)
                grid = None
                cell_geom = None
                inner_bbox = None
                if is_cell:
                    if hasattr(page_ir, "metadata") and isinstance(page_ir.metadata, dict):
                        tables = page_ir.metadata.get("tables", {})
                        if isinstance(tables, dict):
                            for g in tables.values():
                                if hasattr(g, "cells") and isinstance(g.cells, dict) and block.block_id in g.cells:
                                    grid = g
                                    cell_geom = g.cells[block.block_id]
                                    break

                    if cell_geom is None:
                        # Missing cell geometry in table grid (fail-closed)
                        report.skipped_blocks += 1
                        report.skipped_cells += 1
                        page_summary.skipped_blocks += 1
                        page_summary.skipped_cells += 1
                        report.details.append(
                            BlockFittingDetail(
                                block_id=block.block_id,
                                page_number=page_ir.page_number,
                                status=BlockFittingStatus.SKIPPED_UNSUPPORTED,
                                original_text=block.text,
                                translated_text="",
                                original_font_size=10.0,
                                final_font_size=10.0,
                                shrink_ratio=1.0,
                                bbox=block.bbox,
                                unit_kind="CELL",
                                reason="Missing cell geometry in table grid (fail-closed).",
                            )
                        )
                        continue

                    inner_bbox = cell_geom.compute_inner_bbox()
                    if inner_bbox is None:
                        # Narrow or shallow cell where padding exceeds dimensions (fail-closed)
                        report.overflow_blocks += 1
                        report.overflow_cells += 1
                        page_summary.overflow_blocks += 1
                        page_summary.overflow_cells += 1
                        report.details.append(
                            BlockFittingDetail(
                                block_id=block.block_id,
                                page_number=page_ir.page_number,
                                status=BlockFittingStatus.OVERFLOW_FALLBACK,
                                original_text=block.text,
                                translated_text="",
                                original_font_size=10.0,
                                final_font_size=10.0,
                                shrink_ratio=1.0,
                                bbox=block.bbox,
                                overflow_cause=OverflowCause.OVERFLOW_WIDTH_AT_MIN_SIZE,
                                unit_kind="CELL",
                                table_id=grid.table_id if grid else None,
                                row_idx=cell_geom.row_idx,
                                col_idx=cell_geom.col_idx,
                                reason="Cell too narrow or shallow for stroke-aware insets (fail-closed).",
                            )
                        )
                        continue

                # 4. Extract translation candidate
                translated_text = self._resolve_translated_text(block, translated_segments)
                if not translated_text or not translated_text.strip():
                    report.skipped_blocks += 1
                    page_summary.skipped_blocks += 1
                    if is_cell:
                        report.skipped_cells += 1
                        page_summary.skipped_cells += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SKIPPED_EMPTY,
                            original_text=block.text,
                            translated_text="",
                            original_font_size=10.0,
                            final_font_size=10.0,
                            shrink_ratio=1.0,
                            bbox=block.bbox,
                            unit_kind="CELL" if is_cell else "BLOCK",
                            table_id=grid.table_id if grid else None,
                            row_idx=cell_geom.row_idx if cell_geom else None,
                            col_idx=cell_geom.col_idx if cell_geom else None,
                            reason="No translation provided or text is whitespace.",
                        )
                    )
                    continue

                if translated_text.strip() == block.text.strip():
                    report.skipped_blocks += 1
                    page_summary.skipped_blocks += 1
                    if is_cell:
                        report.skipped_cells += 1
                        page_summary.skipped_cells += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SKIPPED_UNCHANGED,
                            original_text=block.text,
                            translated_text=translated_text,
                            original_font_size=10.0,
                            final_font_size=10.0,
                            shrink_ratio=1.0,
                            bbox=block.bbox,
                            unit_kind="CELL" if is_cell else "BLOCK",
                            table_id=grid.table_id if grid else None,
                            row_idx=cell_geom.row_idx if cell_geom else None,
                            col_idx=cell_geom.col_idx if cell_geom else None,
                            reason="Translated text is identical to source text.",
                        )
                    )
                    continue

                # 5. Clearance check: verify safety from pre-computed clearance plan
                decision = clearance_plan.decisions.get(block.block_id)
                if decision is not None and not decision.is_approved:
                    report.collision_blocks += 1
                    page_summary.collision_blocks += 1
                    if is_cell:
                        report.collision_cells += 1
                        page_summary.collision_cells += 1
                    coll = decision.collision_detail
                    coll_type = coll.collision_type if coll else "UNKNOWN"
                    coll_desc = coll.description if coll else "Geometric collision detected."
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.COLLISION_FALLBACK,
                            original_text=block.text,
                            translated_text=translated_text,
                            original_font_size=10.0,
                            final_font_size=10.0,
                            shrink_ratio=1.0,
                            bbox=block.bbox,
                            unit_kind="CELL" if is_cell else "BLOCK",
                            table_id=grid.table_id if grid else None,
                            row_idx=cell_geom.row_idx if cell_geom else None,
                            col_idx=cell_geom.col_idx if cell_geom else None,
                            collision_detail=coll,
                            reason=f"Collision detected ({coll_type}): {coll_desc}. Source retained.",
                        )
                    )
                    continue

                # 6. Determine metrics and color
                orig_font_size = max((s.font_size for s in block.spans), default=10.0)
                dominant_color = (
                    parse_color(block.spans[0].color) if block.spans else (0.0, 0.0, 0.0)
                )

                # 7. Precision Binary Search fitting test with dynamic line-height
                target_layout_box = inner_bbox if is_cell and inner_bbox else block.bbox

                fits, final_font_size, overflow_cause, line_count, effective_lineheight = self._fit_tester.test_fit(
                    rect=target_layout_box,
                    text=translated_text,
                    orig_font_size=orig_font_size,
                    options=self.options,
                )

                if is_cell and inner_bbox:
                    # Clamp tight line redaction rects strictly within inner_bbox
                    raw_lines = decision.tight_line_rects if decision else [inner_bbox]
                    tight_line_rects = [
                        (
                            max(inner_bbox[0], r[0]),
                            max(inner_bbox[1], r[1]),
                            min(inner_bbox[2], r[2]),
                            min(inner_bbox[3], r[3]),
                        )
                        for r in raw_lines
                        if min(inner_bbox[2], r[2]) > max(inner_bbox[0], r[0])
                        and min(inner_bbox[3], r[3]) > max(inner_bbox[1], r[1])
                    ]
                    if not tight_line_rects:
                        tight_line_rects = [inner_bbox]
                else:
                    tight_line_rects = (
                        decision.tight_line_rects
                        if decision
                        else [(block.bbox[0], block.bbox[1], block.bbox[2], block.bbox[3])]
                    )

                if fits:
                    fitting_plan.append((
                        block,
                        tight_line_rects,
                        translated_text,
                        orig_font_size,
                        dominant_color,
                        final_font_size,
                        effective_lineheight,
                        line_count,
                        target_layout_box,
                        is_cell,
                        grid,
                        cell_geom,
                    ))
                else:
                    # Overflow event: fail-closed preserves source text
                    report.overflow_blocks += 1
                    page_summary.overflow_blocks += 1
                    if is_cell:
                        report.overflow_cells += 1
                        page_summary.overflow_cells += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.OVERFLOW_FALLBACK,
                            original_text=block.text,
                            translated_text=translated_text,
                            original_font_size=orig_font_size,
                            final_font_size=orig_font_size,
                            shrink_ratio=1.0,
                            line_height_em=effective_lineheight,
                            line_count=line_count,
                            bbox=target_layout_box,
                            overflow_cause=overflow_cause,
                            unit_kind="CELL" if is_cell else "BLOCK",
                            table_id=grid.table_id if grid else None,
                            row_idx=cell_geom.row_idx if cell_geom else None,
                            col_idx=cell_geom.col_idx if cell_geom else None,
                            reason=(
                                f"Translated text overflowed {'cell inner' if is_cell else ''} bounding box "
                                f"({overflow_cause.value}) at minimum scale ({self.options.min_font_scale:.0%}). Source retained."
                            ),
                        )
                    )

            # 8. Apply selective redaction ONLY to approved, fitting candidates using tight line rects
            if fitting_plan:
                for block, tight_line_rects, _, _, _, _, _, _, _, _, _, _ in fitting_plan:
                    for line_rect in tight_line_rects:
                        rect = pymupdf.Rect(*line_rect)
                        page.add_redact_annot(rect, fill=False, cross_out=False)

                page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_NONE,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )

                # 9. Insert translated text using identical effective line-height
                for (
                    block,
                    _,
                    text,
                    orig_size,
                    color,
                    final_size,
                    lineheight,
                    line_count,
                    target_layout_box,
                    is_cell,
                    grid,
                    cell_geom,
                ) in fitting_plan:
                    rect = pymupdf.Rect(*target_layout_box)
                    page.insert_textbox(
                        rect,
                        text,
                        fontsize=final_size,
                        fontname=self.options.font_name,
                        fontfile=str(self.font_manager.font_path),
                        color=color,
                        lineheight=lineheight,
                    )
                    shrink_ratio = final_size / orig_size if orig_size > 0 else 1.0
                    page_replaced_ratios.append(shrink_ratio)
                    all_replaced_shrink_ratios.append(shrink_ratio)

                    report.replaced_blocks += 1
                    page_summary.replaced_blocks += 1
                    if is_cell:
                        report.replaced_cells += 1
                        page_summary.replaced_cells += 1

                    if shrink_ratio < self.options.severe_shrink_threshold:
                        report.severe_shrink_blocks_count += 1

                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SUCCESS,
                            original_text=block.text,
                            translated_text=text,
                            original_font_size=orig_size,
                            final_font_size=final_size,
                            shrink_ratio=shrink_ratio,
                            line_height_em=lineheight,
                            line_count=line_count,
                            bbox=target_layout_box,
                            overflow_cause=OverflowCause.NONE,
                            unit_kind="CELL" if is_cell else "BLOCK",
                            table_id=grid.table_id if grid else None,
                            row_idx=cell_geom.row_idx if cell_geom else None,
                            col_idx=cell_geom.col_idx if cell_geom else None,
                            reason=(
                                f"Successfully typeset with shrink ratio {shrink_ratio:.2f}."
                                if not is_cell
                                else f"Successfully typeset inside stroke-aware cell inner bbox (shrink ratio {shrink_ratio:.2f})."
                            ),
                        )
                    )

            # Aggregate page summary metrics
            if page_replaced_ratios:
                page_summary.avg_shrink_ratio = sum(page_replaced_ratios) / len(page_replaced_ratios)
                page_summary.worst_shrink_ratio = min(page_replaced_ratios)
                page_summary.has_severe_shrink_warning = (
                    page_summary.worst_shrink_ratio < self.options.severe_shrink_threshold
                )
            else:
                page_summary.avg_shrink_ratio = 1.0
                page_summary.worst_shrink_ratio = 1.0
                page_summary.has_severe_shrink_warning = False

            report.pages.append(page_summary)

        # Aggregate document summary metrics
        if all_replaced_shrink_ratios:
            report.avg_shrink_ratio = sum(all_replaced_shrink_ratios) / len(all_replaced_shrink_ratios)
            report.worst_shrink_ratio = min(all_replaced_shrink_ratios)
        else:
            report.avg_shrink_ratio = 1.0
            report.worst_shrink_ratio = 1.0

        output_bytes = doc.tobytes(deflate=True, garbage=3)
        return TypesetResult(pdf_bytes=output_bytes, fitting_report=report)

    def _resolve_translated_text(
        self,
        block: TextBlock,
        translated_segments: dict[str, str],
    ) -> str:
        """Resolve translated string for a block from the segment map."""
        # 1. Exact match by block_id
        if block.block_id in translated_segments:
            return translated_segments[block.block_id]

        # 2. Single span match
        if len(block.spans) == 1 and block.spans[0].span_id in translated_segments:
            return translated_segments[block.spans[0].span_id]

        # 3. Constituent span matches
        has_any = any(s.span_id in translated_segments for s in block.spans)
        if has_any:
            parts = [translated_segments.get(s.span_id, s.text) for s in block.spans]
            return "".join(parts)

        return ""
