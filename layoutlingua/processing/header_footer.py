"""Running header and footer de-noising for academic and scientific publications.

Detects recurring publication headers, copyright banners, and page numbers
located in the top and bottom margins across document pages, preserving them
in their original pristine form without wasting translation tokens.
"""

from __future__ import annotations

import re
from typing import Sequence

from layoutlingua.core.ir import PageIR

# Regex for standalone page numbers (e.g. "12", "Page 5", "3 / 10", "iv")
_PAGE_NUM_PATTERN = re.compile(
    r"^(?:page\s*)?(?:\d+|[ivxlcdm]+)(?:\s*(?:of|/|-)\s*(?:\d+|[ivxlcdm]+))?$",
    re.IGNORECASE,
)


def detect_running_headers_footers(
    pages: Sequence[PageIR],
    top_margin_ratio: float = 0.08,
    bottom_margin_ratio: float = 0.08,
    min_repetition: int = 3,
) -> set[str]:
    """Identify block IDs of recurring headers, footers, and page numbers.

    Blocks located within the top or bottom margin bounds that:
    1. Repeat across 3 or more pages (e.g. journal title, conference name), OR
    2. Match standard standalone page number patterns

    are identified so they can be preserved untranslated.

    Args:
        pages: Sequence of PageIR objects from DocumentIR.
        top_margin_ratio: Fraction of page height from top treated as header zone (default 8%).
        bottom_margin_ratio: Fraction of page height from bottom treated as footer zone (default 8%).
        min_repetition: Minimum number of pages a header/footer text must appear on to be flagged (default 3).

    Returns:
        Set of block IDs that should be preserved untranslated.
    """
    if not pages:
        return set()

    # Track text occurrences in margin zones across pages: text -> list of (page_num, block_id)
    header_text_occurrences: dict[str, list[str]] = {}
    footer_text_occurrences: dict[str, list[str]] = {}
    page_number_block_ids: set[str] = set()

    for page in pages:
        page_h = page.geometry.height if hasattr(page, "geometry") and page.geometry else 842.0
        top_bound = page_h * top_margin_ratio
        bottom_bound = page_h * (1.0 - bottom_margin_ratio)

        for block in page.blocks:
            text = block.text.strip()
            if not text:
                continue

            # Check if block is entirely or predominantly inside top margin
            y_mid = (block.bbox[1] + block.bbox[3]) / 2.0
            is_top = y_mid <= top_bound
            is_bottom = y_mid >= bottom_bound

            if not (is_top or is_bottom):
                continue

            # Standalone page number check
            if _PAGE_NUM_PATTERN.match(text):
                page_number_block_ids.add(block.block_id)
                continue

            # Normalized text for recurrence check (lowercase, collapsed spaces)
            norm_text = " ".join(text.lower().split())

            if is_top:
                header_text_occurrences.setdefault(norm_text, []).append(block.block_id)
            elif is_bottom:
                footer_text_occurrences.setdefault(norm_text, []).append(block.block_id)

    suppressed_ids: set[str] = set(page_number_block_ids)

    # Flag recurring headers (>= min_repetition pages)
    for _text, b_ids in header_text_occurrences.items():
        if len(b_ids) >= min_repetition:
            suppressed_ids.update(b_ids)

    # Flag recurring footers (>= min_repetition pages)
    for _text, b_ids in footer_text_occurrences.items():
        if len(b_ids) >= min_repetition:
            suppressed_ids.update(b_ids)

    return suppressed_ids
