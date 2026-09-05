"""Cross-Page Paragraph and Sentence Continuity Stitcher for LayoutLingua.

Detects sentences spanning across page boundaries (Page N bottom to Page N+1 top),
stitches them for coherent document-level translation context, and performs proportional
word-boundary partitioning for page-level rendering.
Addresses pain points from BabelDOC, Docling #3422, and Marker #885.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

TERMINAL_PUNCTUATION = (".", "!", "?", "。", "！", "？", ":", "：", ";")


def ends_with_sentence_break(text: str) -> bool:
    """Check if a text block concludes with definitive sentence-ending punctuation."""
    cleaned = text.strip()
    if not cleaned:
        return True
    return cleaned.endswith(TERMINAL_PUNCTUATION)


def begins_with_continuation(text: str) -> bool:
    """Check if a text block begins as a grammatical continuation (e.g. lowercase letter)."""
    cleaned = text.strip()
    if not cleaned:
        return False
    first_char = cleaned[0]
    # Check for lowercase letter in Unicode
    return first_char.isalpha() and first_char.islower()


def is_cross_page_continuation(tail_text: str, head_text: str) -> bool:
    """Determine whether the tail of Page N flows seamlessly into the head of Page N+1."""
    if ends_with_sentence_break(tail_text):
        return False
    if not begins_with_continuation(head_text):
        return False
    return True


def stitch_cross_page_text(tail_text: str, head_text: str) -> str:
    """Stitch two cross-page text fragments into a unified translation segment."""
    t = tail_text.strip()
    h = head_text.strip()
    return f"{t} {h}"


def split_stitched_translation(
    stitched_translation: str,
    original_tail_len: int,
    original_head_len: int,
) -> Tuple[str, str]:
    """Partition a unified translation into Page N tail and Page N+1 head along a word boundary.

    Uses character-length proportional estimation with nearest whitespace snapping.
    """
    total_orig = max(1, original_tail_len + original_head_len)
    ratio = original_tail_len / total_orig

    words = stitched_translation.split()
    if not words:
        return "", ""
    if len(words) == 1:
        return stitched_translation, ""

    target_chars = int(len(stitched_translation) * ratio)

    # Find the word boundary closest to target_chars
    best_split_idx = 1
    min_diff = float("inf")
    accum_len = 0

    for i in range(len(words) - 1):
        accum_len += len(words[i]) + 1  # word + space
        diff = abs(accum_len - target_chars)
        if diff < min_diff:
            min_diff = diff
            best_split_idx = i + 1

    tail_part = " ".join(words[:best_split_idx])
    head_part = " ".join(words[best_split_idx:])
    return tail_part, head_part
