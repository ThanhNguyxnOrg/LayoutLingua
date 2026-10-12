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

            # Structure: (block, tight_line_rects, translated_text, orig_font_size, dominant_color, final_font_size, lineheight, line_count)
            fitting_plan: list[
                tuple[TextBlock, list[tuple[float, float, float, float]], str, float, tuple[float, float, float], float, float, int]
            ] = []

            for block in page_ir.blocks:
                report.total_blocks += 1
                page_summary.total_blocks += 1

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
                            reason="Preserved source text: constituent block of rejected table.",
                        )
                    )
                    continue

                # 4. Extract translation candidate
                translated_text = self._resolve_translated_text(block, translated_segments)
                if not translated_text or not translated_text.strip():
                    report.skipped_blocks += 1
                    page_summary.skipped_blocks += 1
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
                            reason="No translation provided or text is whitespace.",
                        )
                    )
                    continue

                if translated_text.strip() == block.text.strip():
                    report.skipped_blocks += 1
                    page_summary.skipped_blocks += 1
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
                            reason="Translated text is identical to source text.",
                        )
                    )
                    continue

                # 5. Clearance check: verify safety from pre-computed clearance plan
                decision = clearance_plan.decisions.get(block.block_id)
                if decision is not None and not decision.is_approved:
                    report.collision_blocks += 1
                    page_summary.collision_blocks += 1
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
                fits, final_font_size, overflow_cause, line_count, effective_lineheight = self._fit_tester.test_fit(
                    rect=block.bbox,
                    text=translated_text,
                    orig_font_size=orig_font_size,
                    options=self.options,
                )

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
                    ))
                else:
                    # Overflow event: fail-closed preserves source text
                    report.overflow_blocks += 1
                    page_summary.overflow_blocks += 1
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
                            bbox=block.bbox,
                            overflow_cause=overflow_cause,
                            reason=(
                                f"Translated text overflowed bounding box ({overflow_cause.value}) "
                                f"at minimum scale ({self.options.min_font_scale:.0%}). Source retained."
                            ),
                        )
                    )

            # 8. Apply selective redaction ONLY to approved, fitting candidates using tight line rects
            if fitting_plan:
                for block, tight_line_rects, _, _, _, _, _, _ in fitting_plan:
                    for line_rect in tight_line_rects:
                        rect = pymupdf.Rect(*line_rect)
                        page.add_redact_annot(rect, fill=False, cross_out=False)

                page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_NONE,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )

                # 9. Insert translated text using identical effective line-height
                for block, _, text, orig_size, color, final_size, lineheight, line_count in fitting_plan:
                    rect = pymupdf.Rect(*block.bbox)
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
                            bbox=block.bbox,
                            overflow_cause=OverflowCause.NONE,
                            reason="Fitted and typeset successfully via binary search.",
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
