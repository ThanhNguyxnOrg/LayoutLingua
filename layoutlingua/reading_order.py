"""Layout-aware Reading Order Inference Engine for LayoutLingua.

Implements column-aware gutter detection and topological sorting on spatial relation
graphs. Prevents multi-column text leakage in scientific and multi-column documents.
Inspired by Surya, Marker, and Docling reading order pipelines.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class LayoutBox:
    """Generic bounding box for reading order calculation."""
    id: str
    x0: float
    y0: float
    x1: float
    y1: float
    cls: int = -1
    text: str = ""

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2.0


def detect_column_gutters(
    boxes: Sequence[LayoutBox],
    page_width: float,
    min_gutter_width: float = 12.0,
    min_box_count: int = 4,
) -> list[float]:
    """Detect vertical whitespace gutters dividing multi-column layouts (2 or 3 columns).

    Returns:
        List of x-coordinates marking column boundaries, sorted ascending.
    """
    if len(boxes) < min_box_count or page_width <= 0:
        return []

    # Exclude headers, footers, and full-width banners (> 70% page width)
    filtered = [
        b for b in boxes
        if b.width < page_width * 0.70 and b.width > 15.0
    ]
    if len(filtered) < min_box_count:
        return []

    # Scan candidate gutters across 15% to 85% of page width
    x_min = page_width * 0.15
    x_max = page_width * 0.85
    resolution = 140
    step = (x_max - x_min) / resolution
    max_cross = max(1, int(len(filtered) * 0.05))

    clean_runs: list[tuple[float, float]] = []
    current_start: float | None = None
    for i in range(resolution + 1):
        x = x_min + i * step
        intersections = sum(1 for b in filtered if b.x0 <= x <= b.x1)
        if intersections <= max_cross:
            if current_start is None:
                current_start = x
        else:
            if current_start is not None:
                if x - current_start >= min_gutter_width:
                    clean_runs.append((current_start, x))
                current_start = None
    if current_start is not None and (x_max - current_start) >= min_gutter_width:
        clean_runs.append((current_start, x_max))

    gutters: list[float] = []
    for start, end in clean_runs:
        center = (start + end) / 2.0
        left_count = sum(1 for b in filtered if b.x1 <= center)
        right_count = sum(1 for b in filtered if b.x0 >= center)
        if left_count >= 2 and right_count >= 2:
            gutters.append(center)

    # Filter out redundant gutters that are too close to each other (< 18% width)
    if len(gutters) > 1:
        merged = [gutters[0]]
        for g in gutters[1:]:
            if g - merged[-1] >= page_width * 0.18:
                middle_count = sum(1 for b in filtered if merged[-1] <= b.center_x <= g)
                if middle_count >= 2:
                    merged.append(g)
        gutters = merged

    return gutters


def infer_reading_order_indices(
    boxes: Sequence[LayoutBox],
    page_width: float,
    page_height: float,
) -> list[int]:
    """Infer optimal reading order sequence using a Spatial DAG and Topological Sort.

    Steps:
    1. Identify full-width spanning blocks (e.g. Title, Abstract, full-width Figure/Table).
    2. Spanning blocks partition the page vertically into slices.
    3. Detect column whitespace gutters (supporting 2-column and 3-column layouts).
    4. Construct directed precedence edges (Spatial DAG):
       - Spanning block -> blocks in the slice beneath it.
       - Slices ordered top-to-bottom.
       - Within a slice: left column blocks -> right column blocks.
       - Within a column: upper blocks -> lower blocks.
    5. Run Kahn's Topological Sort to produce a deterministic reading order.
    """
    if not boxes:
        return []

    gutters = detect_column_gutters(boxes, page_width)

    # Partition blocks into spanning blocks vs column blocks
    spanning_indices = []
    column_indices = []
    for idx, b in enumerate(boxes):
        if b.width > page_width * 0.70:
            spanning_indices.append(idx)
        else:
            column_indices.append(idx)

    # Sort spanning blocks strictly top-to-bottom (higher y1 first in PDF coords)
    spanning_indices.sort(key=lambda idx: -boxes[idx].y1)

    # Assign column blocks into slices defined by spanning blocks
    slices: list[dict[str, Any]] = []
    if not spanning_indices:
        slices.append({"spanner": None, "boxes": column_indices})
    else:
        top_spanner_y = boxes[spanning_indices[0]].y1
        above = [i for i in column_indices if boxes[i].y0 >= top_spanner_y]
        if above:
            slices.append({"spanner": None, "boxes": above})

        for s_idx, spanner_i in enumerate(spanning_indices):
            cur_y0 = boxes[spanner_i].y0
            next_y1 = (
                boxes[spanning_indices[s_idx + 1]].y1
                if s_idx + 1 < len(spanning_indices)
                else -1.0
            )
            in_slice = [
                i for i in column_indices
                if cur_y0 >= boxes[i].center_y > next_y1
            ]
            slices.append({"spanner": spanner_i, "boxes": in_slice})

    # Construct Spatial DAG
    n = len(boxes)
    adj: dict[int, set[int]] = {i: set() for i in range(n)}

    import bisect

    for s_idx, s in enumerate(slices):
        spanner_idx = s["spanner"]
        slice_boxes = s["boxes"]

        # Spanner precedes all column boxes in its slice
        if spanner_idx is not None:
            for b_idx in slice_boxes:
                adj[spanner_idx].add(b_idx)

        # All boxes in this slice precede spanners in subsequent slices
        if s_idx + 1 < len(slices):
            next_spanner = slices[s_idx + 1]["spanner"]
            if next_spanner is not None:
                if spanner_idx is not None:
                    adj[spanner_idx].add(next_spanner)
                for b_idx in slice_boxes:
                    adj[b_idx].add(next_spanner)

        if not gutters:
            # Single column within slice: sort top-to-bottom
            sorted_slice = sorted(slice_boxes, key=lambda i: (-boxes[i].y1, boxes[i].x0))
            for i in range(len(sorted_slice) - 1):
                adj[sorted_slice[i]].add(sorted_slice[i + 1])
        else:
            # Multi-column within slice: partition into columns
            cols: list[list[int]] = [[] for _ in range(len(gutters) + 1)]
            for b_idx in slice_boxes:
                c_idx = bisect.bisect_right(gutters, boxes[b_idx].center_x)
                cols[c_idx].append(b_idx)

            # Left column precedes right column
            for c_i in range(len(cols) - 1):
                for left_b in cols[c_i]:
                    for right_b in cols[c_i + 1]:
                        adj[left_b].add(right_b)

            # Within each column: top precedes bottom
            for col_boxes in cols:
                sorted_col = sorted(col_boxes, key=lambda i: (-boxes[i].y1, boxes[i].x0))
                for i in range(len(sorted_col) - 1):
                    adj[sorted_col[i]].add(sorted_col[i + 1])

    # Kahn's Topological Sort
    in_degree = {i: 0 for i in range(n)}
    for neighbors in adj.values():
        for v in neighbors:
            in_degree[v] += 1

    ready = [i for i in range(n) if in_degree[i] == 0]
    result_indices: list[int] = []

    while ready:
        # Tie-breaker: prioritize higher y1, then lower x0
        ready.sort(key=lambda i: (-boxes[i].y1, boxes[i].x0))
        node = ready.pop(0)
        result_indices.append(node)

        for neighbor in sorted(adj[node]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                ready.append(neighbor)

    # Fallback safety against cycles: append any remaining nodes
    if len(result_indices) < n:
        seen = set(result_indices)
        remaining = [i for i in range(n) if i not in seen]
        remaining.sort(key=lambda i: (-boxes[i].y1, boxes[i].x0))
        result_indices.extend(remaining)

    return result_indices


def sort_boxes_by_reading_order(
    boxes: list[LayoutBox],
    page_width: float,
    page_height: float,
) -> list[LayoutBox]:
    """Return a new list of LayoutBoxes sorted in natural reading order."""
    order = infer_reading_order_indices(boxes, page_width, page_height)
    return [boxes[i] for i in order]
