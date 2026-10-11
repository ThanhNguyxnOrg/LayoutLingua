"""Deep module typesetting engine for LayoutLingua.

Preserves PDF background graphics, selective text clearance with fill=False,
adaptive font fitting, and fail-closed overflow handling.
"""

from __future__ import annotations

import pymupdf

from layoutlingua.core.ir import DocumentIR, TextBlock
from layoutlingua.typesetting.fitting import TextFitTester, parse_color
from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.models import (
    BlockFittingDetail,
    BlockFittingStatus,
    FittingReport,
    TypesetOptions,
    TypesetResult,
)


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

        for page_ir in document_ir.pages:
            page_idx = page_ir.page_number - 1
            if page_idx >= len(doc):
                continue

            page = doc[page_idx]
            self.font_manager.register_on_page(page, font_name=self.options.font_name)

            fitting_plan: list[tuple[TextBlock, str, float, tuple[float, float, float], float]] = []

            for block in page_ir.blocks:
                report.total_blocks += 1

                # 1. Formula preservation check
                if block.block_type == "formula":
                    report.skipped_blocks += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SKIPPED_FORMULA,
                            original_text=block.text,
                            translated_text="",
                            original_font_size=10.0,
                            final_font_size=10.0,
                            bbox=block.bbox,
                            reason="Formula block preserved intact without translation mutation.",
                        )
                    )
                    continue

                # 2. Extract translation candidate
                translated_text = self._resolve_translated_text(block, translated_segments)
                if not translated_text or not translated_text.strip():
                    report.skipped_blocks += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SKIPPED_EMPTY,
                            original_text=block.text,
                            translated_text="",
                            original_font_size=10.0,
                            final_font_size=10.0,
                            bbox=block.bbox,
                            reason="No translation provided or text is whitespace.",
                        )
                    )
                    continue

                if translated_text.strip() == block.text.strip():
                    report.skipped_blocks += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SKIPPED_UNCHANGED,
                            original_text=block.text,
                            translated_text=translated_text,
                            original_font_size=10.0,
                            final_font_size=10.0,
                            bbox=block.bbox,
                            reason="Translated text is identical to source text.",
                        )
                    )
                    continue

                # 3. Determine metrics and color
                orig_font_size = max((s.font_size for s in block.spans), default=10.0)
                dominant_color = (
                    parse_color(block.spans[0].color) if block.spans else (0.0, 0.0, 0.0)
                )

                # 4. Dry-run fitting test with adaptive shrinkage
                fits, final_font_size = self._fit_tester.test_fit(
                    rect=block.bbox,
                    text=translated_text,
                    orig_font_size=orig_font_size,
                    options=self.options,
                )

                if fits:
                    fitting_plan.append((block, translated_text, orig_font_size, dominant_color, final_font_size))
                else:
                    # Overflow event: fail-closed preserves source text
                    report.overflow_blocks += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.OVERFLOW_FALLBACK,
                            original_text=block.text,
                            translated_text=translated_text,
                            original_font_size=orig_font_size,
                            final_font_size=orig_font_size,
                            bbox=block.bbox,
                            reason=(
                                f"Translated text exceeded bounding box capacity even at "
                                f"minimum scale ({self.options.min_font_scale:.0%}). Source retained."
                            ),
                        )
                    )

            # 5. Apply selective redaction ONLY to approved fitting candidates
            if fitting_plan:
                for block, _, _, _, _ in fitting_plan:
                    rect = pymupdf.Rect(*block.bbox)
                    page.add_redact_annot(rect, fill=False, cross_out=False)

                page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_NONE,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )

                # 6. Insert translated text into cleared bounds
                for block, text, orig_size, color, final_size in fitting_plan:
                    rect = pymupdf.Rect(*block.bbox)
                    page.insert_textbox(
                        rect,
                        text,
                        fontsize=final_size,
                        fontname=self.options.font_name,
                        fontfile=str(self.font_manager.font_path),
                        color=color,
                    )
                    report.replaced_blocks += 1
                    report.details.append(
                        BlockFittingDetail(
                            block_id=block.block_id,
                            page_number=page_ir.page_number,
                            status=BlockFittingStatus.SUCCESS,
                            original_text=block.text,
                            translated_text=text,
                            original_font_size=orig_size,
                            final_font_size=final_size,
                            bbox=block.bbox,
                            reason="Fitted and typeset successfully.",
                        )
                    )

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
