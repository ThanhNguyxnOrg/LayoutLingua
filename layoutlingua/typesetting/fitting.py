"""Adaptive font fitting and text bounding box measurement."""

from __future__ import annotations

import pymupdf

from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.models import TypesetOptions


class TextFitTester:
    """Evaluates whether text fits within a bounding box at varying font scales."""

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
    ) -> tuple[bool, float]:
        """Determine if text fits within rect using bounded adaptive font shrinkage.
        
        Returns:
            (fits, final_font_size)
            If fits is True, final_font_size is the fitted size >= min_size.
            If fits is False, final_font_size is the original font size.
        """
        x0, y0, x1, y1 = rect
        width = x1 - x0
        height = y1 - y0

        if width <= 0 or height <= 0 or not text.strip():
            return False, orig_font_size

        min_font_size = max(options.min_font_pt, options.min_font_scale * orig_font_size)
        step_factor = options.step_down_ratio

        # Test at original size and stepped sizes
        current_size = orig_font_size
        test_rect = pymupdf.Rect(x0, y0, x1, y1)

        while current_size >= min_font_size - 1e-4:
            # page.insert_textbox returns >= 0 if all text fit, < 0 if text overflowed
            rc = self._page.insert_textbox(
                test_rect,
                text,
                fontsize=current_size,
                fontname=self.font_name,
                fontfile=str(self.font_manager.font_path),
            )
            if rc >= 0:
                return True, current_size

            next_size = current_size * step_factor
            if next_size >= current_size - 0.1:
                next_size = current_size - 0.5
            current_size = next_size

        # Test at exact floor
        rc = self._page.insert_textbox(
            test_rect,
            text,
            fontsize=min_font_size,
            fontname=self.font_name,
            fontfile=str(self.font_manager.font_path),
        )
        if rc >= 0:
            return True, min_font_size

        return False, orig_font_size


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
