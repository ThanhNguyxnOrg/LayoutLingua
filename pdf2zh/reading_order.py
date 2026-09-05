"""Layout-aware Reading Order Inference Engine for LayoutLingua.

Implements column-aware gutter detection and topological sorting on spatial relation
graphs. Prevents multi-column text leakage in scientific and multi-column documents.
Inspired by Surya, Marker, and Docling reading order pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


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
) -> List[float]:
    """Detect vertical whitespace gutters dividing multi-column layouts.

    Returns:
        List of x-coordinates marking column boundaries.
    """
    if len(boxes) < min_box_count or page_width <= 0:
        return []

    # Exclude headers, footers, and full-width banners (> 70% page width)
    filtered = [
        b for b in boxes
        if b.width < page_width * 0.70 and b.width > 20.0
    ]
    if len(filtered) < min_box_count:
        return []

    # Check for 2-column layout around mid-page (35% to 65% of width)
    mid_min = page_width * 0.35
    mid_max = page_width * 0.65

    # Check how many boxes intersect candidate split points
    resolution = 50
    step = (mid_max - mid_min) / resolution
    best_split = None
    min_intersections = float("inf")

    for i in range(resolution):
        x = mid_min + i * step
        intersections = sum(1 for b in filtered if b.x0 <= x <= b.x1)
        if intersections < min_intersections:
            min_intersections = intersections
            best_split = x

    # If at the best split point, few or no boxes cross, we have a clear gutter
    if best_split is not None and min_intersections <= max(1, len(filtered) * 0.05):
        left_boxes = sum(1 for b in filtered if b.x1 <= best_split)
        right_boxes = sum(1 for b in filtered if b.x0 >= best_split)
        # Ensure balanced content on both sides
        if left_boxes >= 2 and right_boxes >= 2:
            return [best_split]

    return []


def infer_reading_order_indices(
    boxes: Sequence[LayoutBox],
    page_width: float,
    page_height: float,
) -> List[int]:
    """Infer the optimal reading order sequence of indices for a page's layout boxes.

    Approach:
    1. Identify full-width spanning blocks (e.g. Title, Abstract, full-width Figure/Table).
    2. Spanning blocks divide the page vertically into slices.
    3. Within each slice, if columns exist (left & right of a gutter):
       - Sort all left-column boxes top-to-bottom.
       - Sort all right-column boxes top-to-bottom.
    4. Chain: Slice 1 (Spanner -> Left Col -> Right Col) -> Slice 2 ...
    """
    if not boxes:
        return []

    gutters = detect_column_gutters(boxes, page_width)
    if not gutters:
        # Single column layout: top-to-bottom (higher y1 first), then left-to-right
        indices = list(range(len(boxes)))
        return sorted(
            indices,
            key=lambda idx: (
                -(round(boxes[idx].y1 / 8.0) * 8.0),
                boxes[idx].x0,
            ),
        )

    gutter_x = gutters[0]

    # Partition blocks into spanning blocks vs column blocks
    spanning_indices = []
    column_indices = []
    for idx, b in enumerate(boxes):
        if b.width > page_width * 0.70:
            spanning_indices.append(idx)
        else:
            column_indices.append(idx)

    # Sort spanning blocks strictly top-to-bottom (higher y1 first)
    spanning_indices.sort(key=lambda idx: -boxes[idx].y1)

    # Cutoffs defined by spanning blocks
    # Slice boundaries: from +infinity down to each spanner's y0, down to 0
    spanner_y_cutoffs = [boxes[idx].y0 for idx in spanning_indices]

    # Assign each column box to a slice
    # Slice 0: above first spanner (if any boxes exist there)
    # Slice k: between spanner k-1 and spanner k
    # Slice last: below all spanners
    slices: List[Dict[str, Any]] = []

    if not spanning_indices:
        slices.append({"spanner": None, "boxes": column_indices})
    else:
        # Check boxes above the top-most spanner
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
            # Column boxes between cur_y0 and next_y1
            in_slice = [
                i for i in column_indices
                if cur_y0 >= boxes[i].center_y > next_y1
            ]
            slices.append({"spanner": spanner_i, "boxes": in_slice})

    result_indices: List[int] = []

    for s in slices:
        if s["spanner"] is not None:
            result_indices.append(s["spanner"])

        slice_boxes = s["boxes"]
        left_col = [i for i in slice_boxes if boxes[i].center_x < gutter_x]
        right_col = [i for i in slice_boxes if boxes[i].center_x >= gutter_x]

        # Top-to-bottom in left column
        left_col.sort(key=lambda i: (-boxes[i].y1, boxes[i].x0))
        # Top-to-bottom in right column
        right_col.sort(key=lambda i: (-boxes[i].y1, boxes[i].x0))

        result_indices.extend(left_col)
        result_indices.extend(right_col)

    # Fallback safety: ensure all indices are present
    seen = set(result_indices)
    remaining = [i for i in range(len(boxes)) if i not in seen]
    if remaining:
        remaining.sort(key=lambda i: (-boxes[i].y1, boxes[i].x0))
        result_indices.extend(remaining)

    return result_indices


def sort_boxes_by_reading_order(
    boxes: List[LayoutBox],
    page_width: float,
    page_height: float,
) -> List[LayoutBox]:
    """Return a new list of LayoutBoxes sorted in natural reading order."""
    order = infer_reading_order_indices(boxes, page_width, page_height)
    return [boxes[i] for i in order]
