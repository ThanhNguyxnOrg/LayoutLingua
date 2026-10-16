"""Adaptive font fitting using binary search, dynamic lineheight, and overflow classification."""

from __future__ import annotations

import pymupdf

from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.models import OverflowCause, TypesetOptions


class TextFitTester:
    """Evaluates whether text fits within a bounding box using precision binary search."""

    def __init__(self, font_manager: FontManager, font_name: str = "DejaVuSans") -> None:
        self.font_manager = font_manager
        self.font_name = font_name
        self._doc = pymupdf.open()
        self._page = self._doc.new_page(width=1000, height=1000)
        self.font_manager.register_on_page(self._page, font_name=self.font_name)

    def test_fit(
        self,
        rect: tuple[float, float, float, float],
        text: str,
        orig_font_size: float,
        options: TypesetOptions,
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

        min_font_size = max(options.min_font_pt, options.min_font_scale * orig_font_size)
        test_rect = pymupdf.Rect(x0, y0, x1, y1)

        fontfile_arg = (
            None
            if self.font_name in ("china-s", "china-t", "japan", "korea")
            else str(self.font_manager.font_path)
        )

        # 1. Test original size
        rc_orig = self._page.insert_textbox(
            test_rect,
            text,
            fontsize=orig_font_size,
            fontname=self.font_name,
            fontfile=fontfile_arg,
            lineheight=effective_lineheight,
        )
        if rc_orig >= 0:
            lines = self._estimate_lines(height, rc_orig, orig_font_size, effective_lineheight)
            return True, orig_font_size, OverflowCause.NONE, lines, effective_lineheight

        # 2. Test minimum font size floor
        rc_min = self._page.insert_textbox(
            test_rect,
            text,
            fontsize=min_font_size,
            fontname=self.font_name,
            fontfile=fontfile_arg,
            lineheight=effective_lineheight,
        )
        if rc_min < 0:
            # Overflow event at minimum scale: classify cause
            cause = self._classify_overflow_cause(text, width, min_font_size)
            return False, orig_font_size, cause, 0, effective_lineheight

        # 3. Binary Search in [min_font_size, orig_font_size]
        low = min_font_size
        high = orig_font_size
        best_size = min_font_size
        best_rc = rc_min
        iteration = 0

        while (high - low) > options.binary_search_epsilon and iteration < options.max_search_iterations:
            mid = (low + high) / 2.0
            rc = self._page.insert_textbox(
                test_rect,
                text,
                fontsize=mid,
                fontname=self.font_name,
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
        confirm_rc = self._page.insert_textbox(
            test_rect,
            text,
            fontsize=best_size,
            fontname=self.font_name,
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
