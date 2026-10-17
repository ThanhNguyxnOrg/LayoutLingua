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


# Adobe Standard Symbol Font PUA (0xF020 - 0xF0FF) to standard Unicode mapping
# Implemented following standard PDF font extraction specifications (PDF Reference / ISO 32000-1)
# and open-source PDF math extraction standards (pdf2zh, BabelDOC, Grobid).
SYMBOL_PUA_TO_UNICODE: dict[int, str] = {
    0xF020: " ", 0xF021: "!", 0xF022: "∀", 0xF023: "#", 0xF024: "∃", 0xF025: "%", 0xF026: "&", 0xF027: "∍",
    0xF028: "(", 0xF029: ")", 0xF02A: "∗", 0xF02B: "+", 0xF02C: ",", 0xF02D: "-", 0xF02E: ".", 0xF02F: "/",
    0xF030: "0", 0xF031: "1", 0xF032: "2", 0xF033: "3", 0xF034: "4", 0xF035: "5", 0xF036: "6", 0xF037: "7",
    0xF038: "8", 0xF039: "9", 0xF03A: ":", 0xF03B: ";", 0xF03C: "<", 0xF03D: "=", 0xF03E: ">", 0xF03F: "?",
    0xF040: "≅", 0xF041: "Α", 0xF042: "Β", 0xF043: "Χ", 0xF044: "Δ", 0xF045: "Ε", 0xF046: "Φ", 0xF047: "Γ",
    0xF048: "Η", 0xF049: "Ι", 0xF04A: "ϑ", 0xF04B: "Κ", 0xF04C: "Λ", 0xF04D: "Μ", 0xF04E: "Ν", 0xF04F: "Ο",
    0xF050: "Π", 0xF051: "Θ", 0xF052: "Ρ", 0xF053: "Σ", 0xF054: "Τ", 0xF055: "Υ", 0xF056: "ς", 0xF057: "Ω",
    0xF058: "Ξ", 0xF059: "Ψ", 0xF05A: "Ζ", 0xF05B: "[", 0xF05C: "∴", 0xF05D: "]", 0xF05E: "⊥", 0xF05F: "_",
    0xF060: "‾", 0xF061: "α", 0xF062: "β", 0xF063: "χ", 0xF064: "δ", 0xF065: "ε", 0xF066: "φ", 0xF067: "γ",
    0xF068: "η", 0xF069: "ι", 0xF06A: "ϕ", 0xF06B: "κ", 0xF06C: "λ", 0xF06D: "μ", 0xF06E: "ν", 0xF06F: "ο",
    0xF070: "π", 0xF071: "θ", 0xF072: "ρ", 0xF073: "σ", 0xF074: "τ", 0xF075: "υ", 0xF076: "ϖ", 0xF077: "ω",
    0xF078: "ξ", 0xF079: "ψ", 0xF07A: "ζ", 0xF07B: "{", 0xF07C: "|", 0xF07D: "}", 0xF07E: "~",
    0xF0A0: " ", 0xF0A1: "ϒ", 0xF0A2: "′", 0xF0A3: "≤", 0xF0A4: "⁄", 0xF0A5: "∞", 0xF0A6: "ƒ", 0xF0A7: "♣",
    0xF0A8: "♦", 0xF0A9: "♥", 0xF0AA: "♠", 0xF0AB: "↔", 0xF0AC: "←", 0xF0AD: "↑", 0xF0AE: "→", 0xF0AF: "↓",
    0xF0B0: "°", 0xF0B1: "±", 0xF0B2: "″", 0xF0B3: "≥", 0xF0B4: "×", 0xF0B5: "∝", 0xF0B6: "∂", 0xF0B7: "•",
    0xF0B8: "÷", 0xF0B9: "≠", 0xF0BA: "≡", 0xF0BB: "≈", 0xF0BC: "…", 0xF0BD: "⎪", 0xF0BE: "⎯", 0xF0BF: "↵",
    0xF0C0: "ℵ", 0xF0C1: "ℑ", 0xF0C2: "ℜ", 0xF0C3: "℘", 0xF0C4: "⊗", 0xF0C5: "⊕", 0xF0C6: "∅", 0xF0C7: "∩",
    0xF0C8: "∪", 0xF0C9: "⊃", 0xF0CA: "⊇", 0xF0CB: "⊄", 0xF0CC: "⊂", 0xF0CD: "⊆", 0xF0CE: "∈", 0xF0CF: "∉",
    0xF0D0: "∠", 0xF0D1: "∇", 0xF0D2: "®", 0xF0D3: "©", 0xF0D4: "™", 0xF0D5: "∏", 0xF0D6: "√", 0xF0D7: "⋅",
    0xF0D8: "¬", 0xF0D9: "∧", 0xF0DA: "∨", 0xF0DB: "⇔", 0xF0DC: "⇐", 0xF0DD: "⇒", 0xF0DE: "⇓", 0xF0DF: "◊",
    0xF0E0: "⟨", 0xF0E1: "⟩", 0xF0E5: "∑", 0xF0F1: "", 0xF0F2: "∫", 0xF0F3: "⌠", 0xF0F4: "⎮", 0xF0F5: "⌡",
}


def sanitize_extracted_text(text: str) -> str:
    """Repair broken UTF-8 encoding, normalize mojibake, normalize PUA symbols, and clean control characters.

    Args:
        text: Raw text string extracted from PDF streams.

    Returns:
        Clean, canonical UTF-8 text with mojibake repaired and Symbol font PUA converted.
    """
    if not text:
        return ""

    # 1. Normalize Adobe Symbol / Wingdings PUA codepoints (0xF000 - 0xF0FF)
    pua_normalized = "".join(
        SYMBOL_PUA_TO_UNICODE.get(ord(ch), ch) if 0xF000 <= ord(ch) <= 0xF0FF else ch
        for ch in text
    )

    # 2. Use ftfy to fix broken surrogate pairs, HTML entities, and mojibake
    repaired = ftfy.fix_text(pua_normalized)

    # 3. Strip non-printable ASCII control characters while preserving newlines and tabs
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
