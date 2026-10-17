"""Column-aware reading order sorting for multi-column academic and technical PDFs.

Implements spatial clustering (XY-Cut inspired) to sort blocks into natural
human reading flow: Full-width headers -> Left column -> Right column -> Full-width footers.
"""

from __future__ import annotations

from typing import Sequence

from layoutlingua.core.ir import TextBlock


def sort_blocks_reading_order(
    blocks: Sequence[TextBlock], page_width: float = 595.0
) -> list[TextBlock]:
    """Sort text blocks into natural human reading order.

    Detects multi-column (e.g. 2-column) documents and sequences blocks
    column-by-column rather than purely top-to-bottom across the entire page.

    Args:
        blocks: Sequence of TextBlock items on a single page.
        page_width: Width of the page in points (default A4 width: 595.0).

    Returns:
        Sorted list of TextBlock items in human reading order.
    """
    if len(blocks) <= 1:
        return list(blocks)

    # Threshold for full-width blocks (e.g., Title, Abstract, full-width Tables/Figures)
    # A block spanning >= 60% of the printable page width is considered full-width
    full_width_threshold = page_width * 0.60
    mid_x = page_width / 2.0

    # Separate blocks into full-width band dividers vs multi-column body blocks
    # A block is classified as full-width if:
    # 1. Its width is >= full_width_threshold
    # 2. Or it substantially straddles the center line (crosses mid_x by >= 15% width on both sides)
    def _is_full_width(b: TextBlock) -> bool:
        w = b.bbox[2] - b.bbox[0]
        if w >= full_width_threshold:
            return True
        # Check if straddles mid_x significantly
        left_overlap = mid_x - b.bbox[0]
        right_overlap = b.bbox[2] - mid_x
        if left_overlap > (0.15 * page_width) and right_overlap > (0.15 * page_width):
            return True
        return False

    # Check if there is genuine two-column distribution on this page
    left_col_count = sum(1 for b in blocks if not _is_full_width(b) and b.bbox[2] <= mid_x + 30.0)
    right_col_count = sum(1 for b in blocks if not _is_full_width(b) and b.bbox[0] >= mid_x - 30.0)
    is_multi_column = (left_col_count >= 2 and right_col_count >= 2)

    if not is_multi_column:
        # Standard single column or non-column layout: sort top-to-bottom, left-to-right
        return sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))

    # For multi-column layout, segment blocks into vertical bands defined by full-width elements
    sorted_by_y = sorted(blocks, key=lambda b: b.bbox[1])

    result: list[TextBlock] = []
    current_band: list[TextBlock] = []

    for b in sorted_by_y:
        if _is_full_width(b):
            # Flush current body band sorted column-by-column
            if current_band:
                result.extend(_sort_band_columns(current_band, mid_x))
                current_band = []
            result.append(b)
        else:
            current_band.append(b)

    if current_band:
        result.extend(_sort_band_columns(current_band, mid_x))

    return result


def _sort_band_columns(body_blocks: list[TextBlock], mid_x: float) -> list[TextBlock]:
    """Sort body blocks within a horizontal band: Left column then Right column."""
    left_col: list[TextBlock] = []
    right_col: list[TextBlock] = []

    for b in body_blocks:
        center_x = (b.bbox[0] + b.bbox[2]) / 2.0
        if center_x < mid_x:
            left_col.append(b)
        else:
            right_col.append(b)

    # Inside each column, sort top-to-bottom
    left_col.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
    right_col.sort(key=lambda b: (b.bbox[1], b.bbox[0]))

    return left_col + right_col
