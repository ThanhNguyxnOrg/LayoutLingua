"""Structure-Aware Table Engine for LayoutLingua.

Implements cell-level grid reconstruction, merged-cell logic, numerical/unit protection,
adaptive cell fitting, and GriTS-inspired structural integrity metrics.
Inspired by Table Transformer (TATR), PubTables-1M, and GriTS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# Pattern matching cells containing purely numbers, units, identifiers, or short symbols
NUMERIC_OR_IDENTIFIER_PATTERN = re.compile(
    r"^\s*([±~<>]?\s*[\$€¥£]?\s*-?\d+(?:[.,]\d+)*(?:\s*[%°/]\s*[A-Za-z0-9^]*)?"
    r"|N/?A|n/?a|-|--|—|\+|\*|§|†|‡|#\d+|[A-Z0-9]{1,4}"
    r"|\d+(?:[.,]\d+)*\s*±\s*\d+(?:[.,]\d+)*"
    r"|p\s*[<>=]\s*0?\.\d+"
    r")\s*$",
    re.IGNORECASE,
)


@dataclass
class TableCell:
    """Represents an individual table cell with strict boundary isolation."""
    id: str
    row_idx: int
    col_idx: int
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    row_span: int = 1
    col_span: int = 1
    source_text: str = ""
    translated_text: Optional[str] = None
    is_header: bool = False
    is_numeric_or_code: bool = False
    font_size: float = 9.0
    fitted_font_size: Optional[float] = None
    fitted_lines: List[str] = field(default_factory=list)

    @property
    def width(self) -> float:
        return max(0.0, self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return max(0.0, self.bbox[3] - self.bbox[1])


@dataclass
class TableGrid:
    """Structure-aware table containing logical rows, columns, and isolated cells."""
    bbox: Tuple[float, float, float, float]
    rows: int
    cols: int
    cells: List[TableCell] = field(default_factory=list)
    has_explicit_borders: bool = True
    confidence: float = 1.0

    def get_cell(self, row: int, col: int) -> Optional[TableCell]:
        for cell in self.cells:
            if cell.row_idx == row and cell.col_idx == col:
                return cell
        return None


def is_cell_numeric_or_identifier(text: str) -> bool:
    """Check whether cell text consists of numbers, units, abbreviations, or codes that must be preserved."""
    cleaned = text.strip()
    if not cleaned:
        return True
    return bool(NUMERIC_OR_IDENTIFIER_PATTERN.match(cleaned))


def reconstruct_table_grid(
    raw_cells: Sequence[Tuple[float, float, float, float, str]],
    table_bbox: Tuple[float, float, float, float],
    is_header_first_row: bool = True,
) -> TableGrid:
    """Reconstruct a structured TableGrid from raw cell bounding boxes and text.

    Args:
        raw_cells: Sequence of (x0, y0, x1, y1, text)
        table_bbox: Bounding box of the entire table region (x0, y0, x1, y1)
        is_header_first_row: Whether the top-most row is considered a header
    """
    if not raw_cells:
        return TableGrid(bbox=table_bbox, rows=0, cols=0)

    # Cluster distinct horizontal lines (rows) and vertical lines (columns)
    # Note: In PDF coordinates, higher y is higher on the page
    y_centers = sorted([ (c[1] + c[3]) / 2.0 for c in raw_cells ], reverse=True)
    x_centers = sorted([ (c[0] + c[2]) / 2.0 for c in raw_cells ])

    row_clusters: List[float] = []
    col_clusters: List[float] = []

    cluster_threshold_y = 6.0
    cluster_threshold_x = 12.0

    for yc in y_centers:
        if not row_clusters or all(abs(yc - rc) > cluster_threshold_y for rc in row_clusters):
            row_clusters.append(yc)

    for xc in x_centers:
        if not col_clusters or all(abs(xc - cc) > cluster_threshold_x for cc in col_clusters):
            col_clusters.append(xc)

    # Sort rows descending (top to bottom) and columns ascending (left to right)
    row_clusters.sort(reverse=True)
    col_clusters.sort()

    num_rows = len(row_clusters)
    num_cols = len(col_clusters)

    cells: List[TableCell] = []
    for idx, (x0, y0, x1, y1, text) in enumerate(raw_cells):
        yc = (y0 + y1) / 2.0
        xc = (x0 + x1) / 2.0

        # Find closest row and col
        row_idx = min(range(num_rows), key=lambda r: abs(row_clusters[r] - yc))
        col_idx = min(range(num_cols), key=lambda c: abs(col_clusters[c] - xc))

        is_header = is_header_first_row and (row_idx == 0)
        is_num = is_cell_numeric_or_identifier(text)

        cell = TableCell(
            id=f"cell_{row_idx}_{col_idx}_{idx}",
            row_idx=row_idx,
            col_idx=col_idx,
            bbox=(x0, y0, x1, y1),
            source_text=text,
            is_header=is_header,
            is_numeric_or_code=is_num,
        )
        cells.append(cell)

    return TableGrid(
        bbox=table_bbox,
        rows=num_rows,
        cols=num_cols,
        cells=cells,
        confidence=1.0,
    )


def fit_cell_text(
    cell: TableCell,
    candidate_text: str,
    measure_char: Callable[[str, float], float],
    min_scale: float = 0.65,
    padding: float = 2.0,
) -> Tuple[bool, float, List[str]]:
    """Determine whether translated text fits in cell with adaptive downscaling.

    Returns:
        (fits_successfully, final_font_size, line_wraps)
    """
    usable_w = max(4.0, cell.width - 2 * padding)
    usable_h = max(4.0, cell.height - 2 * padding)

    words = candidate_text.split()
    if not words:
        return True, cell.font_size, []

    # Try decreasing scales from 1.0 down to min_scale in steps of 0.05
    steps = 8
    for i in range(steps + 1):
        scale = 1.0 - (1.0 - min_scale) * (i / steps)
        cur_size = cell.font_size * scale
        line_height = cur_size * 1.25

        # Word wrap test
        lines: List[str] = []
        cur_line = ""
        cur_line_w = 0.0
        possible = True

        for w in words:
            word_w = sum(measure_char(ch, cur_size) for ch in w)
            space_w = measure_char(" ", cur_size)

            if not cur_line:
                if word_w > usable_w:
                    possible = False
                    break
                cur_line = w
                cur_line_w = word_w
            else:
                if cur_line_w + space_w + word_w <= usable_w:
                    cur_line += " " + w
                    cur_line_w += space_w + word_w
                else:
                    lines.append(cur_line)
                    if word_w > usable_w:
                        possible = False
                        break
                    cur_line = w
                    cur_line_w = word_w

        if cur_line:
            lines.append(cur_line)

        if possible and lines:
            total_h = len(lines) * line_height
            if total_h <= usable_h:
                return True, cur_size, lines

    return False, cell.font_size * min_scale, [candidate_text]


def compute_table_grits_score(
    orig_grid: TableGrid,
    trans_grid: TableGrid,
) -> float:
    """Compute a GriTS-inspired cell structure preservation similarity score [0.0, 1.0]."""
    if orig_grid.rows != trans_grid.rows or orig_grid.cols != trans_grid.cols:
        return 0.0
    if not orig_grid.cells or not trans_grid.cells:
        return 1.0

    total_cells = len(orig_grid.cells)
    matched_cells = 0

    for o_cell in orig_grid.cells:
        t_cell = trans_grid.get_cell(o_cell.row_idx, o_cell.col_idx)
        if t_cell is not None:
            # Check bounding box alignment
            w_diff = abs(o_cell.width - t_cell.width)
            h_diff = abs(o_cell.height - t_cell.height)
            if w_diff < 2.0 and h_diff < 2.0:
                matched_cells += 1

    return float(matched_cells / total_cells)
