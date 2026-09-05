"""Adaptive Typesetting and Multi-Space Constraint Solver for LayoutLingua.

Solves the multi-parameter typesetting optimization problem (font scaling, line spacing,
word wrapping, and multi-region spillover).
Addresses BabelDOC #89 (multi-available-space typesetting) and Vietnamese diacritic headroom.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple


@dataclass
class TypesettingConstraints:
    """Geometric and typographic constraints for a text block."""
    box_width: float
    box_height: float
    available_height_below: float = 0.0
    original_font_size: float = 10.0
    min_font_scale: float = 0.70
    line_height_ratio: float = 1.22
    diacritic_headroom: float = 1.8  # Minimum clearance above uppercase Latin/Vietnamese characters
    padding: float = 1.0


@dataclass
class TypesettingSolution:
    """Result of adaptive typesetting optimization."""
    font_size: float
    line_height: float
    lines: List[str]
    total_height: float
    spillover_used: float
    fits: bool
    scale_ratio: float


def word_wrap_text(
    text: str,
    font_size: float,
    max_width: float,
    measure_char: Callable[[str, float], float],
) -> Tuple[bool, List[str]]:
    """Wrap words into lines fitting within max_width."""
    words = text.split()
    if not words:
        return True, []

    space_w = measure_char(" ", font_size)
    lines: List[str] = []
    cur_line = ""
    cur_w = 0.0

    for w in words:
        word_w = sum(measure_char(ch, font_size) for ch in w)
        if word_w > max_width:
            # Word itself is wider than the allowed box width
            return False, []

        if not cur_line:
            cur_line = w
            cur_w = word_w
        else:
            if cur_w + space_w + word_w <= max_width:
                cur_line += " " + w
                cur_w += space_w + word_w
            else:
                lines.append(cur_line)
                cur_line = w
                cur_w = word_w

    if cur_line:
        lines.append(cur_line)

    return True, lines


def solve_adaptive_typesetting(
    text: str,
    constraints: TypesettingConstraints,
    measure_char: Callable[[str, float], float],
) -> TypesettingSolution:
    """Solve optimal font size, line wrapping, and multi-region spillover.

    First attempts to fit within the primary box at 100% font size.
    If overflow occurs, gradually lowers font size down to min_font_scale.
    If still overflowing, utilizes available_height_below (BabelDOC #89).
    If it still cannot fit, returns fits=False (fail-closed signal).
    """
    usable_w = max(4.0, constraints.box_width - 2 * constraints.padding)
    primary_h = max(4.0, constraints.box_height - 2 * constraints.padding)
    total_allowed_h = primary_h + max(0.0, constraints.available_height_below)

    orig_size = constraints.original_font_size
    min_size = orig_size * constraints.min_font_scale

    # Search from scale 1.0 down to min_font_scale in discrete steps
    steps = 10
    best_solution: Optional[TypesettingSolution] = None

    for i in range(steps + 1):
        scale = 1.0 - (1.0 - constraints.min_font_scale) * (i / steps)
        cand_size = orig_size * scale
        line_h = cand_size * constraints.line_height_ratio + constraints.diacritic_headroom

        possible, lines = word_wrap_text(text, cand_size, usable_w, measure_char)
        if not possible or not lines:
            continue

        needed_h = len(lines) * line_h

        # Prefer fitting inside primary box without using spillover
        if needed_h <= primary_h:
            return TypesettingSolution(
                font_size=cand_size,
                line_height=line_h,
                lines=lines,
                total_height=needed_h,
                spillover_used=0.0,
                fits=True,
                scale_ratio=scale,
            )

        # Allow spillover into available height below if within total_allowed_h
        if needed_h <= total_allowed_h:
            spill = needed_h - primary_h
            if best_solution is None or scale > best_solution.scale_ratio:
                best_solution = TypesettingSolution(
                    font_size=cand_size,
                    line_height=line_h,
                    lines=lines,
                    total_height=needed_h,
                    spillover_used=spill,
                    fits=True,
                    scale_ratio=scale,
                )

    if best_solution is not None:
        return best_solution

    # Unfit even at minimum scale with maximum spillover
    _, fallback_lines = word_wrap_text(text, min_size, usable_w, measure_char)
    return TypesettingSolution(
        font_size=min_size,
        line_height=min_size * constraints.line_height_ratio,
        lines=fallback_lines or [text],
        total_height=len(fallback_lines or [text]) * min_size * 1.25,
        spillover_used=constraints.available_height_below,
        fits=False,
        scale_ratio=constraints.min_font_scale,
    )
