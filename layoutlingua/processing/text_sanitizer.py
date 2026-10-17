"""Text sanitization, Unicode mojibake repair, and academic abbreviation guarding.

Combines ftfy encoding normalization with academic abbreviation shielding
(et al., i.e., e.g., Fig., Eq., Ref.) to prevent sentence fracture and NMT corruption.
"""

from __future__ import annotations

import re
import ftfy

# Common academic abbreviations with periods that must not be split or corrupted
_ACADEMIC_ABBREVIATIONS = (
    "et al.", "i.e.", "e.g.", "Fig.", "Figs.", "Eq.", "Eqs.",
    "Ref.", "Refs.", "Sec.", "Secs.", "Vol.", "No.", "pp.",
    "Dr.", "Prof.", "vs.", "approx.", "cf.", "dept.", "univ.",
)

_ABBREV_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in _ACADEMIC_ABBREVIATIONS) + r")",
    re.IGNORECASE,
)


def sanitize_extracted_text(text: str) -> str:
    """Repair broken UTF-8 encoding, normalize mojibake, and clean control characters.

    Args:
        text: Raw text string extracted from PDF streams.

    Returns:
        Clean, canonical UTF-8 text with mojibake repaired.
    """
    if not text:
        return ""

    # 1. Use ftfy to fix broken surrogate pairs, HTML entities, and mojibake
    repaired = ftfy.fix_text(text)

    # 2. Strip non-printable ASCII control characters while preserving newlines and tabs
    clean_chars = [
        ch for ch in repaired
        if ch in ("\n", "\r", "\t") or ord(ch) >= 32
    ]
    return "".join(clean_chars)


def shield_academic_abbreviations(text: str) -> tuple[str, dict[str, str]]:
    """Protect academic abbreviations from sentence-splitting and numerical mangling.

    Replaces occurrences like 'et al.' or 'Fig. 1' with invariant placeholders.

    Args:
        text: Input prose string.

    Returns:
        Tuple of (shielded_text, mapping_dict).
    """
    if not text:
        return text, {}

    mapping: dict[str, str] = {}
    counter = 0

    def _replace(m: re.Match) -> str:
        nonlocal counter
        matched = m.group(0)
        token = f"⟦LL_ABBR_{counter}⟧"
        mapping[token] = matched
        counter += 1
        return token

    shielded = _ABBREV_PATTERN.sub(_replace, text)
    return shielded, mapping


def unshield_academic_abbreviations(text: str, mapping: dict[str, str]) -> str:
    """Restore shielded academic abbreviation tokens back to original abbreviations.

    Args:
        text: Translated prose containing abbreviation tokens.
        mapping: Mapping of tokens to original abbreviations.

    Returns:
        Restored prose with authentic academic abbreviations.
    """
    if not mapping:
        return text

    result = text
    for token, original in mapping.items():
        result = result.replace(token, original)

    return result
