"""Line-break dehyphenation for academic and technical documents.

Restores words fractured across line boundaries by soft hyphens
while strictly preserving compound terms, model names, and formula tokens.
"""

from __future__ import annotations

import re

# 1. Explicit Unicode soft hyphen (\u00ad) is always a soft syllable break
_SOFT_HYPHEN_PATTERN = re.compile(r"\b([a-zA-Z]+)\u00ad\s*([a-zA-Z]+)\b")

# 2. Line-break hyphens: hyphen followed by newline / vertical line break
_LINEBREAK_HYPHEN_PATTERN = re.compile(
    r"\b([a-zA-Z]+)[-\u2010\u2011]\s*[\r\n]+\s*([a-z][a-zA-Z]*)\b"
)

# Single letter prefixes that must retain hyphens even at line breaks (e.g., X-\nray, U-\nNet)
_SINGLE_LETTER_PREFIXES = set("ABCDEFGHIJKLMNOPQRSTUVWXYZk")

# Common compound prefixes where retaining the hyphen is standard
_COMPOUND_PREFIXES = {
    "self", "cross", "multi", "semi", "non", "pre", "post", "all",
    "state", "fine", "well", "co", "micro", "macro", "quasi",
}

# Known domain compound words
_KNOWN_COMPOUNDS = {
    "state-of-the-art", "fine-tuned", "zero-shot", "few-shot",
    "end-to-end", "trade-off", "out-of-distribution", "cross-entropy",
    "plug-and-play", "k-means", "drop-out",
}


def dehyphenate_text(text: str) -> str:
    """Restore words broken across line breaks by justification hyphens.

    Examples:
        >>> dehyphenate_text("distri-\\n bution of samples")
        'distribution of samples'
        >>> dehyphenate_text("algo-\\nrithm efficiency")
        'algorithm efficiency'
        >>> dehyphenate_text("U-Net architecture")
        'U-Net architecture'
        >>> dehyphenate_text("state-of-the-art results")
        'state-of-the-art results'
    """
    if not text or ("-" not in text and "\u00ad" not in text and "\u2010" not in text and "\u2011" not in text):
        return text

    # Protect formula placeholders from mutation
    placeholders: list[str] = []

    def _save_ph(m: re.Match) -> str:
        placeholders.append(m.group(0))
        return f"__LL_DEHYPHEN_PH_{len(placeholders)-1}__"

    masked = re.sub(r"⟦LL_FORMULA_\d+⟧|<b\d+></b\d+>", _save_ph, text)

    # First normalize explicit Unicode soft hyphens
    masked = _SOFT_HYPHEN_PATTERN.sub(r"\1\2", masked)

    def _replace_linebreak(m: re.Match) -> str:
        prefix = m.group(1)
        suffix = m.group(2)
        combined = f"{prefix.lower()}-{suffix.lower()}"

        # If prefix is a single letter (U-Net, X-ray, k-means), keep hyphen
        if prefix in _SINGLE_LETTER_PREFIXES:
            return f"{prefix}-{suffix}"

        # Known compound prefixes or exact compound phrases
        if prefix.lower() in _COMPOUND_PREFIXES or combined in _KNOWN_COMPOUNDS:
            return f"{prefix}-{suffix}"

        # All uppercase parts (e.g. IEEE-ACM)
        if prefix.isupper() and suffix.isupper():
            return f"{prefix}-{suffix}"

        # Soft hyphenated word break: rejoin
        return f"{prefix}{suffix}"

    result = _LINEBREAK_HYPHEN_PATTERN.sub(_replace_linebreak, masked)

    for idx, ph in enumerate(placeholders):
        result = result.replace(f"__LL_DEHYPHEN_PH_{idx}__", ph)

    return result
