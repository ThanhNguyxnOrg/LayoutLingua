"""Citation anchor shielding and restoration for scientific documents.

Protects academic bibliographic references (e.g., [1], [2, 3], [1-5])
from semantic mistranslation, reordering, or numerical mutation by NMT/LLM models.
"""

from __future__ import annotations

import re

# Regex for academic citation markers: [1], [2, 3], [1-5], [12, 15, 22]
_CITATION_PATTERN = re.compile(r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")
_REF_TOKEN_PATTERN = re.compile(r"⟦LL_REF_(\d+)⟧")


def shield_citations(text: str) -> tuple[str, dict[str, str]]:
    """Replace citation brackets with invariant tokens prior to machine translation.

    Args:
        text: Input text containing potential citation references like [1], [2, 3].

    Returns:
        A tuple of (shielded_text, token_mapping).

    Example:
        >>> shielded, mapping = shield_citations("Attention [1] is all you need [2, 3].")
        >>> shielded
        'Attention ⟦LL_REF_0⟧ is all you need ⟦LL_REF_1⟧.'
        >>> mapping
        {'⟦LL_REF_0⟧': '[1]', '⟦LL_REF_1⟧': '[2, 3]'}
    """
    if "[" not in text or "]" not in text:
        return text, {}

    mapping: dict[str, str] = {}
    counter = 0

    def _replace(m: re.Match) -> str:
        nonlocal counter
        ref_text = m.group(0)
        token = f"⟦LL_REF_{counter}⟧"
        mapping[token] = ref_text
        counter += 1
        return token

    shielded = _CITATION_PATTERN.sub(_replace, text)
    return shielded, mapping


def unshield_citations(text: str, mapping: dict[str, str]) -> str:
    """Restore shielded citation tokens back to their original reference markers.

    Args:
        text: Translated text containing tokens like ⟦LL_REF_0⟧.
        mapping: Dictionary mapping tokens to original reference brackets.

    Returns:
        Restored text with authentic bibliographic references intact.
    """
    if not mapping:
        return text

    result = text
    for token, original_ref in mapping.items():
        result = result.replace(token, original_ref)

    return result
