"""Deep module typesetting engine for LayoutLingua.

Preserves PDF background graphics, selective text clearance with fill=False,
precision binary search font fitting, dynamic line-height, and multi-tier telemetry.
"""

from __future__ import annotations

import pymupdf

from layoutlingua.core.ir import DocumentIR, PageIR, TextBlock
from layoutlingua.typesetting.accumulator import DocumentAccumulator
from layoutlingua.typesetting.fitting import TextFitTester, parse_color
from layoutlingua.typesetting.fonts import BUILTIN_OR_CJK_FONTS, FontManager
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


def extract_weighted_dominant_color(block: TextBlock) -> tuple[float, float, float]:
    """Extract character-weighted dominant color from a TextBlock's spans.
    Prevents single colored bullet points, icons, or math markers from poisoning
    the entire paragraph's font color.
    """
    if not block.spans:
        return (0.0, 0.0, 0.0)

    color_weights: dict[tuple[float, float, float], int] = {}
    for span in block.spans:
        c = parse_color(span.color)
        text_len = len(span.text.strip()) if span.text else 0
        if text_len == 0:
            text_len = 1
        color_weights[c] = color_weights.get(c, 0) + text_len

    if not color_weights:
        return (0.0, 0.0, 0.0)

    return max(color_weights.items(), key=lambda item: item[1])[0]


def resolve_block_font(base_font: str, block: TextBlock) -> str:
    """Resolve font name for a block, upgrading to bold variant if block spans are majority bold."""
    if not block.spans:
        return base_font
    bold_weight = sum(
        len(s.text.strip())
        for s in block.spans
        if (s.flags & 16) or ("bold" in s.font_name.lower()) or ("black" in s.font_name.lower())
    )
    total_weight = sum(len(s.text.strip()) for s in block.spans) or 1
    is_bold = (bold_weight / total_weight) >= 0.5

    base_lower = base_font.lower()
    if is_bold:
        if base_lower in ("tiro", "times-roman", "times"):
            return "tibo"
        if base_lower in ("helv", "helvetica"):
            return "hebo"
        if base_lower in ("couri", "courier"):
            return "cobo"
    return base_font


def compute_expanded_layout_box(
    block_bbox: tuple[float, float, float, float],
    page_blocks: list[TextBlock],
    page_width: float,
    current_block_id: str,
    margin_padding: float = 40.0,
    page_regions: list[Any] | None = None,
    scratch_page: Any = None,
) -> tuple[float, float, float, float]:
    """Dynamically expand block width into available whitespace in writing direction (BabelDOC algorithm).
    Strictly preserves multi-column layouts and avoids colliding with adjacent figures, drawings, tables, and images.
    """
    x0, y0, x1, y1 = block_bbox
    orig_w = max(10.0, x1 - x0)
    orig_h = max(8.0, y1 - y0)

    # In academic publications and multi-column books (BabelDOC layout preservation):
    # Multi-line paragraphs should not arbitrarily blow up to full page width into neighboring figures.
    # Allow at most 15% horizontal expansion for paragraphs, while single-line titles can use margin whitespace.
    is_multiline_column = (orig_h > 18.0) and (orig_w < page_width * 0.70)
    if is_multiline_column:
        max_allowed_x1 = min(x0 + orig_w * 1.15, page_width - margin_padding)
    else:
        max_allowed_x1 = max(x1, page_width - margin_padding)

    right_limit = max_allowed_x1

    # 1. Collect obstacles from other text blocks
    for other in page_blocks:
        if other.block_id == current_block_id:
            continue
        ox0, oy0, ox1, oy1 = other.bbox
        v_overlap = max(0.0, min(y1, oy1) - max(y0, oy0))
        if v_overlap > 2.0 and ox0 >= x1 - 5.0:
            right_limit = min(right_limit, ox0 - 5.0)

    # 2. Collect obstacles from page regions (figures, tables, images, formulas)
    if page_regions:
        for reg in page_regions:
            cat = getattr(reg, "category", "")
            if cat in ("figure", "image", "table", "formula"):
                r_bbox = getattr(reg, "bbox", None)
                if r_bbox and len(r_bbox) == 4:
                    rx0, ry0, rx1, ry1 = r_bbox
                    v_overlap = max(0.0, min(y1, ry1) - max(y0, ry0))
                    if v_overlap > 2.0 and rx0 >= x0:
                        right_limit = min(right_limit, rx0 - 5.0)

    # 3. Collect obstacles from vector drawings on scratch_page (e.g. geometric diagrams)
    if scratch_page and hasattr(scratch_page, "get_drawings"):
        try:
            for drw in scratch_page.get_drawings():
                dr = drw.get("rect")
                if dr and (dr.width > 12.0 or dr.height > 12.0):
                    v_overlap = max(0.0, min(y1, dr.y1) - max(y0, dr.y0))
                    if v_overlap > 2.0 and dr.x0 >= x0:
                        right_limit = min(right_limit, dr.x0 - 5.0)
        except Exception:
            pass

    # 4. Collect obstacles from raster images on scratch_page
    if scratch_page and hasattr(scratch_page, "get_images"):
        try:
            for img_info in scratch_page.get_images():
                xref = img_info[0]
                for r in scratch_page.get_image_rects(xref):
                    v_overlap = max(0.0, min(y1, r.y1) - max(y0, r.y0))
                    if v_overlap > 2.0 and r.x0 >= x0:
                        right_limit = min(right_limit, r.x0 - 5.0)
        except Exception:
            pass

    expanded_x1 = max(x1, min(max_allowed_x1, right_limit))
    # Never exceed right_limit if right_limit is valid
    if right_limit > x0 + 10.0:
        expanded_x1 = min(expanded_x1, right_limit)

    return (x0, y0, max(x0 + 10.0, expanded_x1), y1)


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
                dominant_color = extract_weighted_dominant_color(block)
                block_font = resolve_block_font(self.options.font_name, block)

                # 7. Precision Binary Search fitting test
                if is_cell and inner_bbox:
                    target_layout_box = inner_bbox
                else:
                    page_w = page_ir.geometry.width if hasattr(page_ir, "geometry") and page_ir.geometry else 595.0
                    target_layout_box = compute_expanded_layout_box(
                        block_bbox=block.bbox,
                        page_blocks=page_ir.blocks,
                        page_width=page_w,
                        current_block_id=block.block_id,
                        margin_padding=self.options.clearance_padding_pt + 30.0,
                        page_regions=getattr(page_ir, "regions", None),
                        scratch_page=scratch_page,
                    )

                fits, final_font_size, overflow_cause, line_count, effective_lineheight = self._fit_tester.test_fit(
                    rect=target_layout_box,
                    text=translated_text,
                    orig_font_size=orig_font_size,
                    options=self.options,
                    font_name=block_font,
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
                        block_font,
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
                for block, tight_line_rects, *rest in fitting_plan:
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
                    block_font,
                ) in fitting_plan:
                    box_h = max(target_layout_box[3] - target_layout_box[1], line_count * final_size * 1.50)
                    rect = pymupdf.Rect(target_layout_box[0], target_layout_box[1], target_layout_box[2], target_layout_box[1] + box_h)
                    fontfile_arg = (
                        None
                        if block_font.lower() in BUILTIN_OR_CJK_FONTS
                        else str(self.font_manager.font_path)
                    )
                    rc = scratch_page.insert_textbox(
                        rect,
                        text,
                        fontsize=final_size,
                        fontname=block_font,
                        fontfile=fontfile_arg,
                        color=color,
                        lineheight=lineheight,
                    )
                    if rc < 0:
                        # Accommodate any remaining PyMuPDF line deficit
                        rect = pymupdf.Rect(target_layout_box[0], target_layout_box[1], target_layout_box[2], target_layout_box[1] + box_h + abs(rc) + 2.0)
                        scratch_page.insert_textbox(
                            rect,
                            text,
                            fontsize=final_size,
                            fontname=block_font,
                            fontfile=fontfile_arg,
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

    def _build_fallback_page_transaction(
        self,
        source_doc: pymupdf.Document,
        page_ir: PageIR,
        source_page_index: int,
        translated_segments: dict[str, str],
        reason: str = "Transaction rollback to pristine source page.",
    ) -> PageTransactionResult:
        """Construct fallback PageTransactionResult with pristine source page copy."""
        fallback_doc = pymupdf.open()
        fallback_doc.insert_pdf(source_doc, from_page=source_page_index, to_page=source_page_index)

        page_number = page_ir.page_number
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
                    translated_text=trans_text if was_candidate else "",
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

    def _commit_page_telemetry(
        self,
        report: FittingReport,
        tx_result: PageTransactionResult,
        all_replaced_shrink_ratios: list[float],
    ) -> None:
        """Record successful page transaction metrics into FittingReport."""
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

    def _commit_emergency_fallback_telemetry(
        self,
        report: FittingReport,
        page_ir: PageIR,
        page_number: int,
        translated_segments: dict[str, str],
    ) -> None:
        """Record fallback telemetry for a page whose output insertion failed."""
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
                    translated_text=trans_text if was_candidate else "",
                    original_font_size=10.0,
                    final_font_size=10.0,
                    shrink_ratio=1.0,
                    bbox=block.bbox,
                    unit_kind="CELL" if is_cell else "BLOCK",
                    reason="Commit phase failure: rolled back to pristine source page.",
                )
            )

        report.total_blocks += summary.total_blocks
        report.skipped_blocks += summary.skipped_blocks
        report.transaction_fallback_blocks += summary.transaction_fallback_blocks
        report.total_cells += summary.total_cells
        report.skipped_cells += summary.skipped_cells
        report.transaction_fallback_cells += summary.transaction_fallback_cells

        report.pages.append(summary)
        report.details.extend(details)

    def typeset(
        self,
        original_pdf: bytes,
        document_ir: DocumentIR,
        translated_segments: dict[str, str],
    ) -> TypesetResult:
        """Render translated segments into a new PDF using multi-page accumulation with atomic commit gates.

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

        accumulator = DocumentAccumulator(source_doc=source_doc)
        pages_by_number: dict[int, PageIR] = {p.page_number: p for p in document_ir.pages}

        try:
            for p in range(len(source_doc)):
                page_number = p + 1
                page_ir = pages_by_number.get(page_number)

                if page_ir is None:
                    accumulator.commit_pristine_source_page(p)
                    continue

                try:
                    tx_result = self.stage_page_transaction(
                        source_doc=source_doc,
                        page_ir=page_ir,
                        document_ir=document_ir,
                        translated_segments=translated_segments,
                    )
                except Exception:
                    tx_result = self._build_fallback_page_transaction(
                        source_doc=source_doc,
                        page_ir=page_ir,
                        source_page_index=p,
                        translated_segments=translated_segments,
                        reason="Catastrophic exception during page staging; emergency source fallback.",
                    )

                committed_cleanly = accumulator.commit_page(tx_result)

                # Telemetry Commit Gate: only record tx_result metrics if commit cleanly succeeded
                if committed_cleanly:
                    self._commit_page_telemetry(report, tx_result, all_replaced_shrink_ratios)
                else:
                    self._commit_emergency_fallback_telemetry(
                        report=report,
                        page_ir=page_ir,
                        page_number=page_number,
                        translated_segments=translated_segments,
                    )

            if all_replaced_shrink_ratios:
                report.avg_shrink_ratio = sum(all_replaced_shrink_ratios) / len(all_replaced_shrink_ratios)
                report.worst_shrink_ratio = min(all_replaced_shrink_ratios)
            else:
                report.avg_shrink_ratio = 1.0
                report.worst_shrink_ratio = 1.0

            output_bytes = accumulator.finish(report=report)
            return TypesetResult(pdf_bytes=output_bytes, fitting_report=report)
        finally:
            accumulator.close()
            source_doc.close()

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
