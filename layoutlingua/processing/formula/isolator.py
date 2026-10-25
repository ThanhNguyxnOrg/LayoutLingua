"""Structured formula isolation, placeholder tokenization, and integrity verification."""

from __future__ import annotations

import re
from typing import Sequence

from layoutlingua.core.ir import GlyphSpan, TextBlock
from layoutlingua.core.parser import _extract_prose_tokens
from layoutlingua.processing.formula.models import (
    FormulaToken,
    TextSegment,
    TokenVerificationResult,
)

# Regex to match token placeholders: <b0></b0>, <b1></b1>, etc.
_PLACEHOLDER_REGEX = re.compile(r"<b(\d+)></b\1>")

# Common mathematical symbol set and TeX operators
_MATH_OPERATOR_CHARS = set(
    "∫∑∏√∝∞∠∧∨∩∪≈≠≡≤≥⊂⊃⊆⊇⊕⊗⊥⋅∂∇±∓×÷°′″"
    "αβγδεζηθικλμνξπρστυφχψω"
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ"
    "∈∉∋∌"
    "²³¹⁰⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾₀₁₂₃₄₅₆₇₈₉"
)

# Math font substrings
_MATH_FONTS = (
    "math", "symbol", "cmmi", "cmsy", "cmex", "msam", "msbm", "mt2",
    "mathtype", "eufm", "euex", "wasy", "rsfs", "txsy", "stmary",
)

_MATH_FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "lim",
    "max", "min", "det", "deg", "rad", "gcd", "lcm", "sinh", "cosh", "tanh",
}


class FormulaIsolator:
    """Isolates math formulas and validates placeholder integrity in translated prose."""

    def __init__(self) -> None:
        pass

    def is_math_span(self, span: GlyphSpan) -> bool:
        """Heuristic to determine if an individual span is a formula or symbol."""
        text = span.text.strip()
        if not text:
            return False

        if span.is_math_or_symbol:
            return True

        font_lower = span.font_name.lower()
        if any(mf in font_lower for mf in _MATH_FONTS):
            return True

        # Standard math function names (e.g. sin, cos, tan)
        if text.lower() in _MATH_FUNCTIONS:
            return True

        # Natural language prose safeguard:
        # If the span contains multi-character prose words in any language
        prose_tokens = _extract_prose_tokens(text)
        if len(prose_tokens) > 0:
            return False

        # Italic variables or short math notation (e.g. x, y, x², a_1)
        if "ital" in font_lower and len(text) <= 3:
            return True

        # Subscript or superscript font size (<= 9.5 pt) with short alphanumeric tokens without prose
        if span.font_size <= 9.5 and len(text) <= 4:
            return True

        # Isolated punctuation or closing brackets belong to enclosing prose syntax
        if text.strip() in (")", "]", "}", ".)", "]:", "):", ".", ",", ":", ";"):
            return False

        # If span consists predominantly of mathematical symbols or degree marks (e.g. 60°, 360°, ±, α, x², ≤, ≥)
        math_count = sum(1 for ch in text if ch in _MATH_OPERATOR_CHARS or ch in "+-=/*^<>()[]{}≤≥±≠≈")
        if math_count > 0 and (math_count / len(text)) >= 0.3:
            return True

        return False

    def isolate_block(self, block: TextBlock) -> TextSegment:
        """Convert a TextBlock into a TextSegment with structured formula placeholders.
        
        Sorts spans left-to-right and groups consecutive/connected math spans into a single
        cohesive formula token, preventing neural MT models from fragmenting expressions.
        """
        # TS-parity: word-level tokenization when char geometry is available.
        # Falls back to span-level classification for spans without chars.
        from layoutlingua.processing.formula.word_tokens import build_word_tokens, classify_word_tokens

        try:
            word_tokens = build_word_tokens(block)
            classify_word_tokens(word_tokens)
        except Exception:
            word_tokens = []

        use_words = bool(word_tokens)
        if use_words:
            # Sort by the 3pt-baseline-cluster line index (not a coarse y-bucket:
            # sub/superscript words sit a few points lower and a y-bucket sort
            # scrambles them out of their formula group).
            items = sorted(word_tokens, key=lambda w: (w.line_index, w.bbox[0]))
        else:
            items = sorted(block.spans, key=lambda s: (round(s.bbox[1] / 8.0) * 8.0, s.bbox[0]))

        tokens: list[FormulaToken] = []
        masked_parts: list[str] = []
        span_ids: list[str] = [s.span_id for s in block.spans]
        token_id_counter = 0

        is_math_list = [it.is_math if use_words else self.is_math_span(it) for it in items]
        n = len(items)
        i = 0

        while i < n:
            span = items[i]
            # Check if this span is math or starts a math expression
            # A leading number/operator can start a math group if directly followed by a math span
            starts_math = is_math_list[i]
            if not starts_math and i + 1 < n and is_math_list[i + 1]:
                txt_strip = span.text.strip()
                if txt_strip and re.match(r"^[\d.,:;+=\-*/_~^…≤≥()\[\]{}]+$", txt_strip) and len(txt_strip) <= 6:
                    starts_math = True

            if starts_math:
                j = i
                group = []
                while j < n:
                    if is_math_list[j]:
                        group.append(items[j])
                        j += 1
                    elif not items[j].text.strip() and j + 1 < n and is_math_list[j + 1]:
                        group.append(items[j])
                        j += 1
                    elif (
                        j + 1 < n and is_math_list[j + 1] and
                        re.match(r"^[\d\s.,:;+=\-*/_~^…≤≥()\[\]{}]+$", items[j].text) and
                        len(items[j].text.strip()) <= 6
                    ):
                        group.append(items[j])
                        j += 1
                    else:
                        break

                raw_content = "".join(s.text for s in group).strip()
                placeholder = f"<b{token_id_counter}></b{token_id_counter}>"
                min_x0 = min(s.bbox[0] for s in group)
                min_y0 = min(s.bbox[1] for s in group)
                max_x1 = max(s.bbox[2] for s in group)
                max_y1 = max(s.bbox[3] for s in group)
                token = FormulaToken(
                    token_id=token_id_counter,
                    placeholder=placeholder,
                    raw_content=raw_content,
                    bbox=(min_x0, min_y0, max_x1, max_y1),
                    font_name=group[0].font_name,
                )
                tokens.append(token)
                masked_parts.append(f" {placeholder} ")
                token_id_counter += 1
                i = j
            else:
                masked_parts.append(span.text)
                i += 1

        raw_text = block.text
        # Word-level tokens lose the inter-word spaces of their parent spans:
        # re-join with explicit spaces (token parts already carry padding, and
        # the normalization below collapses any doubles).
        masked_text = (" " if use_words else "").join(masked_parts)

        # Normalize semantic boundary spaces around placeholders
        masked_text = re.sub(r"(\S)(<b\d+></b\d+>)", r"\1 \2", masked_text)
        masked_text = re.sub(r"(<b\d+></b\d+>)(\S)", r"\1 \2", masked_text)
        # Collapse multiple adjacent spaces
        masked_text = re.sub(r" +", " ", masked_text).strip()

        # Dehyphenate soft line breaks within block prose
        from layoutlingua.processing.dehyphen import dehyphenate_text

        masked_text = dehyphenate_text(masked_text)

        return TextSegment(
            segment_id=block.block_id,
            raw_text=raw_text,
            masked_text=masked_text,
            tokens=tokens,
            span_ids=span_ids,
        )

    @staticmethod
    def normalize_placeholders(text: str) -> str:
        """Fix any spaces or distortions introduced by translation engines into placeholders."""
        t = re.sub(r"<\s*b\s*(\d+)\s*>\s*<\s*/\s*b\s*\1\s*>", r"<b\1></b\1>", text, flags=re.IGNORECASE)
        t = re.sub(r"<\s*b\s*>\s*(\d+)\s*>\s*<\s*/\s*b\s*>", r"<b\1></b\1>", t, flags=re.IGNORECASE)
        t = re.sub(r"<\s*b\s*(\d+)\s*>\s*<\s*/\s*>", r"<b\1></b\1>", t, flags=re.IGNORECASE)
        t = re.sub(r"<\s*b\s*(\d+)\s*/>", r"<b\1></b\1>", t, flags=re.IGNORECASE)
        # Protect well-formed <bN></bN> with a unique sentinel
        t = re.sub(r"<b(\d+)></b\1>", r"⟦VT_\1⟧", t, flags=re.IGNORECASE)
        # Any remaining stray <bN> or </bN> is converted to sentinel
        t = re.sub(r"<\s*/?\s*b\s*(\d+)\s*>", r"⟦VT_\1⟧", t, flags=re.IGNORECASE)
        # Restore sentinels to canonical <bN></bN>
        t = re.sub(r"⟦VT_(\d+)⟧", r"<b\1></b\1>", t)
        # Deduplicate adjacent identical placeholders
        t = re.sub(r"(<b\d+></b\d+>)(?:\s*\1)+", r"\1", t)
        return t

    def verify_tokens(self, segment: TextSegment, translated_text: str) -> TokenVerificationResult:
        """Verify that translated text preserves all formula tokens without loss, duplication, or reordering."""
        clean_text = self.normalize_placeholders(translated_text)
        if not segment.tokens:
            # Segment had no formula tokens: check if any unexpected token appeared
            found_alien = _PLACEHOLDER_REGEX.findall(clean_text)
            if found_alien:
                return TokenVerificationResult(
                    is_valid=False,
                    reason="Unexpected formula tokens found in translation of non-formula segment.",
                    alien_tokens=[f"<b{t}></b{t}>" for t in found_alien],
                )
            return TokenVerificationResult(is_valid=True)

        found_matches = [m.group(0) for m in _PLACEHOLDER_REGEX.finditer(clean_text)]
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

    def restore_translation(
        self,
        segment: TextSegment,
        translated_text: str,
        allow_reorder: bool = True,
    ) -> str:
        """Restore formula tokens into translated text; fall back to raw_text if verification fails."""
        clean_text = self.normalize_placeholders(translated_text)
        verification = self.verify_tokens(segment, clean_text)
        if not verification.is_valid:
            # If the only issue was out_of_order and allow_reorder is True, we can safely proceed
            if (
                allow_reorder
                and verification.out_of_order
                and not verification.missing_tokens
                and not verification.duplicate_tokens
                and not verification.alien_tokens
            ):
                pass
            else:
                # Fail-closed invariant: retain original source text
                return segment.raw_text

        result = clean_text
        for token in segment.tokens:
            result = result.replace(token.placeholder, token.raw_content)

        # Final safety cleanup: remove any leftover deformed XML tag artifacts
        result = re.sub(r"<\s*/?\s*b\d*[^>]*>", "", result)
        return result
