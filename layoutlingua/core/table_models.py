"""Pure-Python geometric domain models for tables and cells.

Decoupled from PyMuPDF and typesetting engines to preserve architecture boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BorderLine:
    """Straight line segment representing a physical vector grid divider."""

    p1: tuple[float, float]
    p2: tuple[float, float]
    width: float


@dataclass(frozen=True)
class CellInsets:
    """Calculated padding insets based on physical vector border stroke widths."""

    top: float
    bottom: float
    left: float
    right: float


def _safe_stroke_inset(raw_w: Any) -> float:
    """Calculate single-side inset according to spec: p_side = max(1.0, w/2 + 0.5)."""
    try:
        w = float(raw_w) if raw_w is not None else 1.0
    except (TypeError, ValueError):
        w = 1.0
    w = max(0.0, w)
    return max(1.0, (w / 2.0) + 0.5)


def compute_stroke_aware_insets(
    border_widths: dict[str, float] | None = None,
) -> CellInsets:
    """Compute stroke-aware padding insets for all 4 sides.

    Spec formula: p_side = max(1.0, w/2 + 0.5)
    """
    widths = border_widths or {}
    top = _safe_stroke_inset(widths.get("top", 1.0))
    bottom = _safe_stroke_inset(widths.get("bottom", 1.0))
    left = _safe_stroke_inset(widths.get("left", 1.0))
    right = _safe_stroke_inset(widths.get("right", 1.0))
    return CellInsets(top=top, bottom=bottom, left=left, right=right)


def compute_cell_inner_bbox(
    cell_bbox: tuple[float, float, float, float],
    border_widths: dict[str, float] | None = None,
) -> tuple[float, float, float, float] | None:
    """Compute effective inner bounding box for text within cell geometry.

    Returns None if cell is too narrow or shallow for stroke-aware insets (fail-closed).
    """
    insets = compute_stroke_aware_insets(border_widths)
    x0, y0, x1, y1 = cell_bbox
    ix0 = x0 + insets.left
    iy0 = y0 + insets.top
    ix1 = x1 - insets.right
    iy1 = y1 - insets.bottom

    if ix1 <= ix0 or iy1 <= iy0:
        return None

    return (ix0, iy0, ix1, iy1)


@dataclass(frozen=True)
class CellGeometry:
    """Immutable geometric coordinates and border attributes of a single grid cell."""

    cell_id: str  # f"p{page}_t{table}_r{row}_c{col}"
    row_idx: int
    col_idx: int
    cell_bbox: tuple[float, float, float, float]
    border_widths: dict[str, float]  # {"top": w, "bottom": w, "left": w, "right": w}

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.cell_bbox

    @property
    def insets(self) -> CellInsets:
        """Compute stroke-aware padding insets according to p_side = max(1.0, w/2 + 0.5)."""
        return compute_stroke_aware_insets(self.border_widths)

    def compute_inner_bbox(self) -> tuple[float, float, float, float] | None:
        """Compute effective inner bounding box for text within this cell, or None if degenerate."""
        return compute_cell_inner_bbox(self.cell_bbox, self.border_widths)


@dataclass(frozen=True)
class TableGrid:
    """Immutable topological and geometric grid model of a corroborated table."""

    table_id: str  # f"p{page}_t{table}"
    bbox: tuple[float, float, float, float]
    row_count: int
    col_count: int
    cells: dict[str, CellGeometry]  # keyed by cell_id
