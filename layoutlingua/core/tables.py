"""Table detection, vector primitive filtering, and grid validation.

Slice 4C.2: Corroborates PyMuPDF table candidates against physical vector
drawing primitives, enforcing strict stroke verification and fail-closed
rejection semantics.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import pymupdf

from layoutlingua.core.ir import PageIR, TextBlock
from layoutlingua.core.table_models import BorderLine, CellGeometry, TableGrid


def extract_valid_vector_segments(
    drawings: list[dict[str, Any]],
) -> list[tuple[float, float, float, float, float]]:
    """Extract valid orthogonal vector border segments from PDF drawings.

    Admits only drawings with stroke components ('s', 'fs' or color with width > 0).
    Decomposes lines ('l') and rectangles ('re'). Strictly excludes bezier
    curves ('c') and quad curves ('qu').

    Returns:
        List of (x1, y1, x2, y2, width) tuples where x1 <= x2 and y1 <= y2.
    """
    segments: list[tuple[float, float, float, float, float]] = []

    for drawing in drawings:
        d_type = drawing.get("type", "")
        has_stroke_type = d_type in ("s", "fs")
        has_stroke_color = drawing.get("color") is not None and drawing.get("width", 0) > 0

        # Pure fill drawings ('f') without stroke color are strictly ignored
        if not (has_stroke_type or has_stroke_color):
            continue

        raw_width = drawing.get("width", 1.0)
        try:
            width = float(raw_width) if raw_width is not None and raw_width > 0 else 1.0
        except (TypeError, ValueError):
            width = 1.0

        for item in drawing.get("items", []):
            if not item:
                continue
            item_type = item[0]

            if item_type == "l":
                # Line segment: ('l', Point_p1, Point_p2)
                p1 = item[1]
                p2 = item[2]
                dx = abs(p1.x - p2.x)
                dy = abs(p1.y - p2.y)

                # Admit if collinear with horizontal or vertical axis (<= 1.0 pt tolerance)
                if dx <= 1.0 or dy <= 1.0:
                    x1 = min(p1.x, p2.x)
                    x2 = max(p1.x, p2.x)
                    y1 = min(p1.y, p2.y)
                    y2 = max(p1.y, p2.y)
                    # Snap near-orthogonal lines to perfectly orthogonal
                    if dx <= 1.0:
                        x_mid = (x1 + x2) / 2.0
                        x1 = x_mid
                        x2 = x_mid
                    if dy <= 1.0:
                        y_mid = (y1 + y2) / 2.0
                        y1 = y_mid
                        y2 = y_mid
                    segments.append((x1, y1, x2, y2, width))

            elif item_type == "re":
                # Rectangle: ('re', Rect_r, ...)
                r = pymupdf.Rect(item[1])
                # Decompose into 4 orthogonal boundary edge segments
                segments.append((r.x0, r.y0, r.x1, r.y0, width))  # top
                segments.append((r.x0, r.y1, r.x1, r.y1, width))  # bottom
                segments.append((r.x0, r.y0, r.x0, r.y1, width))  # left
                segments.append((r.x1, r.y0, r.x1, r.y1, width))  # right

            # item_type in ('c', 'qu') curves are strictly excluded

    return segments


def _compute_edge_coverage(
    edge: tuple[float, float, float, float],
    segments: list[tuple[float, float, float, float, float]],
    tolerance_pt: float,
) -> tuple[float, float]:
    """Compute physical vector stroke coverage and average width along an edge.

    Edge: (x1, y1, x2, y2) where x1 <= x2 and y1 <= y2.
    Returns:
        (coverage_ratio, average_width)
    """
    x1, y1, x2, y2 = edge
    dx = x2 - x1
    dy = y2 - y1
    is_horizontal = dy <= dx

    intervals: list[tuple[float, float, float]] = []

    if is_horizontal:
        length = dx
        if length <= 0.1:
            return 1.0, 1.0
        y_target = (y1 + y2) / 2.0

        for sx1, sy1, sx2, sy2, sw in segments:
            # Segment must be approximately horizontal
            if abs(sy2 - sy1) > 1.0:
                continue
            sy_mid = (sy1 + sy2) / 2.0
            if abs(sy_mid - y_target) > tolerance_pt:
                continue
            # Overlap along X
            overlap_start = max(x1, sx1)
            overlap_end = min(x2, sx2)
            if overlap_end > overlap_start:
                intervals.append((overlap_start, overlap_end, sw))
    else:
        length = dy
        if length <= 0.1:
            return 1.0, 1.0
        x_target = (x1 + x2) / 2.0

        for sx1, sy1, sx2, sy2, sw in segments:
            # Segment must be approximately vertical
            if abs(sx2 - sx1) > 1.0:
                continue
            sx_mid = (sx1 + sx2) / 2.0
            if abs(sx_mid - x_target) > tolerance_pt:
                continue
            # Overlap along Y
            overlap_start = max(y1, sy1)
            overlap_end = min(y2, sy2)
            if overlap_end > overlap_start:
                intervals.append((overlap_start, overlap_end, sw))

    if not intervals:
        return 0.0, 1.0

    # Sort intervals and merge overlapping or adjacent (gap <= tolerance_pt)
    intervals.sort(key=lambda it: it[0])
    merged: list[tuple[float, float]] = []
    widths: list[float] = []

    curr_start, curr_end, curr_w = intervals[0]
    widths.append(curr_w)

    for next_start, next_end, next_w in intervals[1:]:
        if next_start <= curr_end + tolerance_pt:
            curr_end = max(curr_end, next_end)
            widths.append(next_w)
        else:
            merged.append((curr_start, curr_end))
            curr_start, curr_end = next_start, next_end
            widths.append(next_w)
    merged.append((curr_start, curr_end))

    covered_length = sum(b - a for a, b in merged if b > a)
    coverage = min(1.0, covered_length / length)
    avg_width = sum(widths) / len(widths) if widths else 1.0

    return coverage, avg_width


class TableGridValidator:
    """Validates PyMuPDF table candidates against vector drawing stroke primitives.

    Enforces:
    - Path and primitive-level stroke verification ('l' and 're' admitted, 'f'/'c' ignored)
    - Minimum edge coverage (>= 90%) within geometric tolerance (<= 2.0 pt)
    - Fail-closed rejection on unsupported/merged cells or weak vector corroboration
    """

    def __init__(
        self,
        tolerance_pt: float = 2.0,
        min_edge_coverage: float = 0.90,
    ) -> None:
        self.tolerance_pt = tolerance_pt
        self.min_edge_coverage = min_edge_coverage

    def validate_page_tables(
        self,
        page: pymupdf.Page,
        page_ir: PageIR,
    ) -> list[TableGrid]:
        """Detect and validate tables on page, attaching TableGrid metadata or tagging rejections."""
        finder = page.find_tables()
        if not finder or not finder.tables:
            return []

        drawings = page.get_drawings()
        segments = extract_valid_vector_segments(drawings)

        validated_grids: list[TableGrid] = []

        for t_idx, tab in enumerate(finder.tables):
            # 1. Dimension constraints: reject 1x1 or degenerate tables
            rows = tab.row_count
            cols = tab.col_count
            valid_dims = (rows >= 1 and cols >= 2) or (rows >= 2 and cols >= 1)
            if not valid_dims:
                self._reject_table(tab, page_ir)
                continue

            # 2. Check for missing / merged cells (row.cells containing None) -> fail-closed
            has_merged_or_missing = False
            for r_idx in range(rows):
                row_cells = tab.rows[r_idx].cells
                for c_idx in range(cols):
                    if row_cells[c_idx] is None:
                        has_merged_or_missing = True
                        break
                if has_merged_or_missing:
                    break

            if has_merged_or_missing:
                self._reject_table(tab, page_ir)
                continue

            # 3. Outer border verification: all 4 sides of table.bbox must match vector segments
            tx0, ty0, tx1, ty1 = tab.bbox
            outer_edges = [
                (tx0, ty0, tx1, ty0),  # top
                (tx0, ty1, tx1, ty1),  # bottom
                (tx0, ty0, tx0, ty1),  # left
                (tx1, ty0, tx1, ty1),  # right
            ]

            outer_valid = True
            for edge in outer_edges:
                cov, _ = _compute_edge_coverage(edge, segments, self.tolerance_pt)
                if cov < self.min_edge_coverage:
                    outer_valid = False
                    break

            if not outer_valid:
                self._reject_table(tab, page_ir)
                continue

            # 4. Internal cell dividers verification: >= 90% coverage per divider segment
            internal_valid = True
            cell_border_widths: dict[str, dict[str, float]] = {}

            for r in range(rows):
                for c in range(cols):
                    cell_bbox = tab.rows[r].cells[c]
                    cx0, cy0, cx1, cy1 = cell_bbox
                    cell_id = f"p{page_ir.page_number}_t{t_idx}_r{r}_c{c}"

                    # Top border
                    top_edge = (cx0, cy0, cx1, cy0)
                    cov_top, w_top = _compute_edge_coverage(top_edge, segments, self.tolerance_pt)
                    if r > 0 and cov_top < self.min_edge_coverage:
                        internal_valid = False
                        break

                    # Bottom border
                    bottom_edge = (cx0, cy1, cx1, cy1)
                    cov_bottom, w_bottom = _compute_edge_coverage(bottom_edge, segments, self.tolerance_pt)
                    if r < rows - 1 and cov_bottom < self.min_edge_coverage:
                        internal_valid = False
                        break

                    # Left border
                    left_edge = (cx0, cy0, cx0, cy1)
                    cov_left, w_left = _compute_edge_coverage(left_edge, segments, self.tolerance_pt)
                    if c > 0 and cov_left < self.min_edge_coverage:
                        internal_valid = False
                        break

                    # Right border
                    right_edge = (cx1, cy0, cx1, cy1)
                    cov_right, w_right = _compute_edge_coverage(right_edge, segments, self.tolerance_pt)
                    if c < cols - 1 and cov_right < self.min_edge_coverage:
                        internal_valid = False
                        break

                    cell_border_widths[cell_id] = {
                        "top": w_top,
                        "bottom": w_bottom,
                        "left": w_left,
                        "right": w_right,
                    }

                if not internal_valid:
                    break

            if not internal_valid:
                self._reject_table(tab, page_ir)
                continue

            # 5. Table validated! Construct TableGrid and CellGeometry
            cells: dict[str, CellGeometry] = {}
            for r in range(rows):
                for c in range(cols):
                    cell_bbox = tab.rows[r].cells[c]
                    cell_id = f"p{page_ir.page_number}_t{t_idx}_r{r}_c{c}"
                    b_widths = cell_border_widths.get(
                        cell_id,
                        {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
                    )
                    cg = CellGeometry(
                        cell_id=cell_id,
                        row_idx=r,
                        col_idx=c,
                        cell_bbox=(
                            float(cell_bbox[0]),
                            float(cell_bbox[1]),
                            float(cell_bbox[2]),
                            float(cell_bbox[3]),
                        ),
                        border_widths=b_widths,
                    )
                    cells[cell_id] = cg

            grid = TableGrid(
                table_id=f"p{page_ir.page_number}_t{t_idx}",
                bbox=(float(tx0), float(ty0), float(tx1), float(ty1)),
                row_count=rows,
                col_count=cols,
                cells=cells,
            )

            # Register in page_ir metadata
            tables_meta = page_ir.metadata.setdefault("tables", {})
            tables_meta[grid.table_id] = grid
            validated_grids.append(grid)

        return validated_grids

    def _reject_table(self, tab: Any, page_ir: PageIR) -> None:
        """Tag intersecting blocks as table_rejected and register in metadata (fail-closed)."""
        tx0, ty0, tx1, ty1 = tab.bbox

        # Register in rejected_table_bboxes
        rejected_bboxes = page_ir.metadata.setdefault("rejected_table_bboxes", [])
        rejected_bboxes.append((float(tx0), float(ty0), float(tx1), float(ty1)))

        # Tag intersecting text blocks and record in preserved_block_ids
        preserved_ids = page_ir.metadata.setdefault("preserved_block_ids", set())
        if isinstance(preserved_ids, list):
            preserved_ids = set(preserved_ids)
            page_ir.metadata["preserved_block_ids"] = preserved_ids

        for block in page_ir.blocks:
            bx0, by0, bx1, by1 = block.bbox
            if max(bx0, tx0) < min(bx1, tx1) and max(by0, ty0) < min(by1, ty1):
                block.block_type = "table_rejected"
                preserved_ids.add(block.block_id)
