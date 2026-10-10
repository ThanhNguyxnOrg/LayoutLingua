"""Enhanced Formula & Code Protection and Recovery Normalizer for LayoutLingua.

Recovers from machine-translation artifacts (rogue spaces in tags, HTML entity escapes,
stripped style numbers) to maximize translation yield while maintaining 100% fail-closed
safety for damaged placeholders.
Addresses pain points from BabelDOC, PDFMathTranslate #1175, and PaperLocale.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from typing import Optional, Set, Tuple

# Regex to match raw or spaced placeholder tags
SPACED_OPEN_TAG = re.compile(r"<\s*b\s*(\d+)\s*>", re.IGNORECASE)
SPACED_CLOSE_TAG = re.compile(r"<\s*/\s*b\s*(\d+)\s*>", re.IGNORECASE)
SPACED_STYLE_OPEN = re.compile(r"<\s*s\s*([123])\s*>", re.IGNORECASE)
SPACED_STYLE_CLOSE = re.compile(r"<\s*/\s*s\s*([123])\s*>", re.IGNORECASE)

# Standard paired tags
CANONICAL_PLACEHOLDER = re.compile(r"</?b\d+>")
PAIRED_PLACEHOLDER = re.compile(r"<b(\d+)>\s*</b\1>")


def normalize_mt_placeholders(text: str) -> str:
    """Normalize translation output by repairing common MT formatting artifacts.

    Fixes:
    1. HTML entity escapes (&lt;b1&gt; -> <b1>)
    2. Spacing inside tag delimiters (< b 1 > -> <b1>, < / b 1 > -> </b1>)
    3. Spacing between paired tags (<b1>   </b1> -> <b1></b1>)
    4. Malformed style tags (< s 1 > -> <s1>, < / s 1 > -> </s1>, <s1>...</s> -> <s1>...</s1>)

    Note: Truly unclosed or mismatched formula tags are intentionally NOT auto-closed,
    preserving the fail-closed invariant of LayoutLingua.
    """
    if not text:
        return ""

    # Step 1: HTML unescape
    cleaned = html.unescape(text)

    # Step 2: Remove spaces within placeholder tags
    cleaned = SPACED_CLOSE_TAG.sub(r"</b\1>", cleaned)
    cleaned = SPACED_OPEN_TAG.sub(r"<b\1>", cleaned)

    # Step 3: Remove spaces within numbered style tags
    cleaned = SPACED_STYLE_OPEN.sub(r"<s\1>", cleaned)
    cleaned = SPACED_STYLE_CLOSE.sub(r"</s\1>", cleaned)

    # If MT produced generic </s> without style number, pair it with the preceding <sN>
    def fix_generic_style_close(match: re.Match) -> str:
        prefix = cleaned[:match.start()]
        open_tags = re.findall(r"<s([123])>", prefix, flags=re.IGNORECASE)
        close_tags = re.findall(r"</s([123])>", prefix, flags=re.IGNORECASE)
        if len(open_tags) > len(close_tags):
            return f"</s{open_tags[-1]}>"
        return "</s1>"

    cleaned = re.sub(r"<\s*/\s*s\s*>", fix_generic_style_close, cleaned, flags=re.IGNORECASE)

    # Step 4: Collapse space between paired tags (<b1>  </b1> -> <b1></b1>)
    cleaned = PAIRED_PLACEHOLDER.sub(r"<b\1></b\1>", cleaned)

    # Step 5: Auto-close unclosed style tags at end of segment if MT dropped them
    style_stack: list[str] = []
    for match in re.finditer(r"<(/?)s([123])>", cleaned, flags=re.IGNORECASE):
        closing, identifier = match.groups()
        if not closing:
            style_stack.append(identifier)
        elif style_stack and style_stack[-1] == identifier:
            style_stack.pop()
    while style_stack:
        unclosed_id = style_stack.pop()
        cleaned += f"</s{unclosed_id}>"

    return cleaned


def extract_placeholder_ids(text: str) -> Set[int]:
    """Extract all formula identifier integers present in a string."""
    matches = re.findall(r"<b(\d+)>", text)
    return {int(m) for m in matches}


def validate_formula_integrity(
    encoded_source: str,
    translated: str,
) -> Tuple[bool, Optional[str]]:
    """Validate that formula placeholders in translation match source perfectly.

    Returns:
        (is_valid, error_message_if_any)
    """
    src_ids = Counter(int(m) for m in re.findall(r"<b(\d+)>", encoded_source))
    dst_ids = Counter(int(m) for m in re.findall(r"<b(\d+)>", translated))

    if src_ids != dst_ids:
        missing = set(src_ids.keys()) - set(dst_ids.keys())
        extra = set(dst_ids.keys()) - set(src_ids.keys())
        if missing:
            return False, f"Missing formula placeholders: {sorted(missing)}"
        if extra:
            return False, f"Extra unexpected formula placeholders: {sorted(extra)}"
        return False, "Formula placeholder counts do not match source"

    # Check for balanced tag pairs
    stack: list[str] = []
    for match in CANONICAL_PLACEHOLDER.finditer(translated):
        tag = match.group(0)
        closing = tag.startswith("</")
        ident = re.search(r"\d+", tag).group(0)
        if not closing:
            stack.append(ident)
        else:
            if not stack or stack[-1] != ident:
                return False, f"Cross-nested or unaligned tag </b{ident}>"
            stack.pop()

    if stack:
        return False, f"Unclosed formula tags: {stack}"

    return True, None
