"""Structured formula isolation, placeholder tokenization, and integrity verification."""

from __future__ import annotations

import re
from typing import Sequence

from layoutlingua.core.ir import GlyphSpan, TextBlock
from layoutlingua.processing.formula.models import (
    FormulaToken,
    TextSegment,
    TokenVerificationResult,
)

# Regex to match token placeholders: <b0></b0>, <b1></b1>, etc.
_PLACEHOLDER_REGEX = re.compile(r"<b(\d+)></b\1>")

# Common mathematical symbol set and TeX operators
_MATH_OPERATOR_CHARS = set(
    "∫∑∏√∝∞∠∧∨∩∪≈≠≡≤≥⊂⊃⊆⊇⊕⊗⊥⋅∂∇±×÷"
    "αβγδεζηθικλμνξπρστυφχψω"
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ"
    "∈∉∋∌"
)

# Math font substrings
_MATH_FONTS = (
    "math", "symbol", "cmmi", "cmsy", "cmex", "msam", "msbm", "mt2",
    "mathtype", "eufm", "euex", "wasy",
)


class FormulaIsolator:
    """Isolates math formulas and validates placeholder integrity in translated prose."""

    def __init__(self) -> None:
        pass

    def is_math_span(self, span: GlyphSpan) -> bool:
        """Heuristic to determine if an individual span is a formula or symbol."""
        if span.is_math_or_symbol:
            return True

        font_lower = span.font_name.lower()
        if any(mf in font_lower for mf in _MATH_FONTS):
            return True

        text = span.text.strip()
        if not text:
            return False

        # If span consists predominantly of mathematical symbols
        math_count = sum(1 for ch in text if ch in _MATH_OPERATOR_CHARS)
        if math_count > 0 and (math_count / len(text)) >= 0.4:
            return True

        return False

    def isolate_block(self, block: TextBlock) -> TextSegment:
        """Convert a TextBlock into a TextSegment with structured formula placeholders."""
        tokens: list[FormulaToken] = []
        masked_parts: list[str] = []
        span_ids: list[str] = []
        token_id_counter = 0

        for span in block.spans:
            span_ids.append(span.span_id)
            if self.is_math_span(span):
                placeholder = f"<b{token_id_counter}></b{token_id_counter}>"
                token = FormulaToken(
                    token_id=token_id_counter,
                    placeholder=placeholder,
                    raw_content=span.text,
                    bbox=span.bbox,
                    font_name=span.font_name,
                )
                tokens.append(token)
                masked_parts.append(f" {placeholder} ")
                token_id_counter += 1
            else:
                masked_parts.append(span.text)

        raw_text = block.text
        masked_text = "".join(masked_parts)

        # Normalize semantic boundary spaces around placeholders
        masked_text = re.sub(r"(\S)(<b\d+></b\d+>)", r"\1 \2", masked_text)
        masked_text = re.sub(r"(<b\d+></b\d+>)(\S)", r"\1 \2", masked_text)
        # Collapse multiple adjacent spaces
        masked_text = re.sub(r" +", " ", masked_text).strip()

        return TextSegment(
            segment_id=block.block_id,
            raw_text=raw_text,
            masked_text=masked_text,
            tokens=tokens,
            span_ids=span_ids,
        )

    def verify_tokens(self, segment: TextSegment, translated_text: str) -> TokenVerificationResult:
        """Verify that translated text preserves all formula tokens without loss, duplication, or reordering."""
        if not segment.tokens:
            # Segment had no formula tokens: check if any unexpected token appeared
            found_alien = _PLACEHOLDER_REGEX.findall(translated_text)
            if found_alien:
                return TokenVerificationResult(
                    is_valid=False,
                    reason="Unexpected formula tokens found in translation of non-formula segment.",
                    alien_tokens=[f"<b{t}></b{t}>" for t in found_alien],
                )
            return TokenVerificationResult(is_valid=True)

        found_matches = [m.group(0) for m in _PLACEHOLDER_REGEX.finditer(translated_text)]
        expected_tokens = [t.placeholder for t in segment.tokens]

        # 1. Check for duplicates
        seen: set[str] = set()
        duplicates: list[str] = []
        for tag in found_matches:
            if tag in seen and tag not in duplicates:
                duplicates.append(tag)
            seen.add(tag)

        # 2. Check for missing tokens
        missing = [t for t in expected_tokens if t not in seen]

        # 3. Check for alien tokens
        alien = [t for t in found_matches if t not in expected_tokens]

        # 4. Check ordering
        out_of_order = False
        if not missing and not duplicates and not alien:
            if found_matches != expected_tokens:
                out_of_order = True

        if duplicates:
            return TokenVerificationResult(
                is_valid=False,
                reason=f"Duplicate formula tokens detected: {duplicates}",
                duplicate_tokens=duplicates,
            )

        if missing:
            return TokenVerificationResult(
                is_valid=False,
                reason=f"Missing formula tokens in translation: {missing}",
                missing_tokens=missing,
            )

        if alien:
            return TokenVerificationResult(
                is_valid=False,
                reason=f"Alien formula tokens appeared: {alien}",
                alien_tokens=alien,
            )

        if out_of_order:
            return TokenVerificationResult(
                is_valid=False,
                reason="Formula tokens were reordered during translation.",
                out_of_order=True,
            )

        return TokenVerificationResult(is_valid=True)

    def restore_translation(self, segment: TextSegment, translated_text: str) -> str:
        """Restore formula tokens into translated text; fall back to raw_text if verification fails."""
        verification = self.verify_tokens(segment, translated_text)
        if not verification.is_valid:
            # Fail-closed invariant: retain original source text
            return segment.raw_text

        result = translated_text
        for token in segment.tokens:
            result = result.replace(token.placeholder, token.raw_content)

        return result
