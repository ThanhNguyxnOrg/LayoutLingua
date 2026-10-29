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
            items = list(word_tokens)
        else:
            items = sorted(block.spans, key=lambda s: (round(s.bbox[1] / 8.0) * 8.0, s.bbox[0]))

        tokens: list[FormulaToken] = []
        masked_parts: list[str] = []
        span_ids: list[str] = [s.span_id for s in block.spans]
        token_id_counter = 0

        is_math_list = [it.is_math if use_words else self.is_math_span(it) for it in items]
        n = len(items)
        i = 0

        def _paren_closes_in_math(start_idx: int) -> bool:
            depth = 0
            for k in range(start_idx, n):
                if abs(items[k].bbox[1] - items[start_idx].bbox[1]) > 8.0 and k > start_idx:
                    break
                t_k = items[k].text
                is_m = is_math_list[k] or bool(re.match(r"^[\d\s.,:;+=\-*/!_~^…≤≥()\[\]{}|]+$", t_k))
                if not is_m and depth > 0:
                    return False
                depth += t_k.count("(") - t_k.count(")")
                if depth <= 0 and "(" in items[start_idx].text:
                    return True
                if not is_m:
                    break
            return False

        while i < n:
            span = items[i]
            # Check if this span is math or starts a math expression
            # A leading number/operator can start a math group if directly followed by a math span on the same line
            starts_math = is_math_list[i]
            if not starts_math and i + 1 < n and is_math_list[i + 1]:
                txt_strip = span.text.strip()
                same_line = (
                    abs(span.bbox[1] - items[i + 1].bbox[1]) <= 6.0
                    and -1.0 <= (items[i + 1].bbox[0] - span.bbox[2]) <= 6.0
                )
                if (
                    same_line
                    and txt_strip
                    and not txt_strip.endswith((",", ";", ":", ".", "…"))
                    and re.match(r"^[\d+=\-*/_~^≤≥()\[\]{}|]+$", txt_strip)
                    and len(txt_strip) <= 6
                ):
                    if "(" in txt_strip and ")" not in txt_strip:
                        starts_math = _paren_closes_in_math(i)
                    else:
                        starts_math = True

            if starts_math:
                j = i
                group = []
                open_paren_balance = 0
                while j < n:
                    it_j = items[j]
                    txt_j = it_j.text.strip()
                    ref_prev = group[-1] if group else it_j
                    # If group already has balanced parens and items[j] opens a new '(' that does not close before prose
                    # (e.g. "k=tanα (α là góc...)" or "(-1)S × (1 + Fraction)"), break before '('
                    if (
                        group
                        and open_paren_balance <= 0
                        and txt_j.startswith("(")
                        and it_j.text.count("(") > it_j.text.count(")")
                        and not _paren_closes_in_math(j)
                    ):
                        break

                    if is_math_list[j]:
                        group.append(it_j)
                        open_paren_balance += it_j.text.count("(") - it_j.text.count(")")
                        j += 1
                    elif not txt_j and j + 1 < n and is_math_list[j + 1]:
                        group.append(it_j)
                        j += 1
                    elif (
                        group
                        and open_paren_balance > 0
                        and txt_j.startswith(")")
                        and abs(it_j.bbox[1] - ref_prev.bbox[1]) <= 6.0
                        and (it_j.bbox[0] - ref_prev.bbox[2]) <= 4.0
                    ):
                        group.append(it_j)
                        open_paren_balance += it_j.text.count("(") - it_j.text.count(")")
                        j += 1
                    elif (
                        group
                        and txt_j == "!"
                        and abs(it_j.bbox[1] - ref_prev.bbox[1]) <= 6.0
                        and (it_j.bbox[0] - ref_prev.bbox[2]) <= 3.0
                    ):
                        group.append(it_j)
                        j += 1
                    elif (
                        j + 1 < n
                        and is_math_list[j + 1]
                        and abs(it_j.bbox[1] - ref_prev.bbox[1]) <= 6.0
                        and abs(items[j + 1].bbox[1] - it_j.bbox[1]) <= 6.0
                        and re.match(r"^[\d\s.,:;+=\-*/!_~^…≤≥()\[\]{}|]+$", it_j.text)
                        and len(txt_j) <= 6
                        and not (txt_j in (",", ";", ":") and "(" in items[j + 1].text)
                    ):
                        if "(" in txt_j and ")" not in txt_j and not _paren_closes_in_math(j):
                            break
                        group.append(it_j)
                        open_paren_balance += it_j.text.count("(") - it_j.text.count(")")
                        j += 1
                    else:
                        break

                if use_words and len(group) > 1:
                    parts_g: list[str] = [group[0].text]
                    for k_idx in range(1, len(group)):
                        prev_g = group[k_idx - 1]
                        curr_g = group[k_idx]
                        gap_x = curr_g.bbox[0] - prev_g.bbox[2]
                        ref_sz = getattr(prev_g, "font_size", 10.0) or 10.0
                        is_rel_boundary = (
                            curr_g.text.startswith(("=", "<", ">", "≤", "≥", "≠", "≈"))
                            or prev_g.text.endswith(("=", "<", ">", "≤", "≥", "≠", "≈"))
                        )
                        if (
                            prev_g.text.endswith((",", ";", ":"))
                            or (not is_rel_boundary and gap_x >= max(2.2, ref_sz * 0.20))
                        ):
                            parts_g.append(" ")
                        parts_g.append(curr_g.text)
                    raw_content = "".join(parts_g).strip()
                else:
                    raw_content = "".join(s.text for s in group).strip()

                # Peel unmatched leading opening brackets and trailing clause punctuation / unmatched closing brackets
                orig_len = max(1, len(raw_content))
                prefix_peeled = ""
                suffix_peeled = ""

                while raw_content and raw_content[0] == "(" and raw_content.count("(") > raw_content.count(")"):
                    prefix_peeled += "("
                    raw_content = raw_content[1:].lstrip()
                while raw_content and raw_content[0] == "[" and raw_content.count("[") > raw_content.count("]"):
                    prefix_peeled += "["
                    raw_content = raw_content[1:].lstrip()

                while len(raw_content) > 1:
                    if raw_content.endswith((",", ";", ":")) or (
                        raw_content.endswith(".") and not raw_content.endswith("..")
                    ):
                        suffix_peeled = raw_content[-1] + suffix_peeled
                        raw_content = raw_content[:-1].rstrip()
                    elif raw_content.endswith(")") and raw_content.count(")") > raw_content.count("("):
                        suffix_peeled = ")" + suffix_peeled
                        raw_content = raw_content[:-1].rstrip()
                    elif raw_content.endswith("]") and raw_content.count("]") > raw_content.count("["):
                        suffix_peeled = "]" + suffix_peeled
                        raw_content = raw_content[:-1].rstrip()
                    else:
                        break

                if not raw_content:
                    masked_parts.append("".join(s.text for s in group))
                    i = j
                    continue

                placeholder = f"<b{token_id_counter}></b{token_id_counter}>"
                min_x0 = min(s.bbox[0] for s in group)
                min_y0 = min(s.bbox[1] for s in group)
                max_x1 = max(s.bbox[2] for s in group)
                max_y1 = max(s.bbox[3] for s in group)
                total_w = max(0.0, max_x1 - min_x0)
                if prefix_peeled and total_w > 2.0:
                    min_x0 += total_w * (len(prefix_peeled) / orig_len)
                if suffix_peeled and total_w > 2.0:
                    max_x1 -= total_w * (len(suffix_peeled) / orig_len)

                token = FormulaToken(
                    token_id=token_id_counter,
                    placeholder=placeholder,
                    raw_content=raw_content,
                    bbox=(min_x0, min_y0, max(min_x0 + 1.0, max_x1), max_y1),
                    font_name=group[0].font_name,
                )
                tokens.append(token)
                piece = f"{prefix_peeled} {placeholder} {suffix_peeled}".strip()
                masked_parts.append(f" {piece} ")
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

        # Strip trailing TOC dot-leader + optional page number before NMT so providers
        # only translate the clean heading and never truncate or drop page numbers.
        m_toc_raw = re.search(r"^(.*?\S)(\s*[\.\…]{3,}\s*(?:\d+\s*)?)$", raw_text.strip())
        if m_toc_raw:
            masked_text = re.sub(r"\s*[\.\…]{3,}\s*(?:<b\d+></b\d+>\s*|\d+\s*)?$", "", masked_text).strip()
            if tokens and re.match(r"^[\.\…\s\d]+$", tokens[-1].raw_content) and tokens[-1].placeholder not in masked_text:
                tokens.pop()

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
            result = result.replace(token.placeholder, f"⟦RESTORED_{token.token_id}⟧")

        # Remove any leftover deformed XML placeholder tags BEFORE restoring math content
        # so math inequalities like 'a<b then b>a' are never matched as '<b...>' tags.
        result = re.sub(r"<\s*/?\s*b\d+\s*>", "", result, flags=re.IGNORECASE)

        for token in segment.tokens:
            marker = f"⟦RESTORED_{token.token_id}⟧"
            ph = token.placeholder
            had_leading_space = bool(re.search(r"\s" + re.escape(ph), segment.masked_text))
            had_trailing_space = bool(re.search(re.escape(ph) + r"\s", segment.masked_text))
            if had_leading_space:
                result = re.sub(r"(?<=[^\W_])" + re.escape(marker), " " + marker, result)
            if had_trailing_space:
                result = re.sub(re.escape(marker) + r"(?=[^\W_])", marker + " ", result)
            result = result.replace(marker, token.raw_content)

        # Typography & punctuation spacing cleanup around restored math tokens:
        # 1. Remove artificial spaces before punctuation/closing brackets and after opening brackets
        result = re.sub(r"\s+([,.;:!?)\]])", r"\1", result)
        result = re.sub(r"([(\[])\s+", r"\1", result)
        # 2. Ensure a space after semicolons when followed by non-space
        result = re.sub(r";(?=\S)", "; ", result)
        # 3. Ensure a space after commas when followed by letters, Greek symbols, ellipsis, or comparisons (preserving decimal commas like 1,566)
        result = re.sub(r",(?=[A-Za-zα-ωΑ-Ω…(])", ", ", result)
        result = re.sub(r",(?=\d+\s*[<>≠=≤≥])", ", ", result)
        # 4. Normalize asymmetric spacing around binary comparison operators (e.g. 'b≠ 1' -> 'b≠1')
        result = re.sub(r"(?<=\S)([≠≤≥<>])\s+(?=\S)", r"\1", result)
        # 5. Collapse excess spaces after section/list markers (e.g. 'A.     不定积分' -> 'A. 不定积分', '1 .  定义' -> '1. 定义')
        result = re.sub(r"^(\s*(?:[IVXLCDM]+|\d+|[A-Za-z]))\s*([.)])\s+", r"\1\2 ", result)
        # 6. Tighten internal spaces inside coordinate tuples (e.g. '( 0 , c )' -> '(0, c)')
        result = re.sub(r"\(\s*([0-9a-zA-Z′']+)\s*,\s*([0-9a-zA-Z′']+)\s*\)", r"(\1, \2)", result)

        # Re-attach any TOC dot-leader + page number suffix stripped prior to NMT
        m_toc_raw = re.search(r"^(.*?\S)(\s*[\.\…]{3,}\s*(?:\d+\s*)?)$", segment.raw_text.strip())
        if m_toc_raw:
            toc_suffix = m_toc_raw.group(2)
            result_clean = re.sub(r"\s*[\.\…]{2,}\s*(?:\d+\s*)?$", "", result.strip()).strip()
            result = f"{result_clean}{toc_suffix}"

        return result
