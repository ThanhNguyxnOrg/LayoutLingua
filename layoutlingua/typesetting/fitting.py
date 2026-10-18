"""Adaptive font fitting using binary search, dynamic lineheight, and overflow classification."""

from __future__ import annotations

import re

import pymupdf

from layoutlingua.typesetting.fonts import BUILTIN_OR_CJK_FONTS, FontManager
from layoutlingua.typesetting.models import OverflowCause, TypesetOptions

# Standard Table of Contents dot leader pattern: Title + at least 2 dots/dashes + page number
TOC_LEADER_PATTERN = re.compile(r"^(.*?)(\s*[\.\:\-_–—…]{2,}\s*)(\d+)$")


class TextFitTester:
    """Evaluates whether text fits within a bounding box using precision binary search."""

    def __init__(self, font_manager: FontManager, font_name: str = "DejaVuSans") -> None:
        self.font_manager = font_manager
        self.font_name = font_name
        self._doc = pymupdf.open()
        self._page = self._doc.new_page(width=1000, height=1000)
        self.font_manager.register_on_page(self._page, font_name=self.font_name)
        self.font_manager.register_on_page(self._page, font_name=f"{self.font_name}-Bold")

    def adapt_dot_leader_if_needed(
        self,
        text: str,
        target_width: float,
        font_size: float,
        font_name: str | None = None,
    ) -> str:
        """Dynamically adjust dot leader length for Table of Contents lines (LaTeX \\dotfill pattern).

        Prevents line-wrapping which causes catastrophic single-line OVERFLOW_FALLBACK.
        """
        if not text or target_width <= 0:
            return text

        match = TOC_LEADER_PATTERN.match(text.strip())
        if not match:
            return text

        prefix = match.group(1).rstrip()
        suffix = match.group(3).lstrip()

        active_font = font_name or self.font_name
        prefix_len = self.font_manager.measure_text_length(prefix, font_size, active_font)
        suffix_len = self.font_manager.measure_text_length(suffix, font_size, active_font)
        space_len = self.font_manager.measure_text_length(" ", font_size, active_font)
        dot_len = max(1.0, self.font_manager.measure_text_length(".", font_size, active_font))

        # Available width for dot leader with a safety cushion of 8.0pt
        avail_width = target_width - prefix_len - suffix_len - (2 * space_len) - 8.0
        if avail_width <= dot_len * 2:
            return f"{prefix} ... {suffix}"

        num_dots = int(avail_width / dot_len)
        num_dots = max(3, min(num_dots, 120))
        dots_str = "." * num_dots
        return f"{prefix} {dots_str} {suffix}"

    def test_fit(
        self,
        rect: tuple[float, float, float, float],
        text: str,
        orig_font_size: float,
        options: TypesetOptions,
        font_name: str | None = None,
    ) -> tuple[bool, float, OverflowCause, int, float]:
        """Determine if text fits within rect using bounded binary search.

        Returns:
            (fits, final_font_size, overflow_cause, line_count, effective_lineheight)
        """
        x0, y0, x1, y1 = rect
        width = x1 - x0
        height = y1 - y0

        effective_lineheight = self.font_manager.calculate_effective_lineheight(
            configured_ratio=options.base_lineheight_ratio,
            safety_padding_em=options.safety_padding_em,
        )

        if width <= 0 or height <= 0 or not text.strip():
            return False, orig_font_size, OverflowCause.OVERFLOW_UNDETERMINED, 0, effective_lineheight

        active_font = font_name or self.font_name

        is_toc = bool(TOC_LEADER_PATTERN.match(text.strip()))
        is_single_line = (height <= 2.2 * orig_font_size) or is_toc

        # For Table of Contents dot-leader lines and single-line labels, allow flexible font floor (down to 0.50x or 5.0pt)
        # to prevent catastrophic 2-line wrapping in a 1-line bounding box.
        effective_min_scale = min(options.min_font_scale, 0.50) if (is_single_line or is_toc) else options.min_font_scale
        effective_min_pt = (
            min(options.min_font_pt, 5.0)
            if (is_single_line or is_toc) and options.min_font_pt <= 6.0
            else options.min_font_pt
        )
        min_font_size = max(effective_min_pt, effective_min_scale * orig_font_size)
        test_rect = pymupdf.Rect(x0, y0, x1, y1)

        fontfile_arg = (
            None
            if active_font.lower() in BUILTIN_OR_CJK_FONTS
            else str(self.font_manager.get_font_path(active_font))
        )

        def get_text_for_size(sz: float) -> str:
            if is_toc:
                return self.adapt_dot_leader_if_needed(text, width, sz, active_font)
            return text

        # 1. Test original size
        text_orig = get_text_for_size(orig_font_size)
        rc_orig = self._page.insert_textbox(
            test_rect,
            text_orig,
            fontsize=orig_font_size,
            fontname=active_font,
            fontfile=fontfile_arg,
            lineheight=effective_lineheight,
        )
        if rc_orig >= 0:
            lines = self._estimate_lines(height, rc_orig, orig_font_size, effective_lineheight)
            return True, orig_font_size, OverflowCause.NONE, max(1, lines), effective_lineheight

        # 1b. Single-line ink-height accommodation:
        # If text fits horizontally on a single line and the overflow is purely vertical padding deficit (within 60% of font size):
        text_advance = self.font_manager.measure_text_length(text_orig, orig_font_size, active_font)
        if text_advance <= (width * 1.02) and abs(rc_orig) <= (orig_font_size * 0.60):
            return True, orig_font_size, OverflowCause.NONE, 1, effective_lineheight

        # 2. Test minimum font size floor
        text_min = get_text_for_size(min_font_size)
        rc_min = self._page.insert_textbox(
            test_rect,
            text_min,
            fontsize=min_font_size,
            fontname=active_font,
            fontfile=fontfile_arg,
            lineheight=effective_lineheight,
        )
        if rc_min < 0:
            # 2a. Lineheight micro-compaction: try tighter lineheight (down to 1.05x)
            compact_lh = max(1.02, effective_lineheight * 0.90)
            rc_compact = self._page.insert_textbox(
                test_rect,
                text_min,
                fontsize=min_font_size,
                fontname=active_font,
                fontfile=fontfile_arg,
                lineheight=compact_lh,
            )
            if rc_compact >= 0:
                lines = self._estimate_lines(height, rc_compact, min_font_size, compact_lh)
                return True, min_font_size, OverflowCause.NONE, lines, compact_lh

            # 2b. Soft Margin Absorption:
            # Absorb minor vertical overflow (within 1.2 * min_font_size or 8% box height)
            slight_overflow_threshold = 1.2 * min_font_size
            if abs(rc_compact) <= slight_overflow_threshold:
                soft_pad = min(max(3.0, height * 0.15), slight_overflow_threshold)
                soft_rect = pymupdf.Rect(x0, y0, x1, y1 + soft_pad)
                rc_soft = self._page.insert_textbox(
                    soft_rect,
                    text_min,
                    fontsize=min_font_size,
                    fontname=active_font,
                    fontfile=fontfile_arg,
                    lineheight=compact_lh,
                )
                if rc_soft >= 0:
                    lines = self._estimate_lines(height + soft_pad, rc_soft, min_font_size, compact_lh)
                    return True, min_font_size, OverflowCause.NONE, lines, compact_lh

            # Overflow event at minimum scale: classify cause
            cause = self._classify_overflow_cause(text_min, width, min_font_size)
            return False, orig_font_size, cause, 0, effective_lineheight

        # 3. Binary Search in [min_font_size, orig_font_size]
        low = min_font_size
        high = orig_font_size
        best_size = min_font_size
        best_rc = rc_min
        iteration = 0

        while (high - low) > options.binary_search_epsilon and iteration < options.max_search_iterations:
            mid = (low + high) / 2.0
            text_mid = get_text_for_size(mid)
            rc = self._page.insert_textbox(
                test_rect,
                text_mid,
                fontsize=mid,
                fontname=active_font,
                fontfile=fontfile_arg,
                lineheight=effective_lineheight,
            )
            if rc >= 0:
                best_size = mid
                best_rc = rc
                low = mid  # text fits; attempt a larger size for better legibility
            else:
                high = mid  # text overflowed; must reduce size
            iteration += 1

        # 4. Verification pass on scratch page
        text_best = get_text_for_size(best_size)
        confirm_rc = self._page.insert_textbox(
            test_rect,
            text_best,
            fontsize=best_size,
            fontname=active_font,
            fontfile=fontfile_arg,
            lineheight=effective_lineheight,
        )
        if confirm_rc >= 0:
            lines = self._estimate_lines(height, confirm_rc, best_size, effective_lineheight)
            return True, best_size, OverflowCause.NONE, lines, effective_lineheight

        # Fallback to confirmed min_font_size
        lines = self._estimate_lines(height, rc_min, min_font_size, effective_lineheight)
        return True, min_font_size, OverflowCause.NONE, lines, effective_lineheight

    def _estimate_lines(
        self,
        box_height: float,
        rc: float,
        font_size: float,
        lineheight: float,
    ) -> int:
        """Estimate line count from bounding box height and leftover vertical space."""
        used_height = max(0.0, box_height - rc)
        line_height_pt = max(1.0, font_size * lineheight)
        return max(1, round(used_height / line_height_pt))

    def _classify_overflow_cause(
        self,
        text: str,
        box_width: float,
        min_font_size: float,
    ) -> OverflowCause:
        """Classify why text failed to fit within bounds at minimum font floor."""
        try:
            tokens = text.split()
            for token in tokens:
                token_width = self.font_manager.measure_text_length(token, fontsize=min_font_size)
                if token_width > box_width:
                    return OverflowCause.OVERFLOW_WIDTH_AT_MIN_SIZE
            return OverflowCause.OVERFLOW_HEIGHT
        except Exception:
            return OverflowCause.OVERFLOW_UNDETERMINED


def parse_color(color_val: int | str | None) -> tuple[float, float, float]:
    """Parse color into normalized RGB tuple (0.0 to 1.0)."""
    if color_val is None:
        return (0.0, 0.0, 0.0)

    if isinstance(color_val, int):
        r = ((color_val >> 16) & 0xFF) / 255.0
        g = ((color_val >> 8) & 0xFF) / 255.0
        b = (color_val & 0xFF) / 255.0
        return (r, g, b)

    if isinstance(color_val, str):
        c = color_val.strip()
        if c.startswith("#"):
            c = c[1:]
        if len(c) == 6:
            try:
                r = int(c[0:2], 16) / 255.0
                g = int(c[2:4], 16) / 255.0
                b = int(c[4:6], 16) / 255.0
                return (r, g, b)
            except ValueError:
                pass

    return (0.0, 0.0, 0.0)
