"""Deep module typesetting engine for LayoutLingua.

Preserves PDF background graphics, selective text clearance with fill=False,
precision binary search font fitting, dynamic line-height, and multi-tier telemetry.
"""

from __future__ import annotations

import pymupdf

from layoutlingua.core.ir import DocumentIR, PageIR, TextBlock
from layoutlingua.typesetting.fitting import TextFitTester, parse_color
from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.models import (
    BlockFittingDetail,
    BlockFittingStatus,
    CollisionDetail,
    FittingReport,
    OverflowCause,
    PageFittingSummary,
    PageTransactionResult,
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
    def stage_page_transaction(
        self,
        source_doc: pymupdf.Document,
        page_ir: PageIR,
        document_ir: DocumentIR,
        translated_segments: dict[str, str],
        force_fallback: bool = False,
    ) -> PageTransactionResult:
        """Stage single-page typesetting inside an isolated scratch document.

        Guarantees:
        - Invariant: page_number == source_page_index + 1
        - Staging occurs strictly on an isolated scratch document copied from source_doc[source_page_index].
        - If any unhandled exception or critical safety failure occurs, rolls back cleanly
          to a pristine source page clone with is_fallback=True, preserving 100% of source bytes.
        - Telemetry reflects fallback or success without false records.
        """
        page_number = page_ir.page_number
        source_page_index = page_number - 1
        assert page_number == source_page_index + 1, f"Indexing contract violated: {page_number} != {source_page_index} + 1"

        if source_page_index < 0 or source_page_index >= len(source_doc):
            raise IndexError(f"source_page_index {source_page_index} out of range [0, {len(source_doc)})")

        def _build_fallback_result(reason: str = "Transaction rollback to pristine source page.") -> PageTransactionResult:
            fallback_doc = pymupdf.open()
            fallback_doc.insert_pdf(source_doc, from_page=source_page_index, to_page=source_page_index)

            summary = PageFittingSummary(page_number=page_number)
            details: list[BlockFittingDetail] = []

            for block in page_ir.blocks:
                is_cell = (block.block_type == "table_cell")
                summary.total_blocks += 1
                if is_cell:
                    summary.total_cells += 1

                trans_text = self._resolve_translated_text(block, translated_segments)
                was_candidate = bool(
                    trans_text
                    and trans_text.strip()
                    and trans_text.strip() != block.text.strip()
                    and block.block_type not in ("formula", "table_rejected")
                )

                if was_candidate:
                    summary.transaction_fallback_blocks += 1
                    if is_cell:
                        summary.transaction_fallback_cells += 1
                    status = BlockFittingStatus.TRANSACTION_FALLBACK
                else:
                    summary.skipped_blocks += 1
                    if is_cell:
                        summary.skipped_cells += 1
                    status = BlockFittingStatus.SKIPPED_UNCHANGED

                details.append(
                    BlockFittingDetail(
                        block_id=block.block_id,
                        page_number=page_number,
                        status=status,
                        original_text=block.text,
                        translated_text="",
                        original_font_size=10.0,
                        final_font_size=10.0,
                        shrink_ratio=1.0,
                        bbox=block.bbox,
                        unit_kind="CELL" if is_cell else "BLOCK",
                        reason=reason,
                    )
                )

            return PageTransactionResult(
                page_number=page_number,
                source_page_index=source_page_index,
                staging_doc=fallback_doc,
                is_fallback=True,
                details=details,
                summary=summary,
            )

        if force_fallback:
            return _build_fallback_result("Forced page transaction fallback.")

        staging_doc = pymupdf.open()
        try:
            staging_doc.insert_pdf(source_doc, from_page=source_page_index, to_page=source_page_index)
            scratch_page = staging_doc[0]
            self.font_manager.register_on_page(scratch_page, font_name=self.options.font_name)

            page_summary = PageFittingSummary(page_number=page_number)
            page_replaced_ratios: list[float] = []
            page_details: list[BlockFittingDetail] = []

            # 0. Collect preserved block IDs
            preserved_ids = set()
            if hasattr(document_ir, "metadata") and isinstance(document_ir.metadata, dict):
                p_ids = document_ir.metadata.get("preserved_block_ids", set())
                if isinstance(p_ids, (set, list, tuple)):
                    preserved_ids.update(p_ids)
            if hasattr(page_ir, "metadata") and isinstance(page_ir.metadata, dict):
                p_ids = page_ir.metadata.get("preserved_block_ids", set())
                if isinstance(p_ids, (set, list, tuple)):
                    preserved_ids.update(p_ids)

            # 1. Identify translation candidates
            candidate_blocks: list[TextBlock] = []
            block_translation_map: dict[str, str] = {}
            for block in page_ir.blocks:
                if block.block_type in ("formula", "table_rejected") or block.block_id in preserved_ids:
                    continue
                trans_text = self._resolve_translated_text(block, translated_segments)
                if trans_text and trans_text.strip() and trans_text.strip() != block.text.strip():
                    candidate_blocks.append(block)
                    block_translation_map[block.block_id] = trans_text

            # 2. Pre-compute read-only clearance plan on pristine scratch page
            clearance_plan = self._clearance_planner.plan_page_clearance(
                page_ir=page_ir,
                page=scratch_page,
                candidate_blocks=candidate_blocks,
            )

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
                page_summary.total_blocks += 1
                is_cell = (block.block_type == "table_cell")
                if is_cell:
                    page_summary.total_cells += 1

                # 3. Formula preservation check
                if block.block_type == "formula":
                    page_summary.skipped_blocks += 1
                    page_details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_number,
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

                # 3b. Preserved / Rejected table block check
                if block.block_type == "table_rejected" or block.block_id in preserved_ids:
                    page_summary.skipped_blocks += 1
                    if is_cell:
                        page_summary.skipped_cells += 1
                    page_details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_number,
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

                # 3c. Table cell geometry and stroke-aware insets resolution
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
                        page_summary.skipped_blocks += 1
                        page_summary.skipped_cells += 1
                        page_details.append(
                            BlockFittingDetail(
                                block_id=block.block_id,
                                page_number=page_number,
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
                        page_summary.overflow_blocks += 1
                        page_summary.overflow_cells += 1
                        page_details.append(
                            BlockFittingDetail(
                                block_id=block.block_id,
                                page_number=page_number,
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
                    page_summary.skipped_blocks += 1
                    if is_cell:
                        page_summary.skipped_cells += 1
                    page_details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_number,
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
                    page_summary.skipped_blocks += 1
                    if is_cell:
                        page_summary.skipped_cells += 1
                    page_details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_number,
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

                # 5. Clearance check
                decision = clearance_plan.decisions.get(block.block_id)
                if decision is not None and not decision.is_approved:
                    page_summary.collision_blocks += 1
                    if is_cell:
                        page_summary.collision_cells += 1
                    coll = decision.collision_detail
                    coll_type = coll.collision_type if coll else "UNKNOWN"
                    coll_desc = coll.description if coll else "Geometric collision detected."
                    page_details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_number,
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

                # 7. Precision Binary Search fitting test
                target_layout_box = inner_bbox if is_cell and inner_bbox else block.bbox

                fits, final_font_size, overflow_cause, line_count, effective_lineheight = self._fit_tester.test_fit(
                    rect=target_layout_box,
                    text=translated_text,
                    orig_font_size=orig_font_size,
                    options=self.options,
                )

                if is_cell and inner_bbox:
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
                    page_summary.overflow_blocks += 1
                    if is_cell:
                        page_summary.overflow_cells += 1
                    page_details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_number,
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

            # 8. Apply selective redaction ONLY on approved, fitting candidates
            if fitting_plan:
                for block, tight_line_rects, _, _, _, _, _, _, _, _, _, _ in fitting_plan:
                    for line_rect in tight_line_rects:
                        rect = pymupdf.Rect(*line_rect)
                        scratch_page.add_redact_annot(rect, fill=False, cross_out=False)

                scratch_page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_NONE,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )

                # 9. Insert translated text
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
                    scratch_page.insert_textbox(
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

                    page_summary.replaced_blocks += 1
                    if is_cell:
                        page_summary.replaced_cells += 1

                    page_details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_number,
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

            return PageTransactionResult(
                page_number=page_number,
                source_page_index=source_page_index,
                staging_doc=staging_doc,
                is_fallback=False,
                details=page_details,
                summary=page_summary,
            )
        except Exception:
            try:
                staging_doc.close()
            except Exception:
                pass
            return _build_fallback_result("Unhandled exception during page staging.")

    def typeset(
        self,
        original_pdf: bytes,
        document_ir: DocumentIR,
        translated_segments: dict[str, str],
    ) -> TypesetResult:
        """Render translated segments into a new PDF using page-level transactional staging.

        Args:
            original_pdf: Raw byte buffer of the input PDF document.
            document_ir: Extracted Intermediate Representation containing geometric coordinates.
            translated_segments: Map of segment_id / block_id to translated string content.

        Returns:
            TypesetResult containing the regenerated PDF bytes and fitting telemetry.
        """
        if not original_pdf:
            raise ValueError("original_pdf buffer must not be empty.")

        source_doc = pymupdf.open(stream=original_pdf, filetype="pdf")
        report = FittingReport()
        all_replaced_shrink_ratios: list[float] = []
        output_doc = pymupdf.open()

        for page_ir in document_ir.pages:
            source_page_index = page_ir.page_number - 1
            if source_page_index < 0 or source_page_index >= len(source_doc):
                continue

            tx_result = self.stage_page_transaction(
                source_doc=source_doc,
                page_ir=page_ir,
                document_ir=document_ir,
                translated_segments=translated_segments,
            )

            # Insert committed single page into output document
            output_doc.insert_pdf(tx_result.staging_doc)
            tx_result.staging_doc.close()

            # Aggregate telemetry into FittingReport
            report.total_blocks += tx_result.summary.total_blocks
            report.replaced_blocks += tx_result.summary.replaced_blocks
            report.overflow_blocks += tx_result.summary.overflow_blocks
            report.collision_blocks += tx_result.summary.collision_blocks
            report.skipped_blocks += tx_result.summary.skipped_blocks
            report.transaction_fallback_blocks += tx_result.summary.transaction_fallback_blocks

            report.total_cells += tx_result.summary.total_cells
            report.replaced_cells += tx_result.summary.replaced_cells
            report.overflow_cells += tx_result.summary.overflow_cells
            report.collision_cells += tx_result.summary.collision_cells
            report.skipped_cells += tx_result.summary.skipped_cells
            report.transaction_fallback_cells += tx_result.summary.transaction_fallback_cells

            report.pages.append(tx_result.summary)
            report.details.extend(tx_result.details)

            for d in tx_result.details:
                if d.status == BlockFittingStatus.SUCCESS:
                    shrink_ratio = d.shrink_ratio
                    all_replaced_shrink_ratios.append(shrink_ratio)
                    if shrink_ratio < self.options.severe_shrink_threshold:
                        report.severe_shrink_blocks_count += 1

        if all_replaced_shrink_ratios:
            report.avg_shrink_ratio = sum(all_replaced_shrink_ratios) / len(all_replaced_shrink_ratios)
            report.worst_shrink_ratio = min(all_replaced_shrink_ratios)
        else:
            report.avg_shrink_ratio = 1.0
            report.worst_shrink_ratio = 1.0

        output_bytes = output_doc.tobytes(deflate=True, garbage=3)
        output_doc.close()
        source_doc.close()
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
