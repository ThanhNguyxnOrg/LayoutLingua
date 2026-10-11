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
class CellGeometry:
    """Immutable geometric coordinates and border attributes of a single grid cell."""

    cell_id: str  # f"p{page}_t{table}_r{row}_c{col}"
    row_idx: int
    col_idx: int
    cell_bbox: tuple[float, float, float, float]
    border_widths: dict[str, float]  # {"top": w, "bottom": w, "left": w, "right": w}


@dataclass(frozen=True)
class TableGrid:
    """Immutable topological and geometric grid model of a corroborated table."""

    table_id: str  # f"p{page}_t{table}"
    bbox: tuple[float, float, float, float]
    row_count: int
    col_count: int
    cells: dict[str, CellGeometry]  # keyed by cell_id
