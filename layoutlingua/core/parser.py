"""High-fidelity PDF document parser using PyMuPDF.

Extracts page geometry, text blocks, glyph/character spans, fonts,
and styling into decoupled DocumentIR data structures.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pymupdf

from layoutlingua.core.ir import (
    CharInfo,
    DocumentIR,
    GlyphSpan,
    LayoutRegion,
    PageGeometry,
    PageIR,
    TextBlock,
)

import unicodedata
from dataclasses import dataclass

# Standard ISO/MathML mathematical functions (language-neutral international operators)
_ISO_MATH_FUNCTIONS = frozenset({
    "sin", "cos", "tan", "cot", "tg", "cotg", "cottan", "cotan", "cosec", "cossec", "sec", "csc",
    "arcsin", "arccos", "arctan", "arccot", "arctg", "arccotg", "arccottan", "arccotan",
    "sinh", "cosh", "tanh", "coth",
    "log", "ln", "lg", "exp",
    "lim", "liminf", "limsup",
    "max", "min", "sup", "inf",
    "det", "deg", "rad", "dim", "ker", "hom",
    "gcd", "lcm", "arg", "mod", "sgn",
    "vec", "cdot", "times", "div", "sqrt", "frac", "prod",
})

# Standard TeX / Scientific publishing formula font family pattern
# Compatible with open-source PDFMathTranslate (pdf2zh) and BabelDoc
FORMULA_FONT_PATTERN = re.compile(
    r"(?:^(?:[A-Z]{6}\+)?(?:CM[^R]|AMS|MS[AB]M|XY|MT2|MT\s*Extra|BL|RM|EU[FMX]|LA|RSFS|LINE|LCIRCLE|TeX-)"
    r"|rsfs|txsy|wasy|stmary|mathtype|cmmi|cmsy|cmex|msam|msbm|eufm|euex"
    r"|.*Mono|.*Code|.*Ital|.*Oblique|.*Sym|.*Math)",
    re.IGNORECASE,
)

# Standard international mathematical functions pattern (word-bounded, plus unspaced trig/log before a single math var/digit)
MATH_FUNC_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(sorted(_ISO_MATH_FUNCTIONS, key=len, reverse=True))
    + r")\b"
    + r"|\b(?:sin|cos|tan|cot|tg|cotg|cottan|cotan|cosec|cossec|sec|csc|arcsin|arccos|arctan|arccot|arccottan|arccotan|sinh|cosh|tanh|coth|log|ln|lg)(?=[a-df-rt-zα-ωΑ-Ω0-9]\b|[\W_]|$)",
    re.IGNORECASE,
)

# Mathematical relation and structure operators
MATH_RELATION_PATTERN = re.compile(
    r"[=≈≤≥<>±∓∫∑∏√°′″~¬∂∇∅∈∉∋∩∪⊂⊃⊆⊇⊕⊗⊥∠≠≡∝∣∥]"
    r"|\\approx|\\le|\\ge|\\ne|\\equiv|\\in|\\subset|\\cup|\\cap"
)

# Mathematical and Greek symbol pattern
GREEK_AND_MATH_SYMBOLS_PATTERN = re.compile(
    r"[\u0370-\u03ff\u1f00-\u1fff\u2100-\u214f\u2200-\u22ff=≈≤≥<>±∓∫∑∏√°′″^_\-+*/÷%|~¬∂∇∅∈∉∋∩∪⊂⊃⊆⊇⊕⊗⊥∠≠≡!\\…∗;()\[\]{}|^_~]"
)


@dataclass(frozen=True)
class ParserConfig:
    """Configurable layout parser parameters and thresholds."""

    formula_font_pattern: re.Pattern = FORMULA_FONT_PATTERN
    min_block_height_for_split_pt: float = 25.0
    default_fallback_font_size: float = 10.0
    min_math_density_ratio: float = 0.55
    preserve_foreign_blocks: bool = True


_NORMALIZER_MANAGERSingleton = None


def _get_normalizer_manager():
    """Lazily construct the text normalizer chain (VNI/TCVN3 legacy decode + NFC)."""
    global _NORMALIZER_MANAGERSingleton
    if _NORMALIZER_MANAGERSingleton is None:
        from layoutlingua.processing.normalizers.manager import TextNormalizationManager

        _NORMALIZER_MANAGERSingleton = TextNormalizationManager()
    return _NORMALIZER_MANAGERSingleton


def _is_math_char(ch: str) -> bool:
    """Check if a character is a mathematical symbol, Greek letter, or operator (language-agnostic)."""
    cat = unicodedata.category(ch)
    if cat in ("Sm", "So"):
        return True
    code = ord(ch)
    if 0x0370 <= code <= 0x03FF or 0x1F00 <= code <= 0x1FFF:  # Greek
        return True
    if 0x2100 <= code <= 0x23FF or 0x2A00 <= code <= 0x2AFF or 0x2200 <= code <= 0x22FF:  # Math operators
        return True
    if 0x1D400 <= code <= 0x1D7FF:  # Mathematical alphanumeric symbols
        return True
    if ch in "=≈≤≥<>±∓∫∑∏√°′″^_-+*/÷%|~¬∂∇∅∈∉∋∩∪⊂⊃⊆⊇⊕⊗⊥∠!\\()[]{}…∗;:≠≡":
        return True
    return False


_VOWEL_PATTERN = re.compile(
    r"[aeiouyàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]",
    re.IGNORECASE,
)

_COMMON_2CHAR_PROSE = frozenset({
    "or", "on", "no", "to", "in", "of", "by", "at", "if", "up", "as", "so", "be", "do", "go", "is", "it", "an", "we", "us",
})


def _extract_prose_tokens(text: str) -> list[str]:
    """Extract natural language prose words (language-agnostic across all Unicode scripts).

    A prose word consists of consecutive Unicode alphabetic letters >= 2 chars
    that are NOT international mathematical function names, contain vowels,
    and are not uppercase geometric variable clusters (e.g. ABC, XYZ).
    """
    # Strip assembly/shell $-prefixed register/variable identifiers (e.g. $zero, $at, $sp, $ra)
    t_no_reg = re.sub(r"\$[A-Za-z_][A-Za-z0-9_]*", " ", text)
    # Strip superscripts, subscripts, fractions, degree marks, and mathematical symbols
    t_clean = re.sub(
        r"[\u00b0-\u00be\u2070-\u209f\u0370-\u03ff\u2100-\u22ff=≈≤≥<>±∓∫∑∏√°′″^_\-+*/÷%|~¬∂∇∅∈∉∋∩∪⊂⊃⊆⊇⊕⊗⊥∠≠≡!\\…∗;()\[\]{}|^_~:,]",
        " ",
        t_no_reg,
    )
    # Strip standard ISO math functions and hexadecimal/radix literals with base suffix (e.g. 7fffhex, fffchex)
    t_clean = MATH_FUNC_PATTERN.sub(" ", t_clean)
    t_clean = re.sub(r"\b[0-9a-fA-F]+(?:hex|bin|oct|dec)\b", " ", t_clean)
    raw_tokens = re.findall(r"\b[^\W\d_]{2,}\b", t_clean, re.UNICODE)
    valid_prose = []
    _SEQUENTIAL_VAR_RUNS = {
        "abc", "bcd", "cde", "def", "ijk", "lmn", "mno", "opq", "pqr", "rst", "stu", "uvw", "vwx", "wxy", "xyz",
        "abx", "axb", "cbx", "xab", "xbc",
    }
    for t in raw_tokens:
        t_low = t.lower()
        if len(t) == 2 and t.isascii():
            if t_low not in _COMMON_2CHAR_PROSE or t.isupper():
                continue
        if t_low in _ISO_MATH_FUNCTIONS or t_low in _SEQUENTIAL_VAR_RUNS:
            continue
        # Calculus differential products (e.g. udx, vdx, wdx, xdx, ydy, zdz, udv, vdu, tdt)
        if t.isascii() and re.match(r"^[a-z]{1,2}d[xyzuvt]$", t):
            continue
        # 2-4 letter uppercase Latin clusters are geometric vertices / matrices (e.g. ABC, BCD, XYZ)
        if re.match(r"^[A-Z]{2,4}$", t):
            continue
        # Mixed-case ASCII clusters (e.g. aABb, mAB, xOM, SignExtImm, BranchAddr)
        if t.isascii() and re.search(r"[a-z][A-Z]|[A-Z]{2,}[a-z]", t):
            continue
        # Latin words without vowels are math variable products / differentials (e.g. bdx, xdx, uvw, Bhc)
        if re.search(r"[a-zA-Z]", t) and not _VOWEL_PATTERN.search(t):
            continue
        valid_prose.append(t)
    return valid_prose


def _compute_math_metrics(text: str, spans: list[GlyphSpan]) -> tuple[float, int, int]:
    """Compute (math_density, math_symbols_count, prose_word_count) for a text block."""
    non_space = [ch for ch in text if not ch.isspace()]
    if not non_space:
        return 1.0, 0, 0

    prose_tokens = _extract_prose_tokens(text)
    prose_word_count = len(prose_tokens)

    math_chars = 0
    math_symbols = 0
    for ch in non_space:
        if _is_math_char(ch):
            math_chars += 1
            math_symbols += 1
        elif ch.isdigit():
            math_chars += 1

    math_font_chars = 0
    for s in spans:
        if s.is_math_or_symbol or bool(FORMULA_FONT_PATTERN.search(s.font_name)):
            math_font_chars += len([ch for ch in s.text if not ch.isspace()])

    effective_math_chars = max(math_chars, math_font_chars)
    math_density = effective_math_chars / len(non_space)

    return math_density, math_symbols, prose_word_count


def _is_pure_formula_block(spans: list[GlyphSpan], config: ParserConfig = ParserConfig()) -> bool:
    """Detect if a block represents a display formula / equation using font metadata and structural tokens.
    Adopts the language-agnostic open-source pattern from PDFMathTranslate (pdf2zh) and BabelDOC.
    """
    meaningful_spans = [s for s in spans if s.text.strip()]
    if not meaningful_spans:
        return True

    full_text = "".join(s.text for s in spans).strip()
    if not full_text:
        return True

    # Standalone 1-4 char pure-ASCII all-italic token (e.g. "abc", "udx", "Ach", "uvw", "arc", "arn")
    # inside an equation is a mathematical variable product, never a standalone natural-language paragraph.
    if (
        re.fullmatch(r"[A-Za-z]{1,4}", full_text)
        and all((s.flags & 2) or "ital" in s.font_name.lower() or "oblique" in s.font_name.lower() for s in meaningful_spans)
        and not any("vni" in s.font_name.lower() for s in meaningful_spans)
    ):
        return True

    # Dotted technical identifier or opcode mnemonic without spaces (e.g. "round.w.f", "trunc.w.f", "ceil.w.f")
    if re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", full_text):
        return True

    # Assembly register / variable identifier starting with $ (e.g. "$zero", "$at", "$sp", "$ra")
    if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*(?:\s+\$[A-Za-z_][A-Za-z0-9_]*)*", full_text):
        return True

    # Monospace code / instruction mnemonic token (e.g. "and", "or", "nor", "sub", "subu", "syscall", "sync mfhi (2)", "round.w.f")
    _mono_keys = ("courier", "consolas", "menlo", "monaco", "monospace", "typewriter", "cmtt", "txtt", "dejavusansmono", "liberationsansmono", "firacode", "jetbrainsmono")
    if (
        re.fullmatch(r"[\$a-z0-9_.*]+(?:\s+(?:[\$a-z0-9_.*]+|\(\d+\)))*", full_text)
        and any(
            (s.flags & 8) or any(mk in s.font_name.lower() for mk in _mono_keys)
            for s in meaningful_spans
        )
        and all(
            (s.flags & 8)
            or any(mk in s.font_name.lower() for mk in _mono_keys)
            or (s.flags & 2)
            or s.text.strip() in (".", "f", "s", "d", "w")
            or bool(re.fullmatch(r"\(\d+\)", s.text.strip()))
            for s in meaningful_spans
        )
    ):
        return True

    math_density, math_sym_count, prose_count = _compute_math_metrics(full_text, spans)

    # 1. Font metadata check: if all meaningful spans use recognized math/formula/symbol fonts
    # A block containing natural language prose words (>= 1 prose token) is prose text, never a pure formula
    if prose_count == 0 and all(s.is_math_or_symbol or bool(config.formula_font_pattern.search(s.font_name)) for s in meaningful_spans):
        return True

    # 2. Structural equation & token analysis
    has_rel = bool(MATH_RELATION_PATTERN.search(full_text))

    # Pure equation with mathematical relation and zero prose words
    if has_rel and prose_count == 0:
        return True

    # Equation with relation operator and at most 1 short non-prose variable cluster (e.g. S = abc / 4R = pr)
    # A token carrying non-ASCII diacritics is a natural-language word in some script
    # (e.g. Vietnamese "Hàm", "số") and is never a variable cluster — mirroring the
    # TS engine's multilingual-script protection for prose beside 2D formulas.
    prose_tokens = _extract_prose_tokens(full_text)
    if has_rel and len(prose_tokens) <= 1 and math_sym_count >= 2 and all(
        len(w) <= 3 and w.isascii() for w in prose_tokens
    ):
        return True

    # Heavy math symbol dominance with zero prose words
    if math_sym_count >= 2 and prose_count == 0:
        return True

    # High mathematical density with zero prose words
    if math_density >= config.min_math_density_ratio and prose_count == 0:
        return True

    # 3. Disjoint / fragmented math expression (e.g. fractions, superscripts like "0 ... ...", "k k n n k", "1 1 ! ! 1 !", "2! 1 ... 1 ... !")
    if prose_count == 0:
        words = re.findall(r"\b[^\W\d_]+\b", full_text, re.UNICODE)
        if len(words) == 0:
            return True
        if re.search(r"[=≈≤≥<>±∓∫∑∏√!/\\+\\-∗;()\[\]{}|^_~…:≠]", full_text):
            return True
        tokens = [t for t in re.split(r"\s+", full_text) if t]
        def is_math_token(t: str) -> bool:
            return (
                len(t) <= 2
                or t.isdigit()
                or t.startswith(".")
                or t.lower() in _ISO_MATH_FUNCTIONS
                or bool(MATH_FUNC_PATTERN.fullmatch(t))
                or not bool(_VOWEL_PATTERN.search(t))
                or bool(re.search(r"(?:dx|dy|dz|dt)$", t, re.I))
            )
        if tokens and all(is_math_token(t) for t in tokens):
            return True

    return False


def _tight_line_x_bounds(line: dict) -> tuple[float, float] | None:
    """Return tight (x0, x1) horizontal bounds of non-whitespace spans in a raw line."""
    xs0: list[float] = []
    xs1: list[float] = []
    for s in line.get("spans", []):
        txt = s.get("text")
        if txt is None and "chars" in s:
            txt = "".join(c.get("c", "") for c in s["chars"])
        if not (txt or "").strip():
            continue
        chars = [c for c in s.get("chars", []) if str(c.get("c", "")).strip()]
        if chars:
            xs0.append(min(float(c.get("bbox", s.get("bbox", (0, 0, 0, 0)))[0]) for c in chars))
            xs1.append(max(float(c.get("bbox", s.get("bbox", (0, 0, 0, 0)))[2]) for c in chars))
        else:
            sb = s.get("bbox")
            if sb and sb[2] > sb[0]:
                xs0.append(float(sb[0]))
                xs1.append(float(sb[2]))
    if not xs0 or not xs1:
        return None
    return (min(xs0), max(xs1))


_SUPERSCRIPT_MAP: dict[str, str] = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "\u2212": "⁻", "\uf02d": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ", "k": "ᵏ",
    "o": "°", "ο": "°", "\u03bf": "°", "°": "°", "\uf06f": "°",
}

_SUBSCRIPT_MAP: dict[str, str] = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "\u2212": "₋", "\uf02d": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
    "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ",
    "v": "ᵥ", "x": "ₓ",
}


def _raw_span_text(s: dict) -> str:
    txt = s.get("text")
    if txt is None and "chars" in s:
        txt = "".join(c.get("c", "") for c in s["chars"])
    return txt or ""


def _split_main_span_for_inline_scripts(span: dict, small_spans: list[dict], main_fs: float) -> list[dict]:
    """Split a main span at internal char gaps or synthetic space chars occupied by an inline sub/superscript."""
    chars = span.get("chars")
    if not chars or len(chars) <= 1:
        return [span]
    sb = span.get("bbox", (0.0, 0.0, 0.0, 0.0))
    ms_cy = (float(sb[1]) + float(sb[3])) / 2.0

    # Find relevant small spans on this vertical band and within horizontal range
    relevant_ss = []
    for ss in small_spans:
        ssb = ss.get("bbox", (0.0, 0.0, 0.0, 0.0))
        ss_cy = (float(ssb[1]) + float(ssb[3])) / 2.0
        ss_cx = (float(ssb[0]) + float(ssb[2])) / 2.0
        if abs(ss_cy - ms_cy) <= main_fs * 0.85 and float(sb[0]) - 2.0 <= ss_cx <= float(sb[2]) + 2.0:
            relevant_ss.append((ss_cx, float(ssb[0]), float(ssb[2]), ss))
    if not relevant_ss:
        return [span]

    chunks: list[list[dict]] = []
    cur: list[dict] = []
    i = 0
    n = len(chars)
    while i < n:
        ch = chars[i]
        cb = ch.get("bbox", sb)
        ch_str = str(ch.get("c", ""))

        # Case A: synthetic space char whose bbox is occupied by a small span
        if ch_str in (" ", "\xa0") and cur:
            cx0, cx1 = float(cb[0]), float(cb[2])
            matched_ss = any(
                (cx0 - 2.0 <= ss_cx <= cx1 + 2.0) or (min(cx1, ss_x1) - max(cx0, ss_x0) >= 0.5)
                for (ss_cx, ss_x0, ss_x1, _) in relevant_ss
            )
            if matched_ss:
                # Check next non-space char in this span
                next_ch_str = ""
                for j in range(i + 1, n):
                    nc = str(chars[j].get("c", ""))
                    if nc.strip():
                        next_ch_str = nc
                        break
                chunks.append(cur)
                cur = []
                # Keep space only if the next character starts a natural prose word
                if next_ch_str and next_ch_str.isalpha():
                    adj_ch = dict(ch)
                    adj_b = list(cb)
                    adj_b[0] = max(float(cb[0]), min(float(cb[2]) - 0.5, float(cb[0]) + (float(cb[2]) - float(cb[0])) * 0.6))
                    adj_ch["bbox"] = tuple(adj_b)
                    cur.append(adj_ch)
                i += 1
                continue

        # Case B: horizontal gap before ch occupied by a small span
        if cur:
            prev_x1 = float(cur[-1].get("bbox", sb)[2])
            curr_x0 = float(cb[0])
            if (curr_x0 - prev_x1) >= 1.8:
                matched_gap = any(
                    prev_x1 - 1.8 <= ss_cx <= curr_x0 + 1.8
                    for (ss_cx, _, _, _) in relevant_ss
                )
                if matched_gap:
                    chunks.append(cur)
                    cur = []

        cur.append(ch)
        i += 1

    if cur:
        chunks.append(cur)
    if len(chunks) <= 1:
        return [span]

    out_spans: list[dict] = []
    for grp in chunks:
        gx0 = min(float(c.get("bbox", sb)[0]) for c in grp)
        gy0 = min(float(c.get("bbox", sb)[1]) for c in grp)
        gx1 = max(float(c.get("bbox", sb)[2]) for c in grp)
        gy1 = max(float(c.get("bbox", sb)[3]) for c in grp)
        ns = dict(span)
        ns["chars"] = grp
        ns["text"] = "".join(str(c.get("c", "")) for c in grp)
        ns["bbox"] = (gx0, gy0, gx1, gy1)
        if grp and "origin" in grp[0]:
            ns["origin"] = grp[0]["origin"]
        out_spans.append(ns)
    return out_spans


def _normalize_raw_block_1d_scripts(raw_lines: list[dict], config: ParserConfig = ParserConfig()) -> list[dict]:
    """Coalesce non-stacked 1D sub/superscript spans into their parent prose line as Unicode characters.

    Leaves blocks with 2D vertically stacked sub+superscripts (e.g. C_n^k), multi-column layouts,
    or pure display formulas completely untouched.
    """
    if not raw_lines:
        return raw_lines

    from layoutlingua.processing.text_sanitizer import sanitize_extracted_text

    norm_mgr = _get_normalizer_manager()
    all_non_empty: list[tuple[dict, float, str]] = []
    for l in raw_lines:
        for s in l.get("spans", []):
            raw_t = _raw_span_text(s)
            if not raw_t.strip():
                continue
            dec_t = norm_mgr.normalize_text(
                sanitize_extracted_text(raw_t),
                font_name=str(s.get("font", "")),
            ).text
            if not dec_t.strip():
                continue
            sz = float(s.get("size", config.default_fallback_font_size) or config.default_fallback_font_size)
            all_non_empty.append((s, sz, dec_t))

    if not all_non_empty:
        return raw_lines

    main_fs = max(sz for _, sz, _ in all_non_empty)
    if main_fs < 9.5:
        return raw_lines

    small_entries = [(s, sz, dec_t) for (s, sz, dec_t) in all_non_empty if sz < main_fs * 0.82]
    main_entries = [(s, sz, dec_t) for (s, sz, dec_t) in all_non_empty if sz >= main_fs * 0.82]
    if not main_entries or (not small_entries and len(raw_lines) <= 1):
        return raw_lines

    # Must contain natural prose words (never flatten pure display equations)
    full_block_text = " ".join(dec_t for _, _, dec_t in all_non_empty)
    if not _extract_prose_tokens(full_block_text):
        return raw_lines

    # Do not flatten if any line has dot leaders or if any two small spans are vertically stacked at the same X (e.g. C_n^k)
    if any("..." in dec_t or "…" in dec_t and dec_t.count(".") >= 3 for _, _, dec_t in all_non_empty):
        return raw_lines

    for idx1 in range(len(small_entries)):
        b1 = small_entries[idx1][0].get("bbox", (0.0, 0.0, 0.0, 0.0))
        cy1 = (float(b1[1]) + float(b1[3])) / 2.0
        for idx2 in range(idx1 + 1, len(small_entries)):
            b2 = small_entries[idx2][0].get("bbox", (0.0, 0.0, 0.0, 0.0))
            cy2 = (float(b2[1]) + float(b2[3])) / 2.0
            x_overlap = min(float(b1[2]), float(b2[2])) - max(float(b1[0]), float(b2[0]))
            if x_overlap > -1.5 and 3.0 <= abs(cy1 - cy2) <= main_fs * 1.15:
                return raw_lines

    # Do not flatten if any main span is an unmatched tall Symbol delimiter (e.g. \uf028 at 13.8pt)
    for ms, msz, _ in main_entries:
        mfont = str(ms.get("font", "") or "").lower()
        mraw = _raw_span_text(ms).strip()
        if "symbol" in mfont and mraw in ("\uf028", "\uf029", "\uf05b", "\uf05d", "\uf07b", "\uf07d"):
            return raw_lines

    # Verify every small span can be cleanly mapped to Unicode superscript or subscript characters
    small_spans_only = [s for s, _, _ in small_entries]
    main_spans_split: list[dict] = []
    for ms, _, _ in main_entries:
        main_spans_split.extend(_split_main_span_for_inline_scripts(ms, small_spans_only, main_fs))

    # Group main spans into visual rows by vertical center
    main_spans_split.sort(key=lambda s: (float(s.get("bbox", (0, 0, 0, 0))[1]) + float(s.get("bbox", (0, 0, 0, 0))[3])) / 2.0)
    rows: list[list[dict]] = []
    row_cys: list[float] = []
    row_tol = max(4.5, main_fs * 0.42)
    for ms in main_spans_split:
        mb = ms.get("bbox", (0.0, 0.0, 0.0, 0.0))
        cy = (float(mb[1]) + float(mb[3])) / 2.0
        if rows and abs(cy - row_cys[-1]) <= row_tol:
            rows[-1].append(ms)
            row_cys[-1] = sum((float(x.get("bbox", (0, 0, 0, 0))[1]) + float(x.get("bbox", (0, 0, 0, 0))[3])) / 2.0 for x in rows[-1]) / len(rows[-1])
        else:
            rows.append([ms])
            row_cys.append(cy)

    if not rows or (not small_entries and len(rows) >= len(raw_lines)):
        return raw_lines

    # Check if any row has a wide horizontal gap (> 9.5pt) not genuinely bridged by small spans
    for r_idx, r_spans in enumerate(rows):
        r_sorted = sorted(r_spans, key=lambda s: float(s.get("bbox", (0, 0, 0, 0))[0]))
        for k in range(len(r_sorted) - 1):
            x1_prev = float(r_sorted[k].get("bbox", (0, 0, 0, 0))[2])
            x0_next = float(r_sorted[k + 1].get("bbox", (0, 0, 0, 0))[0])
            if (x0_next - x1_prev) > 9.5:
                gap_ss = [
                    ss for ss in small_spans_only
                    if abs(((float(ss.get("bbox", (0, 0, 0, 0))[1]) + float(ss.get("bbox", (0, 0, 0, 0))[3])) / 2.0) - row_cys[r_idx]) <= main_fs * 0.85
                    and x1_prev - 2.0 <= float(ss.get("bbox", (0, 0, 0, 0))[0])
                    and float(ss.get("bbox", (0, 0, 0, 0))[2]) <= x0_next + 2.0
                ]
                if not gap_ss:
                    return raw_lines
                min_ss_x0 = min(float(ss.get("bbox", (0, 0, 0, 0))[0]) for ss in gap_ss)
                max_ss_x1 = max(float(ss.get("bbox", (0, 0, 0, 0))[2]) for ss in gap_ss)
                if (min_ss_x0 - x1_prev) > 3.5 or (x0_next - max_ss_x1) > 4.5:
                    return raw_lines

    # Map each small span to its parent row and convert characters
    row_main_bounds: list[tuple[float, float]] = []
    for r_spans in rows:
        ry0 = min(float(s.get("bbox", (0, 0, 0, 0))[1]) for s in r_spans)
        ry1 = max(float(s.get("bbox", (0, 0, 0, 0))[3]) for s in r_spans)
        row_main_bounds.append((ry0, ry1))

    for ss, s_sz, dec_t in small_entries:
        ssb = ss.get("bbox", (0.0, 0.0, 0.0, 0.0))
        ss_cy = (float(ssb[1]) + float(ssb[3])) / 2.0
        best_r = min(range(len(rows)), key=lambda idx: abs(ss_cy - row_cys[idx]))
        if abs(ss_cy - row_cys[best_r]) > main_fs * 0.90:
            return raw_lines

        clean_chars = [ch for ch in dec_t.strip() if not ch.isspace()]
        if not clean_chars:
            continue
        is_degree = all(ch in ("o", "ο", "\u03bf", "°", "\uf06f") for ch in clean_chars)
        is_super = is_degree or (ss_cy < row_cys[best_r] - 0.8) or (float(ssb[1]) < row_main_bounds[best_r][0] - 0.5)
        char_map = _SUPERSCRIPT_MAP if is_super else _SUBSCRIPT_MAP
        if not all(ch in char_map or ch in "<>,.;:/*" for ch in clean_chars):
            return raw_lines
        if not any(ch in char_map for ch in clean_chars) and len(clean_chars) > 2:
            return raw_lines

        # Verify horizontal attachment: a 1D script must either be a leading footnote number (1..9)
        # immediately before the first main span on the row, or attach to the right of a base span
        # (within 3.8pt) on the same row. Otherwise an external glyph from another raw block sits between them.
        row_First_x0 = min(float(ms.get("bbox", (0, 0, 0, 0))[0]) for ms in rows[best_r])
        is_leading_footnote_num = (
            is_super
            and all(ch.isdigit() for ch in clean_chars)
            and float(ssb[2]) <= row_First_x0 + 2.0
            and (row_First_x0 - float(ssb[2])) <= 6.0
        )
        if not is_leading_footnote_num:
            attached_to_base = any(
                -2.0 <= (float(ssb[0]) - float(ms.get("bbox", (0, 0, 0, 0))[2])) <= 3.8
                for ms in rows[best_r]
            ) or any(
                other_ss is not ss
                and abs(((float(other_ss.get("bbox", (0, 0, 0, 0))[1]) + float(other_ss.get("bbox", (0, 0, 0, 0))[3])) / 2.0) - row_cys[best_r]) <= main_fs * 0.85
                and -1.5 <= (float(ssb[0]) - float(other_ss.get("bbox", (0, 0, 0, 0))[2])) <= 2.5
                for other_ss in small_spans_only
            )
            if not attached_to_base:
                return raw_lines

        mapped_str = "".join(char_map.get(ch, ch) for ch in clean_chars)
        ry0, ry1 = row_main_bounds[best_r]
        # Inherit font & flags from nearest main span on the same row
        ref_main = min(rows[best_r], key=lambda ms: abs(float(ms.get("bbox", (0, 0, 0, 0))[2]) - float(ssb[0])))
        new_ss = dict(ss)
        new_ss["text"] = mapped_str
        new_ss["size"] = float(ref_main.get("size", main_fs) or main_fs)
        new_ss["font"] = ref_main.get("font", ss.get("font", "Times New Roman"))
        new_ss["flags"] = int(ref_main.get("flags", 0)) & ~1
        new_ss["bbox"] = (float(ssb[0]), ry0, float(ssb[2]), ry1)
        new_ss["origin"] = (float(ssb[0]), float(ref_main.get("origin", (ssb[0], ry1 - 2.0))[1]))
        if "chars" in new_ss:
            step = max(0.5, (float(ssb[2]) - float(ssb[0])) / max(1, len(mapped_str)))
            new_ss["chars"] = [
                {
                    "c": ch,
                    "bbox": (float(ssb[0]) + idx_c * step, ry0, float(ssb[0]) + (idx_c + 1) * step, ry1),
                    "origin": new_ss["origin"],
                }
                for idx_c, ch in enumerate(mapped_str)
            ]
        rows[best_r].append(new_ss)

    # Reconstruct normalized raw lines (one per visual row, sorted left-to-right by x0)
    template_line = raw_lines[0]
    normalized_lines: list[dict] = []
    for r_spans in rows:
        r_spans.sort(key=lambda s: float(s.get("bbox", (0, 0, 0, 0))[0]))
        lx0 = min(float(s.get("bbox", (0, 0, 0, 0))[0]) for s in r_spans)
        ly0 = min(float(s.get("bbox", (0, 0, 0, 0))[1]) for s in r_spans)
        lx1 = max(float(s.get("bbox", (0, 0, 0, 0))[2]) for s in r_spans)
        ly1 = max(float(s.get("bbox", (0, 0, 0, 0))[3]) for s in r_spans)
        nl = dict(template_line)
        nl["spans"] = r_spans
        nl["bbox"] = (lx0, ly0, lx1, ly1)
        normalized_lines.append(nl)

    return normalized_lines


def _extract_page_vertical_dividers(page: Any) -> list[tuple[float, float, float]]:
    """Extract 1D vertical table/column divider segments (vx, vy0, vy1) from page vector drawings."""
    dividers: list[tuple[float, float, float]] = []
    try:
        drawings = page.get_drawings()
    except Exception:
        return dividers
    for d in drawings:
        items = d.get("items") or []
        for it in items:
            op = it[0] if it else ""
            if op == "l" and len(it) >= 3:
                p1, p2 = it[1], it[2]
                x0, y0 = min(float(p1.x), float(p2.x)), min(float(p1.y), float(p2.y))
                x1, y1 = max(float(p1.x), float(p2.x)), max(float(p1.y), float(p2.y))
                if (x1 - x0) <= 3.0 and (y1 - y0) >= 12.0:
                    dividers.append(((x0 + x1) * 0.5, y0, y1))
            elif op == "re" and len(it) >= 2:
                r = it[1]
                x0, y0, x1, y1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)
                if (x1 - x0) <= 3.0 and (y1 - y0) >= 12.0:
                    dividers.append(((x0 + x1) * 0.5, y0, y1))
    return dividers


def _split_lines_across_horizontal_gaps(
    lines: list[dict],
    min_gap_pt: float = 6.5,
    vertical_dividers: list[tuple[float, float, float]] | None = None,
) -> list[dict]:
    """Split a raw PyMuPDF line if its non-empty spans are separated by:
    - a wide horizontal gap (>= min_gap_pt),
    - a vertical vector table/column divider line,
    - an intervening sibling span from another line in the same raw block (e.g. stacked C_n^{k-1}),
    - a 2D fraction / multi-row vertical baseline shift, or
    - a tall/unmatched Symbol delimiter (\uf028, \uf029, etc.) adjacent to prose.
    """
    line_span_boxes: list[tuple[int, float, float, float, float, float]] = []
    for li_idx, l_item in enumerate(lines):
        for sp in l_item.get("spans", []):
            stxt = _raw_span_text(sp)
            if not stxt.strip():
                continue
            sb_box = sp.get("bbox", (0.0, 0.0, 0.0, 0.0))
            sp_sz = float(sp.get("size", 12.0) or 12.0)
            line_span_boxes.append((li_idx, float(sb_box[0]), float(sb_box[1]), float(sb_box[2]), float(sb_box[3]), sp_sz))

    out: list[dict] = []
    for li_idx, line in enumerate(lines):
        l_spans = line.get("spans", [])
        if len(l_spans) <= 1:
            out.append(line)
            continue

        line_full_text = "".join(_raw_span_text(s) for s in l_spans)
        if re.search(r"[\.\…]{3,}", line_full_text):
            out.append(line)
            continue

        groups: list[list[dict]] = []
        curr_group: list[dict] = []
        last_non_empty_x1: float | None = None
        last_non_empty_y0: float | None = None
        last_non_empty_size: float | None = None
        last_non_empty_is_sym_delim: bool | None = None
        last_non_empty_is_mono_code: bool | None = None
        _mono_keys = ("courier", "consolas", "menlo", "monaco", "monospace", "typewriter", "cmtt", "txtt", "dejavusansmono", "liberationsansmono", "firacode", "jetbrainsmono")

        for s in l_spans:
            txt = _raw_span_text(s)
            sb = s.get("bbox", (0.0, 0.0, 0.0, 0.0))
            s_w = float(sb[2]) - float(sb[0])
            s_size = float(s.get("size", 12.0) or 12.0)
            s_font = str(s.get("font", "") or "").lower()
            s_flags = int(s.get("flags", 0) or 0)
            s_clean = txt.strip()

            if not s_clean:
                # A wide whitespace-only span (>= 6.0pt) acts as a column/brace separator
                if s_w >= 6.0 and curr_group:
                    groups.append(curr_group)
                    curr_group = []
                    last_non_empty_x1 = None
                    last_non_empty_y0 = None
                    last_non_empty_size = None
                    last_non_empty_is_sym_delim = None
                    last_non_empty_is_mono_code = None
                elif curr_group:
                    curr_group.append(s)
                continue

            is_sym_delim = (
                "symbol" in s_font
                and s_clean in ("\uf028", "\uf029", "\uf05b", "\uf05d", "\uf07b", "\uf07d", "(", ")", "[", "]", "{", "}")
            )
            gap_x = (float(sb[0]) - last_non_empty_x1) if last_non_empty_x1 is not None else 0.0
            prev_non_ws_txt = ""
            for prev_sp in reversed(curr_group):
                ptxt = _raw_span_text(prev_sp).strip()
                if ptxt:
                    prev_non_ws_txt = ptxt
                    break
            is_dotted_continuation = bool(
                last_non_empty_is_mono_code
                and gap_x <= 1.5
                and (s_clean.startswith(".") or prev_non_ws_txt.endswith("."))
            )
            is_mono_code = (
                (
                    (s_flags & 8) != 0
                    or any(mk in s_font for mk in _mono_keys)
                    or is_dotted_continuation
                )
                and bool(re.fullmatch(r"[a-z0-9_.*]+", s_clean))
            )
            is_h_gap = last_non_empty_x1 is not None and gap_x >= min_gap_pt

            has_vertical_divider = False
            if last_non_empty_x1 is not None and vertical_dividers:
                for vx, vy0, vy1 in vertical_dividers:
                    if (last_non_empty_x1 - 1.2 <= vx <= float(sb[0]) + 1.2) and (
                        min(float(sb[3]), vy1) - max(float(sb[1]), vy0) >= 2.5
                    ):
                        has_vertical_divider = True
                        break

            # Check if another line in the same raw block has a span horizontally inside [last_non_empty_x1, sb[0]]
            s_cy = (float(sb[1]) + float(sb[3])) / 2.0
            has_intervening_sibling = False
            if last_non_empty_x1 is not None and gap_x >= 1.5:
                for other_li, ox0, oy0, ox1, oy1, _osz in line_span_boxes:
                    if other_li == li_idx:
                        continue
                    o_cx = (ox0 + ox1) / 2.0
                    o_cy = (oy0 + oy1) / 2.0
                    if (last_non_empty_x1 - 0.8 <= o_cx <= float(sb[0]) + 0.8) and abs(o_cy - s_cy) <= 14.0:
                        has_intervening_sibling = True
                        break

            # Full-size 2D fraction or multi-row header shifted vertically relative to font size
            is_2d_frac_shift = (
                last_non_empty_y0 is not None
                and last_non_empty_size is not None
                and abs(float(sb[1]) - last_non_empty_y0) >= max(3.2, min(s_size, last_non_empty_size) * 0.45)
                and min(s_size, last_non_empty_size) >= max(s_size, last_non_empty_size) * 0.85
            )
            is_sym_delim_split = (
                last_non_empty_is_sym_delim is not None
                and is_sym_delim != last_non_empty_is_sym_delim
            )
            is_mono_code_split = (
                last_non_empty_is_mono_code is not None
                and is_mono_code != last_non_empty_is_mono_code
                and gap_x >= 2.0
            )

            if (is_h_gap or has_vertical_divider or has_intervening_sibling or is_2d_frac_shift or is_sym_delim_split or is_mono_code_split) and curr_group:
                # Trim trailing whitespace spans from curr_group before splitting
                while curr_group and not _raw_span_text(curr_group[-1]).strip():
                    curr_group.pop()
                if curr_group:
                    groups.append(curr_group)
                curr_group = [s]
            else:
                curr_group.append(s)
            last_non_empty_x1 = float(sb[2])
            last_non_empty_y0 = float(sb[1])
            last_non_empty_size = s_size
            last_non_empty_is_sym_delim = is_sym_delim
            last_non_empty_is_mono_code = is_mono_code

        while curr_group and not _raw_span_text(curr_group[-1]).strip():
            curr_group.pop()
        if curr_group:
            groups.append(curr_group)

        if len(groups) <= 1:
            out.append(line)
        else:
            for g in groups:
                non_ws = [sp for sp in g if _raw_span_text(sp).strip()]
                if not non_ws:
                    continue
                gx0 = min(float(sp.get("bbox", (0, 0, 0, 0))[0]) for sp in non_ws)
                gy0 = min(float(sp.get("bbox", (0, 0, 0, 0))[1]) for sp in non_ws)
                gx1 = max(float(sp.get("bbox", (0, 0, 0, 0))[2]) for sp in non_ws)
                gy1 = max(float(sp.get("bbox", (0, 0, 0, 0))[3]) for sp in non_ws)
                sub_line = dict(line)
                sub_line["spans"] = g
                sub_line["bbox"] = (gx0, gy0, gx1, gy1)
                sub_line["_raw_line_idx"] = li_idx
                out.append(sub_line)
    return out



def _partition_lines_into_columns(
    lines: list[dict],
    min_gutter_pt: float = 9.5,
    vertical_dividers: list[tuple[float, float, float]] | None = None,
) -> list[list[dict]]:
    """Partition lines of a raw block into distinct horizontal columns if multi-column table layout is present.

    In technical and tabular PDFs (e.g. symbol tables, key-value indices), PyMuPDF frequently groups multiple
    horizontal columns into a single raw block, causing reading order jumbling and layout collapse.
    Following BabelDOC and PDFMathTranslate, we find unobstructed vertical whitespace gutters between columns
    using tight non-whitespace horizontal bounds.
    """
    if len(lines) <= 1:
        return [lines]

    intervals: list[tuple[float, float]] = []
    line_bounds: list[tuple[dict, tuple[float, float] | None]] = []
    for l in lines:
        tb = _tight_line_x_bounds(l)
        line_bounds.append((l, tb))
        if tb and (tb[1] > tb[0]):
            intervals.append(tb)
    if not intervals:
        return [lines]

    y_min_all = min(float(l.get("bbox", (0, 0, 0, 0))[1]) for l in lines)
    y_max_all = max(float(l.get("bbox", (0, 0, 0, 0))[3]) for l in lines)

    intervals.sort(key=lambda it: it[0])
    merged: list[tuple[float, float]] = [intervals[0]]
    for cur in intervals[1:]:
        prev = merged[-1]
        has_v_div = bool(
            vertical_dividers
            and cur[0] >= prev[1] - 0.5
            and any(
                (prev[1] - 1.2 <= vx <= cur[0] + 1.2)
                and (min(y_max_all, vy1) - max(y_min_all, vy0) >= 6.0)
                for vx, vy0, vy1 in vertical_dividers
            )
        )
        if not has_v_div and cur[0] <= prev[1] + 1.5:
            merged[-1] = (prev[0], max(prev[1], cur[1]))
        else:
            merged.append(cur)

    cut_points: list[float] = []
    for i in range(len(merged) - 1):
        gap = merged[i + 1][0] - merged[i][1]
        has_v_div = bool(
            vertical_dividers
            and any(
                (merged[i][1] - 1.2 <= vx <= merged[i + 1][0] + 1.2)
                and (min(y_max_all, vy1) - max(y_min_all, vy0) >= 6.0)
                for vx, vy0, vy1 in vertical_dividers
            )
        )
        if gap >= min_gutter_pt or has_v_div:
            cut_points.append((merged[i][1] + merged[i + 1][0]) / 2.0)

    if not cut_points:
        return [lines]

    columns: list[list[dict]] = [[] for _ in range(len(cut_points) + 1)]
    for l, tb in line_bounds:
        if tb is None:
            continue
        mid_x = (tb[0] + tb[1]) / 2.0
        col_idx = 0
        for cp in cut_points:
            if mid_x >= cp:
                col_idx += 1
            else:
                break
        columns[col_idx].append(l)

    non_empty = [c for c in columns if c]
    for col in non_empty:
        col.sort(key=lambda l: l.get("bbox", (0.0, 0.0, 0.0, 0.0))[1])
    return non_empty if non_empty else [lines]


def _is_raw_line_math(line: dict, config: ParserConfig = ParserConfig()) -> bool:
    """Check if an individual line within a raw text block is purely mathematical/symbolic."""
    l_spans = line.get("spans", [])
    meaningful = [
        s for s in l_spans
        if (s.get("text") or ("".join(c.get("c", "") for c in s.get("chars", [])) if "chars" in s else "")).strip()
    ]
    if not meaningful:
        return False
    from layoutlingua.processing.text_sanitizer import sanitize_extracted_text

    norm_mgr = _get_normalizer_manager()
    decoded_parts: list[str] = []
    for s in meaningful:
        raw_s = s.get("text") or ("".join(c.get("c", "") for c in s.get("chars", [])) if "chars" in s else "")
        san_s = sanitize_extracted_text(raw_s)
        dec_s = norm_mgr.normalize_text(san_s, font_name=str(s.get("font", ""))).text
        decoded_parts.append(dec_s)

    full_text = "".join(decoded_parts).strip()

    _mono_keys = ("courier", "consolas", "menlo", "monaco", "monospace", "typewriter", "cmtt", "txtt", "dejavusansmono", "liberationsansmono", "firacode", "jetbrainsmono")
    if (
        re.fullmatch(r"[a-z0-9_.*]+(?:\s+[a-z0-9_.*]+)*", full_text)
        and any(
            (int(s.get("flags", 0) or 0) & 8) or any(mk in str(s.get("font", "") or "").lower() for mk in _mono_keys)
            for s in meaningful
        )
        and all(
            (int(s.get("flags", 0) or 0) & 8)
            or any(mk in str(s.get("font", "") or "").lower() for mk in _mono_keys)
            or (int(s.get("flags", 0) or 0) & 2)
            or _raw_span_text(s).strip() in (".", "f", "s", "d", "w")
            for s in meaningful
        )
    ):
        return True
    if re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", full_text):
        return True

    if (
        1 <= len(full_text) <= 4
        and full_text.isalpha()
        and full_text.isascii()
        and all((int(s.get("flags", 0) or 0) & 2) != 0 for s in meaningful)
    ):
        return True

    prose_tokens = _extract_prose_tokens(full_text)
    if prose_tokens:
        return False

    if all(bool(config.formula_font_pattern.search(s.get("font", ""))) for s in meaningful):
        return True

    has_rel = bool(MATH_RELATION_PATTERN.search(full_text))
    words = re.findall(r"\b[^\W\d_]+\b", full_text, re.UNICODE)
    return (
        has_rel
        or len(words) == 0
        or all(
            len(w) <= 2
            or w.lower() in _ISO_MATH_FUNCTIONS
            or bool(MATH_FUNC_PATTERN.fullmatch(w))
            for w in words
        )
    )


def _merge_vertical_hyphenated_fragments(blocks: list[TextBlock]) -> list[TextBlock]:
    """Coalesce vertically stacked hyphenated word fragments (e.g. 'Hexa-' + 'deci-' + 'mal', 'Char-' + 'acter', 'FOR-' + 'MAT')
    into unified multi-line words so narrow table headers translate as complete words rather than broken syllables.
    Safeguards against merging separate table rows of prefixes (e.g. 'milli-', 'micro-', 'nano-', 'pico-', 'femto-', 'atto-', 'zepto-', 'yocto-').
    """
    if len(blocks) <= 1:
        return blocks

    def _has_row_sibling(idx: int, exclude: set[int]) -> bool:
        b = blocks[idx]
        by = (b.bbox[1] + b.bbox[3]) * 0.5
        for k, ob in enumerate(blocks):
            if k == idx or k in exclude:
                continue
            oy = (ob.bbox[1] + ob.bbox[3]) * 0.5
            if abs(oy - by) <= 4.5 and abs(ob.bbox[0] - b.bbox[0]) >= 6.0 and abs(ob.bbox[0] - b.bbox[0]) <= 120.0:
                return True
        return False

    work = list(blocks)
    skip: set[int] = set()
    out: list[TextBlock] = []

    for i in range(len(work)):
        if i in skip:
            continue
        curr = work[i]
        c_txt = curr.text.strip()
        if len(c_txt) >= 3 and c_txt.endswith("-") and c_txt[-2].isalpha():
            chain = [i]
            cur_idx = i
            while True:
                cb = work[cur_idx]
                cb_txt = cb.text.strip()
                if not cb_txt.endswith("-"):
                    break
                c_box = cb.bbox
                c_w = max(1.0, c_box[2] - c_box[0])
                c_fs = max((s.font_size for s in cb.spans), default=8.0)
                is_upper_head = cb_txt[:-1].isupper()
                best_j: int | None = None
                best_dy = 999.0
                for j in range(len(work)):
                    if j in skip or j in chain:
                        continue
                    cand = work[j]
                    k_txt = cand.text.strip()
                    if not k_txt:
                        continue
                    if is_upper_head:
                        if not re.fullmatch(r"[A-Z]{2,}-?", k_txt):
                            continue
                    else:
                        if not re.fullmatch(r"[a-z]+-?", k_txt):
                            continue
                    k_box = cand.bbox
                    k_w = max(1.0, k_box[2] - k_box[0])
                    dy = k_box[1] - c_box[3]
                    if -2.5 <= dy <= max(4.5, c_fs * 0.65):
                        ox = min(c_box[2], k_box[2]) - max(c_box[0], k_box[0])
                        if ox >= min(c_w, k_w) * 0.50 and dy < best_dy:
                            best_dy = dy
                            best_j = j
                if best_j is None:
                    break
                chain.append(best_j)
                cur_idx = best_j
                if len(chain) >= 4:
                    break

            # A genuine hyphenated word wraps onto a final syllable that does NOT end with '-'.
            # Prefix lists (e.g. 'femto-', 'atto-', 'zepto-', 'yocto-') all end with '-' and are never merged.
            last_txt = work[chain[-1]].text.strip()
            if len(chain) >= 2 and not last_txt.endswith("-"):
                min_x0 = min(work[idx_c].bbox[0] for idx_c in chain)
                min_y0 = min(work[idx_c].bbox[1] for idx_c in chain)
                max_x1 = max(work[idx_c].bbox[2] for idx_c in chain)
                max_y1 = max(work[idx_c].bbox[3] for idx_c in chain)
                joined_parts: list[str] = []
                for pos, idx_c in enumerate(chain):
                    part_txt = work[idx_c].text.strip()
                    if pos < len(chain) - 1 and part_txt.endswith("-"):
                        part_txt = part_txt[:-1]
                    joined_parts.append(part_txt)
                    skip.add(idx_c)
                ref_span = work[chain[0]].spans[0]
                coalesced_span = GlyphSpan(
                    span_id=ref_span.span_id,
                    text="".join(joined_parts),
                    bbox=(min_x0, min_y0, max_x1, max_y1),
                    font_name=ref_span.font_name,
                    font_size=ref_span.font_size,
                    color=ref_span.color,
                    flags=ref_span.flags,
                    origin=ref_span.origin,
                    chars=(),
                    is_math_or_symbol=ref_span.is_math_or_symbol,
                )
                curr = TextBlock(
                    block_id=curr.block_id,
                    bbox=(min_x0, min_y0, max_x1, max_y1),
                    spans=[coalesced_span],
                    block_type="text",
                )
        elif (
            curr.block_type == "text"
            and not c_txt.endswith(("-", ".", ":", ";", ",", "!", "?"))
            and (curr.bbox[2] - curr.bbox[0]) <= 65.0
            and (curr.bbox[3] - curr.bbox[1]) <= 18.0
            and 1 <= len(c_txt.split()) <= 3
        ):
            # Merge vertically stacked narrow multi-line table header cells (e.g. 'Góc phần ' + 'tư ')
            c_box = curr.bbox
            c_fs = max((s.font_size for s in curr.spans), default=10.0)
            c_fn = curr.spans[0].font_name if curr.spans else ""
            for j in range(i + 1, len(work)):
                if j in skip:
                    continue
                cand = work[j]
                if cand.block_type != "text":
                    continue
                k_txt = cand.text.strip()
                if not k_txt or len(k_txt.split()) != 1 or not k_txt[0].islower() or k_txt.endswith(("-", ".", ":", ";", ",", "!", "?")):
                    continue
                k_box = cand.bbox
                dy = k_box[1] - c_box[3]
                if -2.0 <= dy <= max(4.0, c_fs * 0.50):
                    if k_box[0] >= c_box[0] - 2.0 and k_box[2] <= c_box[2] + 2.0:
                        k_fn = cand.spans[0].font_name if cand.spans else ""
                        k_fs = max((s.font_size for s in cand.spans), default=10.0)
                        if c_fn == k_fn and abs(c_fs - k_fs) <= 0.4:
                            min_x0 = min(c_box[0], k_box[0])
                            min_y0 = min(c_box[1], k_box[1])
                            max_x1 = max(c_box[2], k_box[2])
                            max_y1 = max(c_box[3], k_box[3])
                            ref_span = curr.spans[0]
                            coalesced_span = GlyphSpan(
                                span_id=ref_span.span_id,
                                text=f"{c_txt} {k_txt}",
                                bbox=(min_x0, min_y0, max_x1, max_y1),
                                font_name=ref_span.font_name,
                                font_size=ref_span.font_size,
                                color=ref_span.color,
                                flags=ref_span.flags,
                                origin=ref_span.origin,
                                chars=(),
                                is_math_or_symbol=False,
                            )
                            curr = TextBlock(
                                block_id=curr.block_id,
                                bbox=(min_x0, min_y0, max_x1, max_y1),
                                spans=[coalesced_span],
                                block_type="text",
                            )
                            skip.add(j)
                            break
        out.append(curr)
    return out


def _merge_horizontal_baseline_fragments(
    blocks: list[TextBlock],
    vertical_dividers: list[tuple[float, float, float]] | None = None,
) -> list[TextBlock]:
    """Coalesces horizontally adjacent text fragments sharing the exact same baseline into single blocks.

    PyMuPDF splits single lines containing math baseline shifts (such as C_n^k) or intraword math splits
    (such as '3cot t' + 'an' or 's' + 'in 2') into disjoint micro-blocks. This module stitches them back
    into unified semantic units before translation, eliminating tiny bounding-box overflows and broken tokens.
    """
    if len(blocks) <= 1:
        return blocks

    merged: list[TextBlock] = []
    skip_indices: set[int] = set()

    for i in range(len(blocks)):
        if i in skip_indices:
            continue
        curr = blocks[i]

        for j in range(i + 1, len(blocks)):
            if j in skip_indices:
                continue
            cand = blocks[j]

            c_box = curr.bbox
            k_box = cand.bbox
            c_h = c_box[3] - c_box[1]
            k_h = k_box[3] - k_box[1]

            # Check for zero-gap intraword split across blocks (e.g. '3cot t' [formula] + 'an' [text] or 's' [formula] + 'in 2' [text])
            gap_x = k_box[0] - c_box[2]
            is_intraword_touch = (
                -0.8 <= gap_x <= 1.2
                and abs(c_box[1] - k_box[1]) <= 1.5
                and abs(c_box[3] - k_box[3]) <= 1.5
                and c_h <= 22.0
                and k_h <= 22.0
                and bool(curr.text)
                and bool(cand.text)
                and not curr.text.endswith((" ", "\t", "\n"))
                and not cand.text.startswith((" ", "\t", "\n"))
                and curr.text[-1].isalpha()
                and cand.text[0].isalpha()
            )

            # Only merge regular text blocks unless it is a touching intraword split
            if not is_intraword_touch and (curr.block_type != "text" or cand.block_type != "text"):
                continue

            # Never re-merge sub-blocks that were explicitly split from the same raw block
            # across horizontal gaps or column gutters
            curr_raw_prefix = "_".join(curr.block_id.split("_")[:3])
            cand_raw_prefix = "_".join(cand.block_id.split("_")[:3])
            if curr_raw_prefix == cand_raw_prefix:
                continue

            # Do not merge a hyphenated prefix with an uppercase neighbor (e.g. 'Hexa-' + 'ASCII')
            c_strip = curr.text.strip()
            k_strip = cand.text.strip()
            if c_strip.endswith("-") and k_strip and k_strip[0].isupper():
                continue

            # Only merge single-line fragments (short height)
            if c_h > 26.0 or k_h > 26.0:
                continue

            # Vertical overlap check (must share baseline, overlap >= 65%)
            overlap_y = min(c_box[3], k_box[3]) - max(c_box[1], k_box[1])
            min_h = min(c_h, k_h)
            if min_h <= 0 or (overlap_y / min_h) < 0.65:
                continue

            # Bottom baseline alignment within 4pt
            if abs(c_box[3] - k_box[3]) > 4.0:
                continue

            # Strict gap: 0 to 6.0pt (or -0.8 to 1.2pt for intraword touch). Gaps > 6.0pt are column gutters, braces, or table cells!
            if (-0.8 if is_intraword_touch else 0.0) <= gap_x <= 6.0:
                if vertical_dividers:
                    crosses_v_div = any(
                        (c_box[2] - 1.2 <= vx <= k_box[0] + 1.2)
                        and (min(max(c_box[3], k_box[3]), vy1) - max(min(c_box[1], k_box[1]), vy0) >= 2.5)
                        for vx, vy0, vy1 in vertical_dividers
                    )
                    if crosses_v_div:
                        continue
                # Ensure no other block (such as a vertical brace or math symbol) sits between curr and cand
                if not is_intraword_touch:
                    has_intervening = any(
                        m_idx not in (i, j)
                        and min(c_box[3], blocks[m_idx].bbox[3]) - max(c_box[1], blocks[m_idx].bbox[1]) > 0.0
                        and blocks[m_idx].bbox[2] > c_box[2] - 1.0
                        and blocks[m_idx].bbox[0] < k_box[0] + 1.0
                        for m_idx in range(len(blocks))
                    )
                    if has_intervening:
                        continue
                # Merge cand into curr
                new_bbox = (
                    min(c_box[0], k_box[0]),
                    min(c_box[1], k_box[1]),
                    max(c_box[2], k_box[2]),
                    max(c_box[3], k_box[3]),
                )
                curr_spans = list(curr.spans)
                cand_spans = list(cand.spans)
                if curr_spans and cand_spans and gap_x >= 2.0:
                    last_text = curr_spans[-1].text or ""
                    first_text = cand_spans[0].text or ""
                    if not last_text.endswith((" ", "\t", "\n", "\xa0", "-", "\u2010", "\u2011", "\u00ad")) and not first_text.startswith((" ", "\t", "\n", "\xa0")):
                        curr_spans[-1] = GlyphSpan(
                            span_id=curr_spans[-1].span_id,
                            text=curr_spans[-1].text + " ",
                            bbox=curr_spans[-1].bbox,
                            font_name=curr_spans[-1].font_name,
                            font_size=curr_spans[-1].font_size,
                            color=curr_spans[-1].color,
                            flags=curr_spans[-1].flags,
                            origin=curr_spans[-1].origin,
                            chars=curr_spans[-1].chars,
                            is_math_or_symbol=curr_spans[-1].is_math_or_symbol,
                        )

                combined_spans = curr_spans + cand_spans
                new_block_type = (
                    "formula"
                    if (is_intraword_touch and _is_pure_formula_block(combined_spans))
                    else "text"
                )
                curr = TextBlock(
                    block_id=curr.block_id,
                    bbox=new_bbox,
                    spans=combined_spans,
                    block_type=new_block_type,
                )
                skip_indices.add(j)

        merged.append(curr)

    # Second pass: coalesce a narrow single-line text label (e.g. 'cơ số ') with its
    # contiguous 1D inline equation tail (e.g. 'b', '=', '10', ')') from the same raw block
    # when no 2D sub/superscripts overlap and the tail completes the parenthetical clause.
    final_blocks: list[TextBlock] = []
    consumed_ids: set[str] = set()
    for b in merged:
        if b.block_id in consumed_ids:
            continue
        bw = b.bbox[2] - b.bbox[0]
        bh = b.bbox[3] - b.bbox[1]
        if b.block_type == "text" and bw <= 60.0 and bh <= 22.0:
            prefix = "_".join(b.block_id.split("_")[:3])
            b_cy = (b.bbox[1] + b.bbox[3]) * 0.5
            right_siblings = sorted(
                [
                    ob for ob in merged
                    if ob.block_id != b.block_id
                    and ob.block_id not in consumed_ids
                    and "_".join(ob.block_id.split("_")[:3]) == prefix
                    and ob.bbox[0] >= b.bbox[2] - 2.0
                    and abs(((ob.bbox[1] + ob.bbox[3]) * 0.5) - b_cy) <= 4.0
                ],
                key=lambda x: x.bbox[0],
            )
            if (
                right_siblings
                and all(
                    10.0 <= (rc.bbox[3] - rc.bbox[1]) <= 24.0
                    and bool(re.fullmatch(r"[A-Za-z0-9=+\-(),.;:\s]+", rc.text))
                    for rc in right_siblings
                )
            ):
                chain: list[TextBlock] = []
                cur_x1 = b.bbox[2]
                for rc in right_siblings:
                    if -2.0 <= (rc.bbox[0] - cur_x1) <= 4.0:
                        has_2d_stack = any(
                            other.block_id not in (b.block_id, rc.block_id)
                            and min(rc.bbox[2], other.bbox[2]) - max(rc.bbox[0], other.bbox[0]) > 0.5
                            and (rc.bbox[1] - 10.0 <= other.bbox[3] and other.bbox[1] <= rc.bbox[3] + 10.0)
                            for other in merged
                        )
                        if has_2d_stack:
                            break
                        chain.append(rc)
                        cur_x1 = max(cur_x1, rc.bbox[2])
                    else:
                        break
                if len(chain) == len(right_siblings) and chain[-1].text.strip().endswith(")"):
                    ref_fs = max((s.font_size for s in b.spans), default=12.0)
                    ref_fn = b.spans[0].font_name if b.spans else "Times New Roman"
                    new_spans = list(b.spans)
                    min_x0, min_y0, max_x1, max_y1 = b.bbox
                    left_paren = next(
                        (
                            fb for fb in final_blocks
                            if "_".join(fb.block_id.split("_")[:3]) == prefix
                            and fb.text.strip() == "("
                            and -1.5 <= (b.bbox[0] - fb.bbox[2]) <= 3.0
                            and abs(((fb.bbox[1] + fb.bbox[3]) * 0.5) - b_cy) <= 4.0
                        ),
                        None,
                    )
                    if left_paren is not None:
                        final_blocks.remove(left_paren)
                        consumed_ids.add(left_paren.block_id)
                        lp_spans = [
                            GlyphSpan(
                                span_id=s.span_id,
                                text=s.text,
                                bbox=(s.bbox[0], min_y0, s.bbox[2], max_y1),
                                font_name=ref_fn,
                                font_size=ref_fs,
                                color=s.color,
                                flags=0,
                                origin=s.origin,
                                chars=s.chars,
                                is_math_or_symbol=False,
                            )
                            for s in left_paren.spans
                        ]
                        new_spans = lp_spans + new_spans
                        min_x0 = min(min_x0, left_paren.bbox[0])
                    for rc in chain:
                        if rc in final_blocks:
                            final_blocks.remove(rc)
                        consumed_ids.add(rc.block_id)
                        max_x1 = max(max_x1, rc.bbox[2])
                        is_close_paren = rc.text.strip() == ")"
                        for s in rc.spans:
                            new_spans.append(
                                GlyphSpan(
                                    span_id=s.span_id,
                                    text=s.text,
                                    bbox=(s.bbox[0], min_y0, s.bbox[2], max_y1),
                                    font_name=ref_fn if is_close_paren else s.font_name,
                                    font_size=ref_fs if is_close_paren else s.font_size,
                                    color=s.color,
                                    flags=0 if is_close_paren else s.flags,
                                    origin=s.origin,
                                    chars=s.chars,
                                    is_math_or_symbol=False if is_close_paren else s.is_math_or_symbol,
                                )
                            )
                    b = TextBlock(
                        block_id=b.block_id,
                        bbox=(min_x0, min_y0, max_x1, max_y1),
                        spans=new_spans,
                        block_type="text",
                    )
        final_blocks.append(b)

    return final_blocks


class PDFParseError(Exception):
    """Raised when a PDF cannot be opened, decrypted, or parsed."""


import logging

logger = logging.getLogger(__name__)


def parse_pdf(
    file_path: str | Path,
    password: str | None = None,
    include_chars: bool = True,
    layout_detector: Any | None = None,
    config: ParserConfig = ParserConfig(),
) -> DocumentIR:
    """Parse a PDF document into a decoupled DocumentIR representation.

    Args:
        file_path: Absolute or relative path to the PDF file.
        password: Password for encrypted PDFs (optional).
        include_chars: Whether to extract character-level bounding boxes and origins.

    Returns:
        DocumentIR representing the document hierarchy and geometry.

    Raises:
        PDFParseError: If the file does not exist, is invalid, encrypted without password,
                       or corrupted.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise PDFParseError(f"PDF file does not exist: {path}")

    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise PDFParseError(f"Failed to open PDF file '{path}': {exc}") from exc

    try:
        if doc.is_encrypted:
            if not password or not doc.authenticate(password):
                raise PDFParseError(f"PDF is encrypted and password was invalid or not provided: {path}")

        filename = path.name
        doc_id = f"doc_{path.stem}_{os.path.getsize(path)}"
        page_count = len(doc)
        doc_metadata: dict[str, Any] = dict(doc.metadata or {})

        pages: list[PageIR] = []

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc[page_idx]

            # Coordinate convention: top-left (0, 0), points
            rect = page.rect
            geometry = PageGeometry(
                width=float(rect.width),
                height=float(rect.height),
                rotation=int(page.rotation),
                unit="pt",
                coordinate_origin="top-left",
            )

            blocks: list[TextBlock] = []
            regions: list[LayoutRegion] = []

            # Extract low-level text representation
            try:
                raw_dict = page.get_text("rawdict")
            except Exception as exc:
                raise PDFParseError(f"Failed to extract text streams from page {page_num}: {exc}") from exc

            raw_blocks = raw_dict.get("blocks", [])
            page_v_dividers = _extract_page_vertical_dividers(page)

            # Collect page-wide non-empty line bboxes so multi-column symbol/formula tables
            # (where rows have sibling entries on the same horizontal band) can be recognized
            page_line_bboxes: list[tuple[float, float, float, float]] = []
            for rb in raw_blocks:
                if rb.get("type", 0) != 0:
                    continue
                for rl in _split_lines_across_horizontal_gaps(rb.get("lines", []), vertical_dividers=page_v_dividers):
                    tb = _tight_line_x_bounds(rl)
                    if tb is not None:
                        lb = rl.get("bbox", (0.0, 0.0, 0.0, 0.0))
                        page_line_bboxes.append((tb[0], float(lb[1]), tb[1], float(lb[3])))

            for block_idx, b in enumerate(raw_blocks):
                block_type = b.get("type", 0)
                raw_bbox = b.get("bbox", (0.0, 0.0, 0.0, 0.0))
                b_bbox = _sanitize_bbox(raw_bbox)

                # Type 0: Text Block
                if block_type == 0:
                    raw_lines = b.get("lines", [])

                    # Sort spans in each line left-to-right (x0) to restore reading order
                    for line in raw_lines:
                        l_spans = line.get("spans", [])
                        l_spans.sort(key=lambda s: s.get("bbox", (0.0, 0.0, 0.0, 0.0))[0])

                    # Normalize non-stacked 1D sub/superscripts into their parent prose line
                    raw_lines = _normalize_raw_block_1d_scripts(raw_lines, config=config)

                    # Split lines that bridge across wide internal horizontal gaps, vertical dividers, or braces
                    lines = _split_lines_across_horizontal_gaps(raw_lines, vertical_dividers=page_v_dividers)

                    # Fold a single-word lowercase sentence-ending orphan syllable on line[1] (e.g. 'định.')
                    # into a wide offset prose line[0] (whose left prefix sits in an adjacent raw block)
                    # while keeping line[1]'s span/chars for tight clearance redaction.
                    if len(lines) == 2:
                        tb0 = _tight_line_x_bounds(lines[0])
                        tb1 = _tight_line_x_bounds(lines[1])
                        l0_b = lines[0].get("bbox", (0.0, 0.0, 0.0, 0.0))
                        l1_b = lines[1].get("bbox", (0.0, 0.0, 0.0, 0.0))
                        if (
                            tb0 is not None
                            and tb1 is not None
                            and tb0[0] >= 80.0
                            and (tb0[1] - tb0[0]) >= 140.0
                            and (tb1[1] - tb1[0]) <= 40.0
                            and tb1[1] <= tb0[0] + 5.0
                            and 0.0 <= (float(l1_b[1]) - float(l0_b[3])) <= 6.0
                        ):
                            t0_str = "".join(_raw_span_text(s) for s in lines[0].get("spans", [])).strip()
                            t1_str = "".join(_raw_span_text(s) for s in lines[1].get("spans", [])).strip()
                            if (
                                t0_str
                                and not t0_str.endswith((".", ":", ";", "!", "?"))
                                and len(t1_str.split()) == 1
                                and t1_str[0].islower()
                                and t1_str.endswith(".")
                            ):
                                l0_spans = list(lines[0].get("spans", []))
                                l1_spans = list(lines[1].get("spans", []))
                                if l0_spans and l1_spans:
                                    last_s0 = dict(l0_spans[-1])
                                    last_t0 = _raw_span_text(last_s0)
                                    first_t1 = _raw_span_text(l1_spans[0])
                                    if not last_t0.endswith((" ", "\t", "\n")) and not first_t1.startswith((" ", "\t", "\n")):
                                        last_s0["text"] = last_t0 + " "
                                        l0_spans[-1] = last_s0
                                    folded_line = dict(lines[0])
                                    folded_line["spans"] = l0_spans + l1_spans
                                    lines = [folded_line]

                    # Partition lines into distinct vertical column lanes (BabelDOC / pdf2zh architecture)
                    column_lanes = _partition_lines_into_columns(lines, vertical_dividers=page_v_dividers)

                    # Group lines with matching predominant colors and matching math/prose modality
                    line_color_groups: list[tuple[int, list[dict]]] = []
                    split_by_math = True

                    for col_idx, col_lines in enumerate(column_lanes):
                        curr_state = None
                        curr_lines: list[dict] = []
                        col_xs0 = [
                            tb[0] for l in col_lines for tb in (_tight_line_x_bounds(l),) if tb is not None
                        ]
                        col_xs1 = [
                            tb[1] for l in col_lines for tb in (_tight_line_x_bounds(l),) if tb is not None
                        ]
                        col_min_x0 = min(col_xs0) if col_xs0 else b_bbox[0]
                        col_max_x1 = max(col_xs1) if col_xs1 else b_bbox[2]

                        for line in col_lines:
                            l_spans = line.get("spans", [])
                            predom_c = None
                            l_size = config.default_fallback_font_size
                            non_empty_sizes: list[float] = []
                            bold_chars = 0
                            total_chars = 0
                            for s in l_spans:
                                txt = _raw_span_text(s)
                                s_strip = txt.strip()
                                if s_strip:
                                    if predom_c is None:
                                        predom_c = s.get("color", 0)
                                    non_empty_sizes.append(float(s.get("size", l_size) or l_size))
                                    c_len = len(s_strip)
                                    total_chars += c_len
                                    s_fn = str(s.get("font", "") or "").lower()
                                    if (int(s.get("flags", 0)) & 16) or any(k in s_fn for k in ("bold", "black", "tibo", "hebo")):
                                        bold_chars += c_len
                            if non_empty_sizes:
                                l_size = max(non_empty_sizes)
                            if predom_c is None and l_spans:
                                predom_c = l_spans[0].get("color", 0)

                            line_math = _is_raw_line_math(line, config=config) if split_by_math else False
                            line_bold = (bold_chars / total_chars) >= 0.75 if (total_chars > 0 and not line_math) else False
                            state = (predom_c, line_math, line_bold)

                            # Horizontal continuity check: do not split lines sharing the same physical row
                            # ONLY when they are horizontally adjacent fragments of the same column/expression
                            same_row = False
                            col_break = False
                            if curr_lines:
                                last_l = curr_lines[-1]
                                l_b = line.get("bbox", (0.0, 0.0, 0.0, 0.0))
                                last_b = last_l.get("bbox", (0.0, 0.0, 0.0, 0.0))
                                y_overlap = min(l_b[3], last_b[3]) - max(l_b[1], last_b[1])
                                l_mid_y = (l_b[1] + l_b[3]) / 2.0
                                last_mid_y = (last_b[1] + last_b[3]) / 2.0
                                was_split_from_same_raw = (
                                    line.get("_raw_line_idx") is not None
                                    and line.get("_raw_line_idx") == last_l.get("_raw_line_idx")
                                )
                                if y_overlap > 1.0 or abs(l_mid_y - last_mid_y) <= 4.0:
                                    h_gap = max(l_b[0] - last_b[2], last_b[0] - l_b[2])
                                    if not was_split_from_same_raw and h_gap <= 8.0 and line_math == curr_state[1]:
                                        same_row = True
                                    else:
                                        col_break = True

                            # Disjoint column & table-row check (inheriting ts-engine proseGroups rules)
                            if curr_lines and not same_row and not col_break:
                                last_l = curr_lines[-1]
                                l_b = line.get("bbox", (0.0, 0.0, 0.0, 0.0))
                                last_b = last_l.get("bbox", (0.0, 0.0, 0.0, 0.0))
                                g_x0 = min(l.get("bbox", (0.0, 0.0, 0.0, 0.0))[0] for l in curr_lines)
                                g_y0 = min(l.get("bbox", (0.0, 0.0, 0.0, 0.0))[1] for l in curr_lines)
                                g_x1 = max(l.get("bbox", (0.0, 0.0, 0.0, 0.0))[2] for l in curr_lines)
                                g_y1 = max(l.get("bbox", (0.0, 0.0, 0.0, 0.0))[3] for l in curr_lines)
                                l_x0, l_x1 = l_b[0], l_b[2]
                                if (l_x1 < g_x0 - 45.0) or (l_x0 > g_x1 + 45.0):
                                    col_break = True

                                # Check font size jump (> 1.5pt) or large vertical gap
                                last_sizes = [
                                    float(sp.get("size", l_size) or l_size)
                                    for sp in last_l.get("spans", [])
                                    if _raw_span_text(sp).strip()
                                ]
                                last_size = max(last_sizes) if last_sizes else l_size
                                if abs(l_size - last_size) > 1.5 or (l_b[1] - last_b[3]) > max(9.5, last_size * 0.90):
                                    col_break = True

                                # L-shaped / non-rectangular paragraph guard (BabelDOC #630):
                                # If combining `curr_lines` and `line` expands the rectangular bbox across
                                # another block on the page (e.g. an inline formula or prefix block on one of the lines),
                                # split into separate rectangular blocks so neither block engulfs its neighbor.
                                if not col_break and not line_math and (abs(l_x0 - g_x0) > 15.0 or abs(l_x1 - g_x1) > 15.0):
                                    u_x0 = min(g_x0, l_x0)
                                    u_y0 = min(g_y0, float(l_b[1]))
                                    u_x1 = max(g_x1, l_x1)
                                    u_y1 = max(g_y1, float(l_b[3]))
                                    member_boxes = [
                                        (tb[0], float(ml.get("bbox", (0, 0, 0, 0))[1]), tb[1], float(ml.get("bbox", (0, 0, 0, 0))[3]))
                                        for ml in (curr_lines + [line])
                                        for tb in (_tight_line_x_bounds(ml),)
                                        if tb is not None
                                    ]
                                    for ox0, oy0, ox1, oy1 in page_line_bboxes:
                                        if any(
                                            abs(ox0 - mx0) <= 1.5 and abs(oy0 - my0) <= 1.5 and abs(ox1 - mx1) <= 1.5 and abs(oy1 - my1) <= 1.5
                                            for (mx0, my0, mx1, my1) in member_boxes
                                        ):
                                            continue
                                        if (min(u_x1, ox1) - max(u_x0, ox0) > 4.0) and (min(u_y1, oy1) - max(u_y0, oy0) > 4.0):
                                            col_break = True
                                            break

                                # Table-row separation (ts-engine hasNewLeftSymbolRow / hasDistinctRightFormulaRows):
                                # If another column on the page has a row-aligned entry at `line`'s vertical band
                                # AND another entry at `last_l`'s vertical band, `line` is a distinct table row!
                                if not col_break and not line_math:
                                    l_mid_y = (l_b[1] + l_b[3]) / 2.0
                                    last_mid_y = (last_b[1] + last_b[3]) / 2.0
                                    last_w = last_b[2] - last_b[0]
                                    line_has_outside_sibling = any(
                                        (ox1 <= col_min_x0 - 5.0 or ox0 >= col_max_x1 + 5.0)
                                        and abs(((oy0 + oy1) / 2.0) - l_mid_y) <= 6.5
                                        for (ox0, oy0, ox1, oy1) in page_line_bboxes
                                    )
                                    last_has_outside_sibling = any(
                                        (ox1 <= col_min_x0 - 5.0 or ox0 >= col_max_x1 + 5.0)
                                        and abs(((oy0 + oy1) / 2.0) - last_mid_y) <= 6.5
                                        for (ox0, oy0, ox1, oy1) in page_line_bboxes
                                    )
                                    if line_has_outside_sibling and (last_has_outside_sibling or len(column_lanes) > 1):
                                        col_break = True

                            if (curr_state is None or state == curr_state or same_row) and not col_break:
                                curr_state = state if not same_row else curr_state
                                curr_lines.append(line)
                            else:
                                line_color_groups.append((col_idx, curr_lines))
                                curr_lines = [line]
                                curr_state = state

                        if curr_lines:
                            line_color_groups.append((col_idx, curr_lines))

                    for sub_idx, (col_idx, sub_lines) in enumerate(line_color_groups):
                        spans: list[GlyphSpan] = []
                        sub_min_x0 = b_bbox[0]
                        sub_min_y0 = b_bbox[1]
                        sub_max_x1 = b_bbox[2]
                        sub_max_y1 = b_bbox[3]

                        non_empty_lines = [
                            l for l in sub_lines
                            if any(
                                (s.get("text") or ("".join(c.get("c", "") for c in s.get("chars", [])) if "chars" in s else "")).strip()
                                for s in l.get("spans", [])
                            )
                        ]
                        target_lines = non_empty_lines if non_empty_lines else sub_lines
                        if target_lines:
                            sub_min_x0 = min(l.get("bbox", b_bbox)[0] for l in target_lines)
                            sub_min_y0 = min(l.get("bbox", b_bbox)[1] for l in target_lines)
                            sub_max_x1 = max(l.get("bbox", b_bbox)[2] for l in target_lines)
                            sub_max_y1 = max(l.get("bbox", b_bbox)[3] for l in target_lines)

                        sub_bbox = (float(sub_min_x0), float(sub_min_y0), float(sub_max_x1), float(sub_max_y1))

                        for line_idx, line in enumerate(sub_lines):
                            line_spans = line.get("spans", [])
                            for span_idx, s in enumerate(line_spans):
                                s_text = s.get("text")
                                if s_text is None and "chars" in s:
                                    s_text = "".join(c.get("c", "") for c in s["chars"])
                                if s_text is None:
                                    s_text = ""
                                else:
                                    from layoutlingua.processing.text_sanitizer import sanitize_extracted_text

                                    s_text = sanitize_extracted_text(s_text)
                                    # Decode legacy Vietnamese font encodings (VNI-Times /
                                    # TCVN3) into Unicode NFC — the same decode the TS
                                    # engine applies; without it VNI sections extract as
                                    # 'cô soá' / 'ñ' and never match prose classification.
                                    s_text = _get_normalizer_manager().normalize_text(
                                        s_text, font_name=str(s.get("font", ""))
                                    ).text

                                # Preserve word separation across line breaks within a block
                                is_last_span_in_line = (span_idx == len(line_spans) - 1)
                                is_last_line_in_block = (line_idx == len(sub_lines) - 1)
                                if is_last_span_in_line and not is_last_line_in_block:
                                    next_starts_with_space = False
                                    for ns in sub_lines[line_idx + 1].get("spans", []):
                                        nst = ns.get("text")
                                        if nst is None and "chars" in ns:
                                            nst = "".join(c.get("c", "") for c in ns["chars"])
                                        if nst:
                                            if nst.startswith((" ", "\t", "\n", "\xa0")):
                                                next_starts_with_space = True
                                            break
                                    if not next_starts_with_space and not s_text.endswith(
                                        (" ", "\t", "\n", "\xa0", "-", "\u2010", "\u2011", "\u00ad")
                                    ):
                                        s_text += " "

                                s_bbox = _sanitize_bbox(s.get("bbox", sub_bbox))
                                s_origin = (float(s.get("origin", (0.0, 0.0))[0]), float(s.get("origin", (0.0, 0.0))[1]))

                                # Extract char info if available and requested
                                chars: list[CharInfo] = []
                                if include_chars:
                                    for c in s.get("chars", []):
                                        c_bbox = _sanitize_bbox(c.get("bbox", s_bbox))
                                        c_origin = (
                                            float(c.get("origin", (0.0, 0.0))[0]),
                                            float(c.get("origin", (0.0, 0.0))[1]),
                                        )
                                        chars.append(
                                            CharInfo(
                                                char=str(c.get("c", "")),
                                                bbox=c_bbox,
                                                origin=c_origin,
                                            )
                                        )
                                    if len(chars) < len(s_text):
                                        chars.append(
                                            CharInfo(
                                                char=" ",
                                                bbox=(s_bbox[2], s_bbox[1], s_bbox[2], s_bbox[3]),
                                                origin=s_origin,
                                            )
                                        )

                                # Format color: sRGB int to standard hex string "#RRGGBB"
                                raw_color = s.get("color", 0)
                                color_val: str
                                if isinstance(raw_color, int):
                                    color_val = f"#{raw_color:06x}"
                                else:
                                    color_val = str(raw_color)

                                span_id = f"p{page_num}_b{block_idx}_{sub_idx}_l{line_idx}_s{span_idx}"
                                font_size = float(s.get("size", config.default_fallback_font_size))
                                if font_size <= 0:
                                    font_size = config.default_fallback_font_size

                                spans.append(
                                    GlyphSpan(
                                        span_id=span_id,
                                        text=s_text,
                                        bbox=s_bbox,
                                        font_name=str(s.get("font", "Unknown")),
                                        font_size=font_size,
                                        color=color_val,
                                        flags=int(s.get("flags", 0)),
                                        origin=s_origin,
                                        chars=chars,
                                        is_math_or_symbol=bool(s.get("flags", 0) & 1),
                                    )
                                )

                        if not any(s.text.strip() for s in spans):
                            continue

                        suffix = f"_{col_idx}_{sub_idx}" if len(column_lanes) > 1 else (f"_{sub_idx}" if len(line_color_groups) > 1 else "")
                        block_id = f"p{page_num}_block_{block_idx}{suffix}"
                        is_formula = _is_pure_formula_block(spans, config=config)
                        text_block = TextBlock(
                            block_id=block_id,
                            bbox=sub_bbox,
                            spans=spans,
                            block_type="formula" if is_formula else "text",
                        )
                        blocks.append(text_block)

                # Type 1: Image / Figure Block
                elif block_type == 1:
                    regions.append(
                        LayoutRegion(
                            region_id=f"p{page_num}_img_region_{block_idx}",
                            bbox=b_bbox,
                            category="figure",
                            confidence=1.0,
                            source="pymupdf",
                            metadata={"image_format": b.get("ext", "unknown")},
                        )
                    )

            # Vertical Hyphenated Word Coalescing & Horizontal Baseline Fragment Merging
            blocks = _merge_vertical_hyphenated_fragments(blocks)
            merged_blocks = _merge_horizontal_baseline_fragments(blocks, vertical_dividers=page_v_dividers)

            for mb in merged_blocks:
                regions.append(
                    LayoutRegion(
                        region_id=mb.block_id.replace("_block_", "_region_"),
                        bbox=mb.bbox,
                        category="formula" if mb.block_type == "formula" else "text",
                        confidence=1.0,
                        source="pymupdf",
                        metadata={"span_count": len(mb.spans)},
                    )
                )

            if layout_detector is not None and getattr(layout_detector, "is_available", lambda: False)():
                try:
                    dpi = 150
                    pix = page.get_pixmap(dpi=dpi)
                    vision_regions = layout_detector.detect(pix.tobytes())
                    if vision_regions:
                        scale_factor = 72.0 / float(dpi)
                        from layoutlingua.processing.vision.onnx_detector import LayoutRegion as VisionRegion

                        scaled_regions = [
                            VisionRegion(
                                bbox=(
                                    vr.x0 * scale_factor,
                                    vr.y0 * scale_factor,
                                    vr.x1 * scale_factor,
                                    vr.y1 * scale_factor,
                                ),
                                category=vr.category,
                                score=vr.score,
                            )
                            for vr in vision_regions
                        ]
                        ir_regions = layout_detector.to_ir_regions(scaled_regions, page_num)
                        regions.extend(ir_regions)
                except Exception as exc:
                    logger.warning("Vision layout detection failed on page %d: %s", page_num, exc)

            page_metadata: dict[str, Any] = {}
            if config.preserve_foreign_blocks:
                from layoutlingua.processing.text_sanitizer import detect_language_from_text

                vn_diacritics = set("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
                page_has_vn = any(
                    any(ch.lower() in vn_diacritics for ch in b.text)
                    for b in merged_blocks
                    if b.block_type == "text"
                )
                if page_has_vn:
                    preserved_ids: set[str] = set()
                    for b in merged_blocks:
                        if b.block_type != "text":
                            continue
                        b_txt = b.text.strip()
                        alpha_words = [w for w in re.findall(r"[a-zA-ZÀ-ỹ]+", b_txt) if len(w) >= 2]
                        if (
                            len(alpha_words) >= 5
                            and not any(ch.lower() in vn_diacritics for ch in b_txt)
                            and detect_language_from_text(b_txt) == "en"
                        ):
                            preserved_ids.add(b.block_id)
                    if preserved_ids:
                        page_metadata["preserved_block_ids"] = sorted(preserved_ids)

            pages.append(
                PageIR(
                    page_number=page_num,
                    geometry=geometry,
                    blocks=merged_blocks,
                    regions=regions,
                    metadata=page_metadata,
                )
            )

        return DocumentIR(
            doc_id=doc_id,
            filename=filename,
            page_count=page_count,
            pages=pages,
            metadata=doc_metadata,
        )

    finally:
        doc.close()


def _sanitize_bbox(raw: Any) -> tuple[float, float, float, float]:
    """Ensure bounding box coordinates are well-formed (x0 <= x1, y0 <= y1)."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return (0.0, 0.0, 0.0, 0.0)
    x0, y0, x1, y1 = (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
    # Normalize if coordinates are inverted
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)
