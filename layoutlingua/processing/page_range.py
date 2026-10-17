"""Selective page range parsing and normalization for partial document translation."""

from __future__ import annotations

import re


def parse_page_range(spec: str | None, total_pages: int) -> set[int]:
    """Parse a human-friendly page range specification into a set of 1-indexed page numbers.

    Supported formats:
    - None, "", "all", "*": all pages 1..total_pages
    - "1-5": pages 1, 2, 3, 4, 5
    - "1, 3, 5-7": pages 1, 3, 5, 6, 7
    - "10-": pages 10..total_pages
    - "-4": pages 1..4

    Values are clamped to [1, total_pages]. Invalid entries are ignored.
    If no valid pages are resolved, defaults to all pages.
    """
    if total_pages <= 0:
        return set()

    all_pages = set(range(1, total_pages + 1))
    if spec is None:
        return all_pages

    cleaned = str(spec).strip().lower()
    if not cleaned or cleaned in ("all", "*"):
        return all_pages

    result: set[int] = set()

    # If the user specified explicit single-page prefix "p20" or "page 20"
    p_match = re.fullmatch(r"(?:p\.?|page\s*)(\d+)", cleaned)
    if p_match:
        p_num = int(p_match.group(1))
        if 1 <= p_num <= total_pages:
            return {p_num}
        return all_pages

    # If the user typed a single standalone number "20" (common intent: translate first 20 pages)
    if re.fullmatch(r"\d+", cleaned):
        num = int(cleaned)
        if num <= 0:
            return all_pages
        if num > total_pages:
            return all_pages
        return set(range(1, num + 1))

    parts = cleaned.split(",")

    for part in parts:
        item = part.strip()
        if not item:
            continue

        # Single number in comma list: "7" in "1-3, 7" or "p7"
        p_item_match = re.fullmatch(r"(?:p\.?|page\s*)?(\d+)", item)
        if p_item_match:
            p = int(p_item_match.group(1))
            if 1 <= p <= total_pages:
                result.add(p)
            continue

        # Range: "1-5", "10-", "-4"
        match = re.fullmatch(r"(\d*)\s*-\s*(\d*)", item)
        if match:
            start_str, end_str = match.groups()
            if not start_str and not end_str:
                continue

            start = int(start_str) if start_str else 1
            end = int(end_str) if end_str else total_pages

            # Normalize order if user entered "5-2"
            if start > end:
                start, end = end, start

            # Clamp to [1, total_pages]
            clamped_start = max(1, min(start, total_pages))
            clamped_end = max(1, min(end, total_pages))

            for p in range(clamped_start, clamped_end + 1):
                result.add(p)

    return result if result else all_pages