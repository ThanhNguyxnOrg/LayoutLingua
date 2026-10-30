"""Deep module typesetting engine for LayoutLingua.

Preserves PDF background graphics, selective text clearance with fill=False,
precision binary search font fitting, dynamic line-height, and multi-tier telemetry.
"""

from __future__ import annotations

import math
import re
from typing import Any

import pymupdf

from layoutlingua.core.ir import DocumentIR, PageIR, TextBlock
from layoutlingua.typesetting.accumulator import DocumentAccumulator
from layoutlingua.typesetting.fitting import TextFitTester, parse_color
from layoutlingua.typesetting.fonts import BUILTIN_OR_CJK_FONTS, CJK_EMBED_FONTS, FontManager
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


_CJK_CHAR_RE = __import__("re").compile(r"[\u2E80-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF\uFF00-\uFFEF]")


def resolve_block_font(
    base_font: str,
    block: TextBlock,
    translated_text: str = "",
    font_manager: FontManager | None = None,
) -> str:
    """Resolve font name for a block, preserving serif/sans/mono, bold/italic, and CJK target scripts."""
    if translated_text and _CJK_CHAR_RE.search(translated_text):
        if any(0x3040 <= ord(c) <= 0x30FF for c in translated_text):
            return "cjk-jp"
        if any(0xAC00 <= ord(c) <= 0xD7AF for c in translated_text):
            return "cjk-kr"
        return "cjk-sim"

    if not block.spans:
        return base_font

    total_weight = sum(len(s.text.strip()) for s in block.spans) or 1
    bold_weight = sum(
        len(s.text.strip())
        for s in block.spans
        if (s.flags & 16) or ("bold" in s.font_name.lower()) or ("black" in s.font_name.lower()) or ("tibo" in s.font_name.lower()) or ("hebo" in s.font_name.lower())
    )
    italic_weight = sum(
        len(s.text.strip())
        for s in block.spans
        if (s.flags & 2) or ("italic" in s.font_name.lower()) or ("oblique" in s.font_name.lower()) or ("tiit" in s.font_name.lower())
    )
    _sans_vni_keys = ("helve", "aptima", "avanti", "swiss", "avo", "futura", "arial", "sans", "calibri", "tahoma", "verdana")
    serif_weight = sum(
        len(s.text.strip())
        for s in block.spans
        if (s.flags & 4)
        or any(
            k in s.font_name.lower()
            for k in ("times", "serif", "cambria", "georgia", "book", "centur", "palatin", "garamond", "minion", "tiro", "tibo", "tiit", "roman", "cmr", "lmr")
        )
        or ("vni" in s.font_name.lower() and not any(sk in s.font_name.lower() for sk in _sans_vni_keys))
    )
    mono_weight = sum(
        len(s.text.strip())
        for s in block.spans
        if (s.flags & 8) or any(k in s.font_name.lower() for k in ("courier", "mono", "consolas", "couri"))
    )

    is_bold = (bold_weight / total_weight) >= 0.5
    is_italic = (italic_weight / total_weight) >= 0.5
    is_serif = (serif_weight / total_weight) >= 0.5
    is_mono = (mono_weight / total_weight) >= 0.5

    if font_manager is not None and "dejavu" in base_font.lower():
        cand = font_manager.select_font_variant(
            serif=is_serif,
            bold=is_bold,
            italic=is_italic,
            mono=is_mono,
        )
        if translated_text:
            try:
                font_obj = font_manager.get_font(cand)
                if all(font_obj.has_glyph(ord(ch)) > 0 for ch in translated_text if ord(ch) > 127):
                    return cand
                # If italic variant lacks a mathematical symbol, try regular serif/sans before falling back
                if is_italic:
                    cand_upright = font_manager.select_font_variant(
                        serif=is_serif,
                        bold=is_bold,
                        italic=False,
                        mono=is_mono,
                    )
                    font_up = font_manager.get_font(cand_upright)
                    if all(font_up.has_glyph(ord(ch)) > 0 for ch in translated_text if ord(ch) > 127):
                        return cand_upright
                dv_fallback = (
                    f"DejaVuSerif{'-Bold' if is_bold else ''}"
                    if is_serif
                    else f"DejaVuSans{'-Bold' if is_bold else ''}"
                )
                font_dv = font_manager.get_font(dv_fallback)
                if all(font_dv.has_glyph(ord(ch)) > 0 for ch in translated_text if ord(ch) > 127):
                    return dv_fallback
            except Exception:
                pass
        else:
            return cand

    base_lower = base_font.lower()
    if is_bold:
        if base_lower in ("tiro", "times-roman", "times"):
            return "tibo"
        if base_lower in ("helv", "helvetica"):
            return "hebo"
        if base_lower in ("couri", "courier"):
            return "cobo"
        if "dejavu" in base_lower:
            return "DejaVuSans-Bold"
        return f"{base_font}-Bold"
    return base_font


def compute_expanded_layout_box(
    block_bbox: tuple[float, float, float, float],
    page_blocks: list[TextBlock],
    page_width: float,
    current_block_id: str,
    margin_padding: float = 40.0,
    page_regions: list[Any] | None = None,
    scratch_page: Any = None,
    orig_font_size: float = 10.0,
) -> tuple[float, float, float, float]:
    """Dynamically expand block width into available whitespace in writing direction (BabelDOC algorithm).
    Strictly preserves multi-column layouts and avoids colliding with adjacent figures, drawings, tables, and images.
    """
    x0, y0, x1, y1 = block_bbox
    orig_w = max(10.0, x1 - x0)
    orig_h = max(8.0, y1 - y0)

    # In academic publications and multi-column books (BabelDOC layout preservation):
    # Multi-line paragraphs should not arbitrarily blow up to full page width into neighboring figures.
    # Display headings/titles (orig_font_size >= 16pt) are not multi-column body paragraphs and may expand into open margins.
    is_display_heading = orig_font_size >= 16.0
    is_multiline_column = (orig_h > 42.0) and (orig_w < page_width * 0.70) and not is_display_heading
    if is_multiline_column:
        max_allowed_x1 = min(x0 + orig_w * 1.18, page_width - margin_padding)
    else:
        max_allowed_x1 = max(x1, page_width - margin_padding)

    right_limit = max_allowed_x1

    # 1. Collect obstacles from other text blocks
    above_right_x0s: list[float] = []
    below_right_x0s: list[float] = []
    for other in page_blocks:
        if other.block_id == current_block_id:
            continue
        ox0, oy0, ox1, oy1 = other.bbox
        v_overlap = max(0.0, min(y1, oy1) - max(y0, oy0))
        if v_overlap > 2.0 and ox0 >= x1 - 5.0:
            if orig_h <= 26.0 and 0.0 <= (ox0 - x1) < 8.0:
                gap_pad = min(2.0, max(0.6, (ox0 - x1) * 0.20))
            else:
                gap_pad = min(3.5, max(1.0, (ox0 - x1) * 0.30)) if ox0 >= x1 else 1.0
            right_limit = min(right_limit, max(x1, ox0 - gap_pad))
        elif orig_h <= 26.0 and ox0 >= x1 + 4.0:
            is_f = getattr(other, "block_type", "text") == "formula"
            max_v_gap = 3.5 if is_f else 16.0
            if 0.0 <= (y0 - oy1) <= max_v_gap:
                above_right_x0s.append((ox0, is_f))
            elif 0.0 <= (oy0 - y1) <= max_v_gap:
                below_right_x0s.append((ox0, is_f))

    # Only treat non-overlapping neighbors as a right column boundary when a continuous
    # vertical column exists BOTH above and below this row at the same horizontal offset.
    if orig_h <= 26.0 and above_right_x0s and below_right_x0s:
        for ax0, a_f in above_right_x0s:
            for bx0, b_f in below_right_x0s:
                tol_x = 2.5 if (a_f or b_f) else 10.0
                if abs(ax0 - bx0) <= tol_x:
                    right_limit = min(right_limit, max(ax0, bx0) - 4.0)

    # 2. Collect obstacles from page regions (figures, tables, images, formulas)
    if page_regions:
        for reg in page_regions:
            cat = getattr(reg, "category", "")
            if cat in ("figure", "image", "table", "formula"):
                r_bbox = getattr(reg, "bbox", None)
                if r_bbox and len(r_bbox) == 4:
                    rx0, ry0, rx1, ry1 = r_bbox
                    v_overlap = max(0.0, min(y1, ry1) - max(y0, ry0))
                    if v_overlap > 2.0 and rx0 >= x1 - 5.0:
                        gap_pad = min(3.5, max(1.0, (rx0 - x1) * 0.30)) if rx0 >= x1 else 1.0
                        right_limit = min(right_limit, max(x1, rx0 - gap_pad))

    # 3. Collect obstacles & symmetric container bounds from vector drawings on scratch_page
    if scratch_page and hasattr(scratch_page, "get_drawings"):
        try:
            for drw in scratch_page.get_drawings():
                dr = drw.get("rect")
                if dr and (dr.width > 12.0 or dr.height > 12.0):
                    d_fill = drw.get("fill")
                    if (
                        drw.get("type") == "f"
                        and drw.get("color") is None
                        and dr.width >= 6.0
                        and 8.0 <= dr.height <= 24.0
                        and isinstance(d_fill, (tuple, list))
                        and len(d_fill) >= 3
                        and min(float(c) for c in d_fill[:3]) >= 0.70
                    ):
                        continue
                    # If the drawing is an enclosing container box around this text block (e.g. cover panel or callout box),
                    # preserve symmetric inner padding relative to the container's right border.
                    if dr.x0 <= x0 + 2.5 and dr.x1 >= x1 - 2.5 and dr.y0 <= y0 + 2.5 and dr.y1 >= y1 - 2.5:
                        left_inner_pad = max(0.0, x0 - dr.x0)
                        if 8.0 <= left_inner_pad <= 60.0 and dr.width > page_width * 0.45:
                            right_inner_pad = min(28.0, max(18.0, left_inner_pad * 1.25))
                            right_limit = min(right_limit, max(x1, dr.x1 - right_inner_pad))
                        else:
                            right_limit = min(right_limit, max(x1, dr.x1 - 1.0))
                        continue
                    # Ignore full-page decorative frames that span >80% of page width
                    if dr.width > page_width * 0.80 and dr.x0 < margin_padding:
                        continue
                    v_overlap = max(0.0, min(y1, dr.y1) - max(y0, dr.y0))
                    if v_overlap > 2.0 and dr.x0 >= x1 - 5.0:
                        right_limit = min(right_limit, dr.x0 - 3.5)
        except Exception:
            pass

    # 4. Collect obstacles from raster images on scratch_page
    if scratch_page and hasattr(scratch_page, "get_images"):
        try:
            for img_info in scratch_page.get_images():
                xref = img_info[0]
                for r in scratch_page.get_image_rects(xref):
                    v_overlap = max(0.0, min(y1, r.y1) - max(y0, r.y0))
                    if v_overlap > 2.0 and r.x0 >= x1 - 5.0:
                        right_limit = min(right_limit, r.x0 - 3.5)
        except Exception:
            pass

    # Never contract below original block width (x1)
    expanded_x1 = max(x1, min(max_allowed_x1, max(x1, right_limit)))

    # 4b. Leftward expansion into unobstructed whitespace when a short single-line label
    # is blocked on the right by an immediate obstacle
    expanded_x0 = x0
    page_left_margin = min(
        (b.bbox[0] for b in page_blocks if (b.bbox[2] - b.bbox[0]) > 2.0),
        default=margin_padding,
    )
    effective_left_margin = max(margin_padding, page_left_margin)
    is_narrow_stacked_label = (
        orig_h <= orig_font_size * 3.6
        and (expanded_x1 - x0) < max(48.0, orig_font_size * 4.5)
    )
    if (
        (orig_h <= min(26.0, orig_font_size * 1.75) or is_narrow_stacked_label)
        and right_limit < x1 + 15.0
        and (expanded_x1 - x0) < 135.0
        and x0 > effective_left_margin + 4.0
    ):
        left_limit = max(effective_left_margin, x0 - 32.0)
        for other in page_blocks:
            if other.block_id == current_block_id:
                continue
            ox0, oy0, ox1, oy1 = other.bbox
            v_overlap = max(0.0, min(y1, oy1) - max(y0, oy0))
            if v_overlap > 2.0 and ox1 <= x0 + 2.0:
                gap_pad = min(2.0, max(0.6, (x0 - ox1) * 0.20)) if 0.0 <= (x0 - ox1) < 8.0 else 3.5
                left_limit = max(left_limit, ox1 + gap_pad)
        if scratch_page and hasattr(scratch_page, "get_drawings"):
            try:
                for drw in scratch_page.get_drawings():
                    dr = drw.get("rect")
                    if dr and dr.height > 10.0:
                        v_overlap = max(0.0, min(y1, dr.y1) - max(y0, dr.y0))
                        if v_overlap > 2.0:
                            if dr.x0 <= x0 + 1.0 and dr.x1 >= x1 - 1.0:
                                left_limit = max(left_limit, dr.x0 + 1.5)
                            elif dr.x1 <= x0 + 1.5:
                                left_limit = max(left_limit, dr.x1 + 2.0)
            except Exception:
                pass
        expanded_x0 = min(x0, left_limit)

    return (expanded_x0, y0, max(expanded_x0 + 10.0, expanded_x1), y1)


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

    # ------------------------------------------------------------------
    # TS-parity token flow: keep original math glyphs frozen in place,
    # redact only prose gaps, and draw translated prose chunks into them.
    # ------------------------------------------------------------------

    @staticmethod
    def _split_restored_by_tokens(translated_text: str, tokens: list) -> tuple[list[str], bool]:
        """Split the restored translated string into prose chunks around each token's raw content."""
        import re as _re

        chunks: list[str] = []
        cursor = 0
        for token in tokens:
            raw = token.raw_content.strip()
            if not raw:
                continue
            left_b = r"(?<![^\W_])" if raw[0].isalnum() else ""
            right_b = r"(?![^\W_])" if raw[-1].isalnum() else ""
            pat = _re.compile(f"{left_b}{_re.escape(raw)}{right_b}")
            m = pat.search(translated_text, cursor)
            if m is None:
                return [], False
            chunks.append(translated_text[cursor : m.start()])
            cursor = m.end()
        chunks.append(translated_text[cursor:])
        return chunks, True

    @staticmethod
    def _assign_tokens_to_lines(tokens: list, line_rects: list) -> dict[int, list]:
        """Assign each formula token to the line rect containing its vertical center."""
        assignment: dict[int, list] = {}
        for li, rect in enumerate(line_rects):
            ry0, ry1 = rect[1], rect[3]
            for token in tokens:
                tx0, ty0, tx1, ty1 = token.bbox
                cy = (ty0 + ty1) / 2.0
                if ry0 - 1.0 <= cy <= ry1 + 1.0:
                    assignment.setdefault(li, []).append(token)
        return assignment

    def _plan_token_flow(
        self,
        block: TextBlock,
        tokens: list,
        translated_text: str,
        line_rects: list,
        block_font: str,
        orig_font_size: float,
        max_right_x: float | None = None,
    ) -> list[tuple[pymupdf.Rect, str, float]] | None:
        """Plan prose chunks drawn into the gaps around frozen formula tokens.

        Returns a list of (rect, chunk_text, font_size) draw specs, or None when the
        flow cannot be honored (caller falls back to the legacy full-redact path).
        """
        if len(line_rects) != 1:
            return None

        chunks, ok = self._split_restored_by_tokens(translated_text, tokens)
        if not ok:
            return None

        assignment = self._assign_tokens_to_lines(tokens, line_rects)

        # Gap sequence in reading order: build 1-to-1 slots (len(tokens) + 1) matching chunks
        all_tokens_sorted = sorted(assignment.get(0, []), key=lambda t: t.bbox[0])
        if len(all_tokens_sorted) != len(tokens) or len(chunks) != len(all_tokens_sorted) + 1:
            return None

        raw_probe = block.text
        orig_slots: list[str] = []
        for tok in all_tokens_sorted:
            idx_tok = raw_probe.find(tok.raw_content)
            if idx_tok >= 0:
                orig_slots.append(raw_probe[:idx_tok].strip())
                raw_probe = raw_probe[idx_tok + len(tok.raw_content):]
            else:
                orig_slots.append("")
        orig_slots.append(raw_probe.strip())

        # If target-language word-order inversion (e.g. SOV in Japanese) moved prose across a frozen
        # token so a previously populated slot became empty or vice-versa, abort token flow and render
        # as a unified line so chunks are never drawn into the wrong slot.
        for o_chunk, t_chunk in zip(orig_slots, chunks):
            if bool(o_chunk) != bool(t_chunk.strip()):
                return None

        slot_gaps: list[tuple[pymupdf.Rect | None, bool]] = []
        for li, rect in enumerate(line_rects):
            line_tokens = sorted(assignment.get(li, []), key=lambda t: t.bbox[0])
            cursor_x = rect[0]
            for token in line_tokens:
                tx0, _, tx1, _ = token.bbox
                left = max(cursor_x, rect[0])
                right = min(tx0 - 0.6, rect[2])
                if right - left > 2.0:
                    slot_gaps.append((pymupdf.Rect(left, rect[1], right, rect[3]), False))
                else:
                    slot_gaps.append((None, False))
                cursor_x = max(cursor_x, tx1 + 0.6)
            tail_right = max(rect[2], max_right_x) if (max_right_x and li == len(line_rects) - 1) else rect[2]
            if tail_right - cursor_x > 2.0:
                slot_gaps.append((pymupdf.Rect(cursor_x, rect[1], tail_right, rect[3]), True))
            else:
                slot_gaps.append((None, True))

        if len(slot_gaps) != len(chunks):
            return None

        font = self.font_manager.get_font(block_font)
        eff_min_scale = min(self.options.min_font_scale, 0.50)
        specs: list[tuple[pymupdf.Rect, str, float]] = []
        for idx_c, chunk in enumerate(chunks):
            text = chunk.strip()
            gap, is_tail = slot_gaps[idx_c]
            if not text:
                if gap is not None:
                    specs.append((gap, "", orig_font_size))
                continue
            if gap is None or gap.width <= 4.0:
                return None

            gap_w = max(8.0, gap.width - (1.0 if is_tail else 2.0))
            size = orig_font_size
            while size > orig_font_size * eff_min_scale:
                # Allow gentle horizontal condensation (down to 0.78x) before reducing vertical font size
                if font.text_length(text, fontsize=size) <= gap_w * 1.28:
                    break
                size -= 0.25
            # Allow horizontal condensation up to 1.38x capacity on tight inline slots
            if font.text_length(text, fontsize=size) > gap_w * 1.38:
                return None
            specs.append((gap, text, max(self.options.min_font_pt, size)))

        # Harmonize font size across all non-empty chunks on the same token-flow line
        non_empty_sizes = [sz for _, txt, sz in specs if txt]
        if len(non_empty_sizes) >= 2:
            uniform_sz = max(min(non_empty_sizes), max(non_empty_sizes) * 0.90)
            specs = [
                (
                    g,
                    t,
                    uniform_sz
                    if (t and font.text_length(t, fontsize=uniform_sz) <= max(8.0, g.width - 1.0) * 1.38)
                    else sz,
                )
                for g, t, sz in specs
            ]

        return specs

    def _insert_text_with_cjk_fallback(
        self,
        page: Any,
        pt: pymupdf.Point,
        text: str,
        fontsize: float,
        block_font: str,
        fontfile_arg: str | None,
        color: tuple[float, float, float],
        tz_factor: float = 1.0,
    ) -> None:
        """Render a single-line string, falling back to FreeSerif for characters missing in CJK fonts (such as Unicode subscripts/superscripts ₙ, ₀, ₁, ₂)."""
        if block_font.lower() not in CJK_EMBED_FONTS:
            morph = (pt, pymupdf.Matrix(tz_factor, 1.0)) if tz_factor < 0.995 else None
            page.insert_text(
                pt,
                text,
                fontsize=fontsize,
                fontname=block_font,
                fontfile=fontfile_arg,
                color=color,
                morph=morph,
            )
            return

        cjk_font = self.font_manager.get_font(block_font)
        fallback_font_name = self.options.font_name
        fallback_font = self.font_manager.get_font(fallback_font_name)
        fallback_file = str(self.font_manager.get_font_path(fallback_font_name))
        self.font_manager.register_on_page(page, font_name=fallback_font_name)

        runs: list[tuple[bool, str]] = []
        for ch in text:
            use_fb = (not ch.isspace()) and (0x2070 <= ord(ch) <= 0x209F or cjk_font.has_glyph(ord(ch)) == 0)
            if runs and runs[-1][0] == use_fb:
                runs[-1] = (use_fb, runs[-1][1] + ch)
            else:
                runs.append((use_fb, ch))

        if len(runs) <= 1 and not (runs and runs[0][0]):
            morph = (pt, pymupdf.Matrix(tz_factor, 1.0)) if tz_factor < 0.995 else None
            page.insert_text(
                pt,
                text,
                fontsize=fontsize,
                fontname=block_font,
                fontfile=fontfile_arg,
                color=color,
                morph=morph,
            )
            return

        cur_x = float(pt.x)
        base_y = float(pt.y)
        for use_fb, run_str in runs:
            fn = fallback_font_name if use_fb else block_font
            ff = fallback_file if use_fb else fontfile_arg
            f_obj = fallback_font if use_fb else cjk_font
            r_pt = pymupdf.Point(cur_x, base_y)
            r_morph = (r_pt, pymupdf.Matrix(tz_factor, 1.0)) if tz_factor < 0.995 else None
            page.insert_text(
                r_pt,
                run_str,
                fontsize=fontsize,
                fontname=fn,
                fontfile=ff,
                color=color,
                morph=r_morph,
            )
            cur_x += f_obj.text_length(run_str, fontsize=fontsize) * tz_factor


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
            self.font_manager.register_on_page(scratch_page, font_name=f"{self.options.font_name}-Bold")

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

            # Foreign-language block safeguard (in case PageIR came from an older cached session)
            vn_diacritics = set("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
            page_has_vn = any(
                any(ch.lower() in vn_diacritics for ch in b.text)
                for b in page_ir.blocks
                if b.block_type == "text"
            )
            if page_has_vn:
                import re as _re
                from layoutlingua.processing.text_sanitizer import detect_language_from_text

                for b in page_ir.blocks:
                    if b.block_type == "text" and b.block_id not in preserved_ids:
                        b_txt = b.text.strip()
                        alpha_words = [w for w in _re.findall(r"[a-zA-ZÀ-ỹ]+", b_txt) if len(w) >= 2]
                        en_stop_hits = len(
                            _re.findall(
                                r"\b(?:the|of|and|in|to|is|for|that|with|on|as|are|this|by|be|at|or|from|an|which)\b",
                                b_txt,
                                _re.IGNORECASE,
                            )
                        )
                        if (
                            len(alpha_words) >= 5
                            and en_stop_hits >= 2
                            and not any(ch.lower() in vn_diacritics for ch in b_txt)
                            and detect_language_from_text(b_txt) == "en"
                        ):
                            preserved_ids.add(b.block_id)

            # 1. Identify translation candidates (+ formula tokens for the TS-parity token flow)
            candidate_blocks: list[TextBlock] = []
            block_translation_map: dict[str, str] = {}
            token_map: dict[str, list] = {}
            for block in page_ir.blocks:
                if block.block_type in ("formula", "table_rejected") or block.block_id in preserved_ids:
                    continue
                if not block.text.strip():
                    continue
                trans_text = self._resolve_translated_text(block, translated_segments)
                if trans_text and trans_text.strip() and trans_text.strip() != block.text.strip():
                    candidate_blocks.append(block)
                    block_translation_map[block.block_id] = trans_text
                    try:
                        from layoutlingua.processing.formula.isolator import FormulaIsolator as _FI

                        token_map[block.block_id] = _FI().isolate_block(block).tokens
                    except Exception:
                        token_map[block.block_id] = []

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
                    str,
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

                # Preserve uppercase heading casing (e.g. "V. LƯỢNG GIÁC" -> "V. TRIGONOMETRY")
                source_clean = block.text.strip()
                source_letters = "".join(c for c in source_clean if c.isalpha())
                if source_letters and source_letters.isupper() and len(source_letters) >= 2:
                    translated_text = translated_text.upper()

                from layoutlingua.typesetting.fitting import TOC_LEADER_PATTERN

                if translated_text.strip() == block.text.strip() and not TOC_LEADER_PATTERN.match(block.text.strip()):
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
                orig_font_size = max(
                    (s.font_size for s in block.spans if s.text and s.text.strip()),
                    default=max((s.font_size for s in block.spans), default=10.0),
                )
                dominant_color = extract_weighted_dominant_color(block)
                block_font = resolve_block_font(
                    self.options.font_name,
                    block,
                    translated_text=translated_text,
                    font_manager=self.font_manager,
                )

                # 7. Precision Binary Search fitting test
                if is_cell and inner_bbox:
                    target_layout_box = inner_bbox
                else:
                    page_w = page_ir.geometry.width if hasattr(page_ir, "geometry") and page_ir.geometry else 595.0
                    eff_margin_pad = max(16.0, min(self.options.clearance_padding_pt + 22.0, page_w * 0.042))
                    target_layout_box = compute_expanded_layout_box(
                        block_bbox=block.bbox,
                        page_blocks=page_ir.blocks,
                        page_width=page_w,
                        current_block_id=block.block_id,
                        margin_padding=eff_margin_pad,
                        page_regions=getattr(page_ir, "regions", None),
                        scratch_page=scratch_page,
                        orig_font_size=orig_font_size,
                    )

                orig_box_h = block.bbox[3] - block.bbox[1]
                # Preserve original column measure for multi-line blocks if the translation already
                # fits within the original horizontal width at >=95% font scale, preventing 2-line
                # headings/subtitles from flattening into a single wide page-spanning line.
                if (
                    not is_cell
                    and orig_box_h >= orig_font_size * 2.0
                    and target_layout_box[2] > block.bbox[2] + 8.0
                ):
                    orig_measure_box = (
                        target_layout_box[0],
                        target_layout_box[1],
                        min(target_layout_box[2], block.bbox[2] + 6.0),
                        target_layout_box[3],
                    )
                    m_fits, m_size, m_cause, m_lines, m_lh = self._fit_tester.test_fit(
                        rect=orig_measure_box,
                        text=translated_text,
                        orig_font_size=orig_font_size,
                        options=self.options,
                        font_name=block_font,
                    )
                    if m_fits and m_size >= orig_font_size * 0.95:
                        target_layout_box = orig_measure_box
                        target_w = max(10.0, target_layout_box[2] - target_layout_box[0])
                        fits, final_font_size, overflow_cause, line_count, effective_lineheight = (
                            m_fits,
                            m_size,
                            m_cause,
                            m_lines,
                            m_lh,
                        )
                    else:
                        target_w = max(10.0, target_layout_box[2] - target_layout_box[0])
                        fits, final_font_size, overflow_cause, line_count, effective_lineheight = self._fit_tester.test_fit(
                            rect=target_layout_box,
                            text=translated_text,
                            orig_font_size=orig_font_size,
                            options=self.options,
                            font_name=block_font,
                        )
                else:
                    target_w = max(10.0, target_layout_box[2] - target_layout_box[0])
                    fits, final_font_size, overflow_cause, line_count, effective_lineheight = self._fit_tester.test_fit(
                        rect=target_layout_box,
                        text=translated_text,
                        orig_font_size=orig_font_size,
                        options=self.options,
                        font_name=block_font,
                    )

                orig_box_w = max(1.0, block.bbox[2] - block.bbox[0])
                is_vertical_rotated = (
                    not is_cell
                    and "\n" not in translated_text.strip()
                    and orig_box_w <= orig_font_size * 2.2
                    and orig_box_h >= max(orig_font_size * 3.0, orig_box_w * 2.8)
                )
                if is_vertical_rotated:
                    w_at_orig = self.font_manager.measure_text_length(
                        translated_text.strip(), orig_font_size, block_font
                    )
                    avail_v_len = max(16.0, orig_box_h)
                    if w_at_orig <= avail_v_len * 1.05:
                        fits = True
                        final_font_size = orig_font_size
                        overflow_cause = ""
                        line_count = 1
                    else:
                        min_floor_sz = max(
                            self.options.min_font_pt,
                            orig_font_size * self.options.min_font_scale,
                        )
                        uncond_sz = orig_font_size * (avail_v_len / max(1.0, w_at_orig))
                        cond_sz = max(
                            self.options.min_font_pt,
                            min(
                                orig_font_size,
                                max(
                                    uncond_sz,
                                    min(
                                        min_floor_sz,
                                        orig_font_size * (avail_v_len / max(1.0, w_at_orig * 0.68)),
                                    ),
                                ),
                            ),
                        )
                        fits = True
                        final_font_size = cond_sz
                        overflow_cause = ""
                        line_count = 1

                span_cys = [
                    (s.bbox[1] + s.bbox[3]) * 0.5
                    for s in block.spans
                    if s.text and s.text.strip()
                ]
                src_text_w = self.font_manager.measure_text_length(
                    block.text.strip(), orig_font_size, block_font
                )
                is_single_span_row = (
                    (max(span_cys) - min(span_cys)) <= orig_font_size * 0.65
                    if len(span_cys) >= 2
                    else ("\n" not in block.text.strip() and src_text_w <= orig_box_w * 1.25)
                )
                is_strict_single_line = (
                    not is_cell
                    and not is_vertical_rotated
                    and "\n" not in translated_text.strip()
                    and "\n" not in block.text.strip()
                    and (
                        orig_box_h <= orig_font_size * 1.65
                        or (orig_box_h <= orig_font_size * 2.25 and is_single_span_row)
                    )
                )
                if is_strict_single_line:
                    adapted_at_orig = self._fit_tester.adapt_dot_leader_if_needed(
                        text=translated_text.strip(),
                        target_width=target_w,
                        font_size=orig_font_size,
                        font_name=block_font,
                    )
                    w_at_orig = self.font_manager.measure_text_length(adapted_at_orig, orig_font_size, block_font)
                    if w_at_orig <= target_w * 1.28:
                        # Keep 100% vertical cap/x-height and rely on gentle horizontal condensation (0.78x..1.0x)
                        fits = True
                        final_font_size = orig_font_size
                        line_count = 1
                    elif w_at_orig <= target_w * 1.44:
                        fits = True
                        final_font_size = max(final_font_size, orig_font_size * 0.94)
                        line_count = 1
                    else:
                        # Single-line label that can fit with combined font scaling + 0.68x horizontal condensation
                        cond_sz = min(
                            orig_font_size * 0.94,
                            orig_font_size * (target_w / max(1.0, w_at_orig * 0.68)),
                        )
                        if cond_sz >= max(5.0, orig_font_size * 0.45):
                            fits = True
                            final_font_size = cond_sz
                            line_count = 1

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

                # TS-parity token flow: keep original math glyphs frozen ONLY when the block
                # contains 2D sub/superscript spans or unmapped glyphs not present in block_font (or FreeSerif fallback).
                token_specs = None
                block_tokens = token_map.get(block.block_id) or []
                if block_tokens and tight_line_rects and not is_cell:
                    font_obj_check = self.font_manager.get_font(block_font)
                    fb_font_check = self.font_manager.get_font(self.options.font_name)
                    has_2d_sub_sup = any(
                        s.text.strip() and s.font_size < orig_font_size * 0.82
                        for s in block.spans
                    )
                    has_unmapped_glyph = any(
                        any(
                            0xF000 <= ord(c) <= 0xF0FF
                            or (font_obj_check.has_glyph(ord(c)) == 0 and fb_font_check.has_glyph(ord(c)) == 0)
                            for c in t.raw_content
                            if not c.isspace()
                        )
                        for t in block_tokens
                    )
                    if has_2d_sub_sup or has_unmapped_glyph:
                        token_specs = self._plan_token_flow(
                            block,
                            block_tokens,
                            translated_text,
                            tight_line_rects,
                            block_font,
                            orig_font_size,
                            max_right_x=target_layout_box[2],
                        )

                if fits or token_specs:
                    if token_specs:
                        # Token flow: chunks are drawn per-gap at their own sizes;
                        # the original math glyphs are never touched.
                        fitting_plan.append((
                            block,
                            tight_line_rects,
                            translated_text,
                            orig_font_size,
                            dominant_color,
                            orig_font_size,
                            1.2,
                            len(tight_line_rects),
                            target_layout_box,
                            is_cell,
                            grid,
                            cell_geom,
                            block_font,
                            token_specs,
                        ))
                        continue
                    # For Table of Contents dot leaders, re-adapt to the fitted font size
                    translated_text = self._fit_tester.adapt_dot_leader_if_needed(
                        text=translated_text,
                        target_width=target_w,
                        font_size=final_font_size,
                        font_name=block_font,
                    )
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
                        None,
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

            # 7b. SOTA Font Harmonization (pdf2zh / BabelDOC pattern):
            # Harmonize sibling items in Table of Contents or numbered lists on the same page
            # so adjacent lines do not suffer from ragged font size disparity (e.g. 12pt alternating with 8pt).
            if fitting_plan:
                from layoutlingua.typesetting.fitting import TOC_LEADER_PATTERN

                toc_indices = [
                    idx for idx, item in enumerate(fitting_plan)
                    if TOC_LEADER_PATTERN.match(item[2].strip())
                ]
                if len(toc_indices) >= 2:
                    toc_sizes = [fitting_plan[i][5] for i in toc_indices]
                    max_sz = max(toc_sizes)
                    harmonized_sz = max(max_sz, 7.5)
                    orig_toc_x1 = max(fitting_plan[i][0].bbox[2] for i in toc_indices)
                    canonical_toc_x1 = orig_toc_x1 if orig_toc_x1 > 100.0 else max(fitting_plan[i][8][2] for i in toc_indices)
                    new_plan = list(fitting_plan)
                    for i in toc_indices:
                        item = new_plan[i]
                        t_box = item[8]
                        unified_box = (t_box[0], t_box[1], max(t_box[0] + 40.0, canonical_toc_x1), t_box[3])
                        t_w = max(10.0, unified_box[2] - unified_box[0])
                        re_adapted_text = self._fit_tester.adapt_dot_leader_if_needed(
                            text=item[2],
                            target_width=t_w,
                            font_size=harmonized_sz,
                            font_name=item[12],
                        )
                        new_plan[i] = (
                            item[0],
                            item[1],
                            re_adapted_text,
                            item[3],
                            item[4],
                            harmonized_sz,
                            item[6],
                            1,
                            unified_box,
                            item[9],
                            item[10],
                            item[11],
                            item[12],
                            item[13] if len(item) > 13 else None,
                        )
                    fitting_plan = new_plan

                # 7c. Collinear Row & Page-Level Font Harmonization:
                # Ensure inline text blocks sitting on the exact same horizontal line (e.g. prose fragments
                # separated by inline formula blocks) share a uniform font size instead of ragged jumps.
                row_groups: list[list[int]] = []
                for idx, item in enumerate(fitting_plan):
                    blk, _, _, o_sz, _, _, _, l_cnt, _, is_c, _, _, _, t_specs = item
                    if is_c or t_specs is not None or l_cnt != 1:
                        continue
                    cy = (blk.bbox[1] + blk.bbox[3]) * 0.5
                    placed = False
                    for grp in row_groups:
                        ref_blk = fitting_plan[grp[0]][0]
                        ref_osz = fitting_plan[grp[0]][3]
                        ref_cy = (ref_blk.bbox[1] + ref_blk.bbox[3]) * 0.5
                        if abs(cy - ref_cy) <= max(4.2, o_sz * 0.38) and abs(o_sz - ref_osz) <= 1.2:
                            grp.append(idx)
                            placed = True
                            break
                    if not placed:
                        row_groups.append([idx])

                new_plan_rows = list(fitting_plan)
                for grp in row_groups:
                    if len(grp) < 2:
                        continue
                    grp_sizes = [new_plan_rows[i][5] for i in grp]
                    max_r_sz = max(grp_sizes)
                    min_r_sz = min(grp_sizes)
                    if (max_r_sz - min_r_sz) > 0.35:
                        target_r_sz = max(min_r_sz, max_r_sz * 0.92)
                        for i in grp:
                            it = new_plan_rows[i]
                            t_box = it[8]
                            avail_w = max(10.0, t_box[2] - t_box[0])
                            w_at_target = self.font_manager.measure_text_length(it[2], target_r_sz, it[12])
                            if w_at_target <= avail_w * 1.45:
                                new_plan_rows[i] = (
                                    it[0],
                                    it[1],
                                    it[2],
                                    it[3],
                                    it[4],
                                    target_r_sz,
                                    it[6],
                                    1,
                                    it[8],
                                    it[9],
                                    it[10],
                                    it[11],
                                    it[12],
                                    it[13],
                                )
                fitting_plan = new_plan_rows

            # 8. Apply selective redaction ONLY on approved, fitting candidates
            if fitting_plan:
                for block, tight_line_rects, *rest in fitting_plan:
                    token_specs = rest[-1] if rest and isinstance(rest[-1], list) else None
                    if token_specs:
                        # TS-parity: redact only the prose gaps so the frozen math
                        # glyphs survive with their original fonts and positioning.
                        for gap_rect, _chunk, _size in token_specs:
                            scratch_page.add_redact_annot(gap_rect, fill=False, cross_out=False)
                    else:
                        for line_rect in tight_line_rects:
                            rect = pymupdf.Rect(*line_rect)
                            scratch_page.add_redact_annot(rect, fill=False, cross_out=False)

                scratch_page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_NONE,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )

                # Erase partial-width inline code/highlight pills inside replaced prose blocks
                # so old source-language pill offsets do not sit beneath shifted translated words.
                try:
                    page_drawings = scratch_page.get_drawings()
                    for block, tight_line_rects, *rest in fitting_plan:
                        t_specs = rest[-1] if rest and isinstance(rest[-1], list) else None
                        if t_specs:
                            continue
                        bx0, by0, bx1, by1 = block.bbox
                        parent_bg: tuple[float, float, float] = (1.0, 1.0, 1.0)
                        for drw in page_drawings:
                            dr = drw.get("rect")
                            d_fill = drw.get("fill")
                            if (
                                dr
                                and isinstance(d_fill, (tuple, list))
                                and len(d_fill) >= 3
                                and dr.x0 <= bx0 + 2.5
                                and dr.x1 >= bx1 - 2.5
                                and dr.y0 <= by0 + 2.5
                                and dr.y1 >= by1 - 2.5
                                and (dr.width > (bx1 - bx0) + 8.0 or dr.height > 26.0)
                            ):
                                parent_bg = (float(d_fill[0]), float(d_fill[1]), float(d_fill[2]))
                        for drw in page_drawings:
                            dr = drw.get("rect")
                            d_fill = drw.get("fill")
                            if (
                                dr
                                and drw.get("type") == "f"
                                and drw.get("color") is None
                                and dr.width >= 6.0
                                and 8.0 <= dr.height <= 24.0
                                and isinstance(d_fill, (tuple, list))
                                and len(d_fill) >= 3
                                and min(float(c) for c in d_fill[:3]) >= 0.70
                                and (dr.x0 > bx0 + 3.0 or dr.x1 < bx1 - 3.0)
                                and any(
                                    min(dr.x1, rx1) - max(dr.x0, rx0) > 2.0
                                    and min(dr.y1, ry1) - max(dr.y0, ry0) > 4.0
                                    for (rx0, ry0, rx1, ry1) in tight_line_rects
                                )
                            ):
                                scratch_page.draw_rect(dr, color=None, fill=parent_bg)
                except Exception:
                    pass

                drawn_ink_boxes: list[tuple[float, float, float, float]] = []

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
                    token_specs,
                ) in fitting_plan:
                    if token_specs:
                        # TS-parity draw: prose chunks into the gaps around frozen math
                        fontfile_arg = (
                            None
                            if block_font.lower() in BUILTIN_OR_CJK_FONTS
                            else str(self.font_manager.get_font_path(block_font))
                        )
                        shrink_ratios = []
                        font_obj = self.font_manager.get_font(block_font)
                        self.font_manager.register_on_page(scratch_page, font_name=block_font)
                        for gap_rect, chunk_text, chunk_size in token_specs:
                            if not chunk_text or not chunk_text.strip():
                                continue
                            raw_w = font_obj.text_length(chunk_text, fontsize=chunk_size)
                            avail_w = max(8.0, gap_rect.width - 1.0)
                            tz_factor = min(1.0, max(0.72, avail_w / max(1.0, raw_w))) if raw_w > avail_w else 1.0
                            baseline_y = gap_rect.y1 - max(1.8, chunk_size * 0.20)
                            pt = pymupdf.Point(gap_rect.x0, baseline_y)
                            morph = (pt, pymupdf.Matrix(tz_factor, 1.0)) if tz_factor < 0.995 else None
                            scratch_page.insert_text(
                                pt,
                                chunk_text,
                                fontsize=chunk_size,
                                fontname=block_font,
                                fontfile=fontfile_arg,
                                color=color,
                                morph=morph,
                            )
                            eff_chunk_scale = chunk_size if tz_factor >= 0.78 else (chunk_size * tz_factor)
                            shrink_ratios.append(eff_chunk_scale / orig_size if orig_size > 0 else 1.0)
                            page_replaced_ratios.append(shrink_ratios[-1])

                        shrink_ratio = min(shrink_ratios) if shrink_ratios else 1.0
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
                                final_font_size=round(min(shrink_ratios) * orig_size, 2) if shrink_ratios else orig_size,
                                shrink_ratio=shrink_ratio,
                                line_height_em=1.15,
                                line_count=len(token_specs),
                                bbox=target_layout_box,
                                overflow_cause=OverflowCause.NONE,
                                unit_kind="CELL" if is_cell else "BLOCK",
                                table_id=grid.table_id if grid else None,
                                row_idx=cell_geom.row_idx if cell_geom else None,
                                col_idx=cell_geom.col_idx if cell_geom else None,
                                reason="Token flow: math glyphs frozen, prose drawn into gaps.",
                            )
                        )
                        continue
                    fontfile_arg = (
                        None
                        if block_font.lower() in BUILTIN_OR_CJK_FONTS
                        else str(self.font_manager.get_font_path(block_font))
                    )
                    self.font_manager.register_on_page(scratch_page, font_name=block_font)
                    orig_box_h = block.bbox[3] - block.bbox[1]
                    avail_w = max(10.0, target_layout_box[2] - target_layout_box[0])
                    raw_single_w = self.font_manager.measure_text_length(text, final_size, block_font)
                    m_toc_draw = TOC_LEADER_PATTERN.match(text.strip()) if ("\n" not in text and not is_cell) else None

                    if m_toc_draw is not None:
                        prefix_str = m_toc_draw.group(1).rstrip()
                        suffix_str = (m_toc_draw.group(3) or "").strip()
                        span_oy = (
                            float(block.spans[0].origin[1])
                            if (block.spans and block.spans[0].origin and block.spans[0].origin[1] > block.bbox[1])
                            else (block.bbox[3] - max(1.8, final_size * 0.20))
                        )
                        pt_x = block.bbox[0]
                        right_x = target_layout_box[2]
                        suffix_w = (
                            self.font_manager.measure_text_length(suffix_str, final_size, block_font)
                            if suffix_str
                            else 0.0
                        )
                        suffix_x = (right_x - suffix_w) if suffix_str else right_x
                        prefix_w = self.font_manager.measure_text_length(prefix_str, final_size, block_font)
                        min_leader_gap = max(14.0, final_size * 1.25)
                        max_prefix_w = max(24.0, suffix_x - min_leader_gap - pt_x)
                        tz_prefix = (
                            min(1.0, max(0.64, max_prefix_w / max(1.0, prefix_w)))
                            if prefix_w > max_prefix_w
                            else 1.0
                        )
                        pt_prefix = pymupdf.Point(pt_x, span_oy)
                        morph_prefix = (
                            (pt_prefix, pymupdf.Matrix(tz_prefix, 1.0))
                            if tz_prefix < 0.995
                            else None
                        )
                        scratch_page.insert_text(
                            pt_prefix,
                            prefix_str,
                            fontsize=final_size,
                            fontname=block_font,
                            fontfile=fontfile_arg,
                            color=color,
                            morph=morph_prefix,
                        )
                        prefix_end_x = pt_x + prefix_w * tz_prefix
                        dot_adv = max(1.5, self.font_manager.measure_text_length(".", final_size, block_font))
                        leader_start = prefix_end_x + max(2.5, final_size * 0.25)
                        leader_end = suffix_x - max(3.0, final_size * 0.30)
                        first_dot_x = math.ceil(leader_start / dot_adv) * dot_adv
                        n_dots = max(2, int((leader_end - first_dot_x) / dot_adv))
                        if first_dot_x + n_dots * dot_adv > suffix_x - 1.5:
                            first_dot_x = max(prefix_end_x + 1.5, suffix_x - (n_dots + 1) * dot_adv)
                        scratch_page.insert_text(
                            pymupdf.Point(first_dot_x, span_oy),
                            "." * n_dots,
                            fontsize=final_size,
                            fontname=block_font,
                            fontfile=fontfile_arg,
                            color=color,
                        )
                        if suffix_str:
                            scratch_page.insert_text(
                                pymupdf.Point(suffix_x, span_oy),
                                suffix_str,
                                fontsize=final_size,
                                fontname=block_font,
                                fontfile=fontfile_arg,
                                color=color,
                            )
                        drawn_ink_boxes.append((pt_x, span_oy - final_size * 0.82, right_x, span_oy + final_size * 0.20))
                        shrink_ratio = final_size / orig_size if orig_size > 0 else 1.0
                    elif (
                        not is_cell
                        and "\n" not in text.strip()
                        and (block.bbox[2] - block.bbox[0]) <= orig_size * 2.2
                        and orig_box_h >= max(orig_size * 3.0, (block.bbox[2] - block.bbox[0]) * 2.8)
                    ):
                        span_ox = (
                            float(block.spans[0].origin[0])
                            if (
                                block.spans
                                and block.spans[0].origin
                                and block.bbox[0] - 2.0 <= block.spans[0].origin[0] <= block.bbox[2] + 4.0
                            )
                            else (block.bbox[2] - max(1.8, final_size * 0.22))
                        )
                        mid_y = (block.bbox[1] + block.bbox[3]) * 0.5
                        if block.spans and block.spans[0].origin:
                            raw_oy = float(block.spans[0].origin[1])
                            rot_angle = 90 if raw_oy >= mid_y else 270
                            span_oy = raw_oy
                        else:
                            rot_angle = 90
                            span_oy = block.bbox[3]
                        v_pt = pymupdf.Point(span_ox, span_oy)
                        v_len_at_final = self.font_manager.measure_text_length(
                            text.strip(), final_size, block_font
                        )
                        v_tz = (
                            min(1.0, max(0.68, orig_box_h / max(1.0, v_len_at_final)))
                            if v_len_at_final > orig_box_h * 1.02
                            else 1.0
                        )
                        v_morph = (v_pt, pymupdf.Matrix(1.0, v_tz)) if v_tz < 0.995 else None
                        scratch_page.insert_text(
                            v_pt,
                            text.strip(),
                            fontsize=final_size,
                            fontname=block_font,
                            fontfile=fontfile_arg,
                            color=color,
                            rotate=rot_angle,
                            morph=v_morph,
                        )
                        drawn_ink_boxes.append(block.bbox)
                        shrink_ratio = final_size / orig_size if orig_size > 0 else 1.0
                    elif (
                        line_count == 1
                        and orig_box_h <= orig_size * 2.45
                        and not is_cell
                        and "\n" not in text
                        and raw_single_w <= avail_w * 1.52
                    ):
                        tz_factor = min(1.0, max(0.68, avail_w / max(1.0, raw_single_w))) if raw_single_w > avail_w else 1.0
                        span_oy = (
                            float(block.spans[0].origin[1])
                            if (block.spans and block.spans[0].origin and block.spans[0].origin[1] > block.bbox[1])
                            else (block.bbox[3] - max(1.8, final_size * 0.20))
                        )
                        drawn_w = raw_single_w * tz_factor
                        if target_layout_box[0] < block.bbox[0] - 1.0:
                            pt_x = max(target_layout_box[0], min(block.bbox[0], target_layout_box[2] - drawn_w - 1.0))
                        else:
                            pt_x = target_layout_box[0]
                        curr_ink_top = span_oy - final_size * 0.78
                        for px0, py0, px1, py1 in drawn_ink_boxes:
                            if min(pt_x + drawn_w, px1) - max(pt_x, px0) > 8.0 and py0 < curr_ink_top + 4.0 and py1 > curr_ink_top + 0.35:
                                nudge = min(4.0, (py1 + 0.5) - curr_ink_top)
                                if nudge > 0:
                                    span_oy += nudge
                                    curr_ink_top += nudge
                        pt = pymupdf.Point(pt_x, span_oy)
                        self._insert_text_with_cjk_fallback(
                            scratch_page,
                            pt,
                            text,
                            fontsize=final_size,
                            block_font=block_font,
                            fontfile_arg=fontfile_arg,
                            color=color,
                            tz_factor=tz_factor,
                        )
                        drawn_ink_boxes.append((pt_x, span_oy - final_size * 0.78, pt_x + drawn_w, span_oy + final_size * 0.14))
                        shrink_ratio = final_size / orig_size if orig_size > 0 else 1.0
                    else:
                        try:
                            font_asc = float(self.font_manager.get_font(block_font).ascender)
                        except Exception:
                            font_asc = 0.928

                        span_oy_first = (
                            float(block.spans[0].origin[1])
                            if (block.spans and block.spans[0].origin and block.spans[0].origin[1] > block.bbox[1])
                            else None
                        )

                        # Measure original source line rhythm from distinct span baseline origins
                        span_oys = sorted({
                            round(float(s.origin[1]), 1)
                            for s in block.spans
                            if s.text and s.text.strip() and s.origin and s.origin[1] > block.bbox[1]
                        })
                        distinct_oys: list[float] = []
                        src_pitch_em = 1.25
                        if len(span_oys) >= 2:
                            distinct_oys = [span_oys[0]]
                            for oy in span_oys[1:]:
                                if oy - distinct_oys[-1] >= orig_size * 0.55:
                                    distinct_oys.append(oy)
                            if len(distinct_oys) >= 2:
                                src_pitch_em = (distinct_oys[-1] - distinct_oys[0]) / (
                                    (len(distinct_oys) - 1) * max(1.0, orig_size)
                                )
                        target_em_pitch = max(1.22, min(1.38, src_pitch_em))

                        # Line-Grid Preservation (BabelDOC / pdf2zh):
                        # When a multi-line display/heading block (orig_size >= 14pt or tall box) wraps into the exact
                        # same number of lines as the source block (line_count == len(distinct_oys)) at a reduced font size,
                        # preserve the source's absolute baseline-to-baseline pitch and center each line vertically on its
                        # corresponding source line so background grid rows/dividers stay aligned.
                        preserve_line_grid = (
                            len(distinct_oys) >= 2
                            and line_count == len(distinct_oys)
                            and (orig_size >= 14.0 or orig_box_h >= 60.0)
                            and final_size < orig_size * 0.98
                        )
                        if preserve_line_grid:
                            src_abs_pitch = (distinct_oys[-1] - distinct_oys[0]) / (len(distinct_oys) - 1)
                            target_em_pitch = max(1.22, min(2.0, src_abs_pitch / max(1.0, final_size)))
                            target_base1 = distinct_oys[0] - 0.35 * (orig_size - final_size)
                            top_y = target_base1 - final_size * font_asc
                        elif span_oy_first is not None:
                            # Exact PyMuPDF first-line baseline alignment: insert_textbox places line 1 baseline at rect.y0 + final_size * font_asc
                            if final_size < orig_size * 0.95:
                                target_base1 = span_oy_first - 0.25 * (orig_size - final_size)
                            else:
                                target_base1 = span_oy_first
                            top_y = max(target_layout_box[1] - final_size * 0.25, target_base1 - final_size * font_asc)
                        else:
                            top_y = target_layout_box[1]

                        for px0, py0, px1, py1 in drawn_ink_boxes:
                            if min(target_layout_box[2], px1) - max(target_layout_box[0], px0) > 8.0 and py0 < top_y + 4.0 and py1 > top_y + 0.35:
                                nudge = min(4.5, (py1 + 0.5) - top_y)
                                if nudge > 0:
                                    top_y += nudge

                        # Respect vertical clearance to the next block below on the page
                        if line_count > 1 and not is_cell and not preserve_line_grid:
                            below_y0s = [
                                ob.bbox[1]
                                for ob in page_ir.blocks
                                if ob.block_id != block.block_id
                                and ob.bbox[1] >= block.bbox[3] - 2.5
                                and (min(target_layout_box[2], ob.bbox[2]) - max(target_layout_box[0], ob.bbox[0])) > 8.0
                            ]
                            if below_y0s:
                                next_below_y0 = min(below_y0s)
                                avail_ink_h = max(final_size * 1.2, (next_below_y0 - 1.8) - top_y)
                                max_em_pitch = (avail_ink_h - final_size) / max(1.0, (line_count - 1) * final_size)
                                target_em_pitch = max(1.16, min(target_em_pitch, max_em_pitch))

                        render_lh = (
                            (target_em_pitch / font_asc)
                            if (0.50 <= font_asc < 0.88)
                            else max(lineheight, target_em_pitch)
                        )
                        box_h = max(
                            target_layout_box[3] - top_y,
                            (line_count + 1.5) * final_size * render_lh,
                        )
                        rect = pymupdf.Rect(target_layout_box[0], top_y, target_layout_box[2], top_y + box_h)
                        cjk_multiline_needs_fb = False
                        if block_font.lower() in CJK_EMBED_FONTS:
                            try:
                                cjk_f_obj = self.font_manager.get_font(block_font)
                                cjk_multiline_needs_fb = any(
                                    not ch.isspace() and not cjk_f_obj.has_glyph(ord(ch))
                                    for ch in text
                                )
                            except Exception:
                                cjk_multiline_needs_fb = False

                        narrow_condensed_multiline = False
                        if (
                            not cjk_multiline_needs_fb
                            and orig_box_h >= orig_size * 1.80
                            and any(
                                self.font_manager.measure_text_length(w, final_size, block_font) > max(4.0, rect.width - 2.5)
                                for w in text.split()
                            )
                        ):
                            adapted_uncond = self._fit_tester.adapt_narrow_multiline_if_needed(
                                text, rect.width, orig_box_h, final_size, block_font
                            )
                            uncond_words_fit = all(
                                self.font_manager.measure_text_length(w, final_size, block_font) <= max(4.0, rect.width - 2.5)
                                for w in adapted_uncond.split()
                            )
                            max_uncond_lines = max(line_count, round(orig_box_h / max(4.0, final_size * 0.95)))
                            if uncond_words_fit and len(adapted_uncond.split()) <= max_uncond_lines:
                                text = adapted_uncond
                            else:
                                text = self._fit_tester.adapt_narrow_multiline_if_needed(
                                    text, rect.width / 0.70, orig_box_h, final_size, block_font
                                )
                                narrow_condensed_multiline = True

                        if cjk_multiline_needs_fb or narrow_condensed_multiline:
                            avail_line_w = max(8.0, rect.width - 1.5)
                            wrap_target_w = (avail_line_w / 0.70) if narrow_condensed_multiline else max(20.0, rect.width - 2.0)
                            wrapped_lines: list[str] = []
                            for para in text.split("\n"):
                                cur_line = ""
                                # Tokenize into atomic units: either a CJK char or a contiguous non-CJK non-space token
                                atoms = re.findall(r"[\u2e80-\u9fff\u3040-\u30ff\uac00-\ud7af]|[^\s\u2e80-\u9fff\u3040-\u30ff\uac00-\ud7af]+|\s+", para)
                                for atom in atoms:
                                    cand = cur_line + atom
                                    if cur_line.strip() and self.font_manager.measure_text_length(cand.strip(), final_size, block_font) > wrap_target_w:
                                        wrapped_lines.append(cur_line.strip())
                                        cur_line = atom.lstrip()
                                    else:
                                        cur_line = cand
                                if cur_line.strip():
                                    wrapped_lines.append(cur_line.strip())
                            if narrow_condensed_multiline:
                                base_y0 = min(
                                    span_oy_first if span_oy_first is not None else (block.bbox[1] + final_size * 0.82),
                                    block.bbox[1] + final_size * 0.82,
                                )
                                max_bottom_base = block.bbox[3] - max(0.8, final_size * 0.16)
                                line_step = (
                                    min(
                                        final_size * 1.15,
                                        max(final_size * 0.96, (max_bottom_base - base_y0) / max(1, len(wrapped_lines) - 1)),
                                    )
                                    if len(wrapped_lines) >= 2
                                    else final_size * 1.10
                                )
                            else:
                                base_y0 = span_oy_first if span_oy_first is not None else (top_y + final_size * font_asc)
                                line_step = final_size * target_em_pitch
                            for l_idx, w_line in enumerate(wrapped_lines):
                                line_y = base_y0 + l_idx * line_step
                                line_w = self.font_manager.measure_text_length(w_line, final_size, block_font)
                                tz_l = min(1.0, max(0.68, avail_line_w / max(1.0, line_w))) if line_w > avail_line_w else 1.0
                                self._insert_text_with_cjk_fallback(
                                    scratch_page,
                                    pymupdf.Point(target_layout_box[0], line_y),
                                    w_line,
                                    fontsize=final_size,
                                    block_font=block_font,
                                    fontfile_arg=fontfile_arg,
                                    color=color,
                                    tz_factor=tz_l,
                                )
                        else:
                            rc = scratch_page.insert_textbox(
                                rect,
                                text,
                                fontsize=final_size,
                                fontname=block_font,
                                fontfile=fontfile_arg,
                                color=color,
                                lineheight=render_lh,
                            )
                            if rc < 0:
                                rect = pymupdf.Rect(target_layout_box[0], top_y, target_layout_box[2], top_y + box_h + abs(rc) + 4.0)
                                scratch_page.insert_textbox(
                                    rect,
                                    text,
                                    fontsize=final_size,
                                    fontname=block_font,
                                    fontfile=fontfile_arg,
                                    color=color,
                                    lineheight=render_lh,
                                )
                        est_ink_bottom = top_y + max(0, line_count - 1) * (final_size * target_em_pitch) + final_size
                        drawn_ink_boxes.append((target_layout_box[0], top_y, target_layout_box[2], est_ink_bottom))
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
