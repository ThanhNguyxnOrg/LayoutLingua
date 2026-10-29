"""Word-level math tokenization ported from the TS engine's Sub-Line Formula Pinning (`pdfTranslator.ts`).

Splits GlyphSpans into word tokens using char-level geometry, classifies each word
with the TS `isMathWordToken` rules (vflag fonts, explicit operators, ISO function
names, consonant clusters, italic style-switch, 2D sub/superscript adjacency,
prime derivatives, function calls, geometric dot products, factorials, vertex clusters),
runs the 5-rule contextual prose recovery pass, and provides inline math shielding (`⟦M0⟧`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from layoutlingua.core.ir import TextBlock
from layoutlingua.processing.normalizers.legacy_vietnamese import has_vni_encoding
from layoutlingua.processing.text_sanitizer import SYMBOL_PUA_TO_UNICODE

_MATH_FONTS = (
    "math", "symbol", "cmmi", "cmsy", "cmex", "msam", "msbm", "mt2", "mt ",
    "mathtype", "eufm", "euex", "wasy", "rsfs", "txsy", "stmary", "mt extra",
    "wingding", "courier", "consolas", "menlo", "monaco", "monospace",
)

_EXPLICIT_MATH_OPS = re.compile(
    r"[=<>≤≥≠≈≡±∓×÷⋅∗∘∙√∛∜∑∏∫∬∭∮∞∂∇∆∈∉⊂⊃⊆⊇∪∩∅∀∃⇒⇔↔→←↑↓⊥∥∠°′″‴∝∴∵∶∷∼≃≅≜≝⊕⊗⊙⊥⊢⊨⊤⊥ℕℤℚℝℂ^\u00b2\u00b3\u00b9\u2070-\u209f]"
)

_ISO_MATH_FUNCTIONS = {
    "sin", "cos", "tan", "cot", "tg", "cotg", "cottan", "cotan", "cosec", "cossec", "sec", "csc",
    "arcsin", "arccos", "arctan", "arccot", "arctg", "arccotg", "arccottan", "arccotan",
    "sinh", "cosh", "tanh", "coth",
    "log", "ln", "lg", "exp", "lim", "sup", "inf", "max", "min",
    "det", "dim", "ker", "im", "rank", "tr", "grad", "div", "rot", "curl",
    "mod", "gcd", "lcm", "ucn", "bcnn", "const", "dx", "dy", "dz", "dt", "du", "dv",
}

_ISO_FUNC_REGEX = re.compile(
    r"^(?:sin|cos|tan|cot|tg|cotg|cottan|cotan|cosec|cossec|arcsin|arccos|arctan|arccot|arctg|arccotg|arccottan|arccotan|"
    r"sinh|cosh|tanh|coth|log|ln|lg)(?:[0-9]{1,2}[a-zA-Zα-ωΑ-Ω]?|[a-zA-Zα-ωΑ-Ω][0-9]?|d[a-zA-Z]|[0-9]{1,3}°)$",
    re.IGNORECASE,
)

_CONSONANT_CLUSTER = re.compile(r"^[bcdfghjklmnpqrstvwxz]{2,4}$", re.IGNORECASE)
_ROMAN_NUMERAL_RE = re.compile(r"^[IVXLCDM]+$", re.IGNORECASE)
_NUMERIC_BRIDGE = re.compile(r"^[\d.,:;+=\-*/_~^…≤≥()\[\]{}°′″% ]+$")

_VOWELS = set("aeiouyàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựýỳỷỹỵ")

# Shield 1D inline math expressions inside prose groups before sending to NMT/LLM
INLINE_MATH_SHIELD_REGEX = re.compile(
    r"\[[^\[\]\n]*[;≤≥≠≈±×÷∈∉⊂⊃∪∩∞√∑∏∫α-ωΑ-Ω][^\[\]\n]*\]|"
    r"\([^\(\)\n]*[=<>≤≥≠≈±×÷∈∉⊂⊃∪∩∞√∑∏∫α-ωΑ-Ω\u00b2\u00b3\u00b9\u2070-\u209f+\-*/^][^\(\)\n]*\)[\u00b2\u00b3\u00b9\u2070-\u209f]*|"
    r"\b(?:[a-zA-Zα-ωΑ-Ω0-9°′″_\u00b2\u00b3\u00b9\u2070-\u209f]+\s*(?:[=<>≤≥≠≈≡±∓×÷∈∉⊂⊃⊆⊇∪∩⇒⇔→↔]\s*[a-zA-Zα-ωΑ-Ω0-9°′″_\u00b2\u00b3\u00b9\u2070-\u209f+\-*/^(),.;\s]+)+)|"
    r"\b(?:sin|cos|tan|cot|tg|cotg|log|ln|lim)\s*(?:\([^)]+\)|[a-zA-Zα-ωΑ-Ω0-9°′″]+)|"
    r"\b[a-zA-Z]\([a-zA-Z0-9,\s….\u00b2\u00b3\u00b9\u2070-\u209f=]+\)|"
    r"\b\d+\s*°(?:\s*\d+\s*[′'])?"
)


def decode_symbol_pua(text: str) -> str:
    """Decode Adobe Symbol PUA codepoints (0xF000 - 0xF0FF) into standard Unicode."""
    if not text:
        return text
    return "".join(
        SYMBOL_PUA_TO_UNICODE.get(ord(ch), ch) if 0xF000 <= ord(ch) <= 0xF0FF else ch
        for ch in text
    )


def shield_inline_math_in_prose(text: str) -> tuple[str, list[str]]:
    """Replace 1D inline math expressions inside prose with ⟦M0⟧, ⟦M1⟧ placeholders."""
    tokens: list[str] = []

    def _repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        trailing = ""
        m_trail = re.search(r"([.,:;!?)\]]+\s*)$", raw)
        core = raw
        if m_trail and not raw.startswith("[") and not raw.startswith("("):
            trailing = m_trail.group(1)
            core = raw[: len(raw) - len(trailing)]
        idx = len(tokens)
        tokens.append(core)
        return f"⟦M{idx}⟧{trailing}"

    shielded = INLINE_MATH_SHIELD_REGEX.sub(_repl, text)
    return shielded, tokens


def restore_inline_math_in_prose(translated: str, tokens: list[str]) -> str:
    """Restore ⟦M0⟧ placeholders (and NMT-mutated variants like [M0] / M0) back to inline math."""
    if not tokens:
        return translated
    res = translated
    for idx, tok in enumerate(tokens):
        exact = f"⟦M{idx}⟧"
        if exact in res:
            res = res.replace(exact, tok)
            continue
        pat = re.compile(rf"(?:⟦\s*M\s*{idx}\s*⟧|\[\s*M\s*{idx}\s*\]|\bM{idx}\b)", re.IGNORECASE)
        if pat.search(res):
            res = pat.sub(lambda _m, t=tok: t, res)
    return res


@dataclass
class WordToken:
    """A single word-level token extracted from a GlyphSpan using char boxes."""

    text: str
    bbox: tuple[float, float, float, float]
    font_name: str
    font_size: float
    flags: int
    italic: bool
    bold: bool
    span_id: str
    has_symbol_font: bool = False
    has_vni_font: bool = False
    has_adjacent_sub_sup: bool = False
    line_index: int = 0
    is_math: bool = False


def vflag_pdf2zh(
    font_name: str,
    char_text: str,
    vfont_pattern: str | None = None,
    vchar_pattern: str | None = None,
) -> bool:
    """Open-source PDFMathTranslate (`pdf2zh/converter.py` `vflag`) character/font formula classifier.

    Evaluates:
    1. Unmapped CID glyph names `(cid:...`
    2. Configurable formula font pattern (`vfont_pattern` / `--formular-font-pattern`) or default TeX/Symbol fonts
    3. Configurable formula character pattern (`vchar_pattern` / `--formular-char-pattern`) or Greek/Math operators
    """
    if not char_text:
        return False
    if char_text.startswith("(cid:"):
        return True
    fn = font_name or ""
    if vfont_pattern:
        if re.search(vfont_pattern, fn):
            return True
    elif re.search(
        r"(?:CM[^RT].*|MS.*|.*Ital|.*Math|.*Symbol|MT2.*|MT\s*Extra|EUFM.*|EUEX.*|WASY.*|RSFS.*|STMARY.*|TXSY.*)",
        fn,
        re.IGNORECASE,
    ):
        return True
    if vchar_pattern:
        if re.search(vchar_pattern, char_text):
            return True
    elif (
        _EXPLICIT_MATH_OPS.search(char_text)
        or re.search(r"[\u0370-\u03FF\u2200-\u22FF]", char_text)
        or any(0xF000 <= ord(c) <= 0xF0FF for c in char_text)
    ):
        return True
    return False


def _font_is_math(font_name: str) -> bool:
    fl = (font_name or "").lower()
    if any(mf in fl for mf in _MATH_FONTS):
        return True
    return bool(
        re.search(
            r"(?:^cm[^rt]|^ms[ab]m|^mt2|^eufm|^euex|^wasy|^rsfs|^stmary|^txsy)",
            fl,
            re.IGNORECASE,
        )
    )


def _has_vowel(word: str) -> bool:
    for ch in word.lower():
        if ch in _VOWELS or (ord(ch) > 127 and ch.isalpha()):
            return True
    return False


def _is_explicit_math(text: str) -> bool:
    return bool(_EXPLICIT_MATH_OPS.search(text))


def _is_prose_word(word: str, has_vni_font: bool = False) -> bool:
    """True when `word` looks like a natural-language word in any language."""
    clean = re.sub(r"^[,.;:()\[\]{}\"'«»—–-]+|[,.;:()\[\]{}\"'«»—–-]+$", "", word)
    if len(clean) < 2 or clean.startswith("$"):
        return False
    if _is_explicit_math(clean) or any(ch.isdigit() for ch in clean):
        return False
    if has_vni_font or has_vni_encoding(clean):
        return True
    if any(ord(ch) > 127 and ch.isalpha() and not (0x0370 <= ord(ch) <= 0x03FF) for ch in clean):
        return True
    if not clean.isalpha():
        return False
    return _has_vowel(clean)


@dataclass
class _RawWord:
    text: str
    bbox: tuple[float, float, float, float]
    font_name: str
    font_size: float
    flags: int
    italic: bool
    bold: bool
    span_id: str


def _words_from_span(span) -> list[_RawWord]:
    """Split a GlyphSpan into word-level tokens using its char boxes when available."""
    chars = getattr(span, "chars", None) or ()
    if not chars:
        return []
    fn_lower = (span.font_name or "").lower()
    is_italic = bool(span.flags & 2) or "ital" in fn_lower or "oblique" in fn_lower
    is_bold = bool(span.flags & 16) or "bold" in fn_lower

    _vni_floating_diacritics = set("ùúûõïäëâêáàåãéèüøòóìíÙÚÛÕÏÄËÂÊÁÀÅÃÉÈÜØÒÓÌÍ")
    _vni_base_vowels = set("aeiouyôöAEIOUYÔÖ")
    is_vni_span = "vni" in fn_lower or has_vni_encoding("".join(c.char for c in chars), span.font_name)

    words: list[list] = []
    cur: list = []
    idx_c = 0
    n_chars = len(chars)
    while idx_c < n_chars:
        ch = chars[idx_c]
        if ch.char in (" ", "\u00a0"):
            if (
                is_vni_span
                and cur
                and cur[-1].char in _vni_base_vowels
                and idx_c + 1 < n_chars
                and chars[idx_c + 1].char in _vni_floating_diacritics
            ):
                cur.append(chars[idx_c + 1])
                words.append(cur)
                cur = []
                idx_c += 2
                continue
            if cur:
                words.append(cur)
                cur = []
            idx_c += 1
            continue
        # If the PDF stream left a horizontal TJ kerning gap (>= 2.2pt) inside a span
        # to accommodate an inline 2D superscript/subscript span (e.g. 'b' [2] '-4ac>0'),
        # split here so the superscript/subscript sorts by x0 into its exact slot.
        if cur and (ch.bbox[0] - cur[-1].bbox[2]) >= 2.2:
            if not (is_vni_span and ch.char in _vni_floating_diacritics):
                words.append(cur)
                cur = []
        cur.append(ch)
        idx_c += 1
    if cur:
        words.append(cur)

    from layoutlingua.processing.normalizers.legacy_vietnamese import VietnameseLegacyNormalizer

    vni_norm = VietnameseLegacyNormalizer()
    out: list[_RawWord] = []
    for group in words:
        raw_text = decode_symbol_pua("".join(c.char for c in group))
        if is_vni_span or vni_norm.should_apply(raw_text, font_name=span.font_name):
            text = vni_norm.normalize(raw_text, font_name=span.font_name).text
        else:
            text = raw_text
        x0 = min(c.bbox[0] for c in group)
        y0 = min(c.bbox[1] for c in group)
        x1 = max(c.bbox[2] for c in group)
        y1 = max(c.bbox[3] for c in group)
        out.append(_RawWord(text, (x0, y0, x1, y1), span.font_name, span.font_size, span.flags, is_italic, is_bold, span.span_id))
    return out


def build_word_tokens(block: TextBlock) -> list[WordToken]:
    """Flatten block spans into reading-ordered word tokens with line indices.

    Separates main-line words from 2D sub/superscript words first so superscripts
    (which have smaller y0) and subscripts (which have larger y1) are attached to
    their parent line in left-to-right reading order instead of creating fake rows.
    """
    if not any(getattr(s, "chars", None) for s in block.spans):
        return []
    raws: list[_RawWord] = []
    for span in block.spans:
        raws.extend(_words_from_span(span))
    if not raws:
        return []

    max_fs = max((w.font_size for w in raws), default=12.0)
    def _is_2d_script_raw(w: _RawWord) -> bool:
        if w.font_size >= max_fs * 0.82 or w.font_size > 9.5:
            return False
        w_clean = re.sub(r"^[(\[{«\"']|[)\]}»\"'.,:;!?…]+$", "", w.text.strip())
        if len(w_clean) >= 4 and _is_prose_word(w_clean, "vni" in (w.font_name or "").lower()):
            return False
        return True

    main_raws = [w for w in raws if not _is_2d_script_raw(w)]
    sub_sup_raws = [w for w in raws if _is_2d_script_raw(w)]
    if not main_raws:
        main_raws = list(raws)
        sub_sup_raws = []

    main_raws.sort(key=lambda w: (w.bbox[1] + w.bbox[3]) / 2.0)
    rows: list[list[_RawWord]] = []
    row_cys: list[float] = []
    row_tol = max(4.5, max_fs * 0.42)
    for w in main_raws:
        cy = (w.bbox[1] + w.bbox[3]) / 2.0
        if rows and abs(cy - row_cys[-1]) <= row_tol:
            rows[-1].append(w)
            main_in_row = [rw for rw in rows[-1] if not _is_2d_script_raw(rw)]
            row_cys[-1] = sum((rw.bbox[1] + rw.bbox[3]) / 2.0 for rw in main_in_row) / len(main_in_row)
        else:
            rows.append([w])
            row_cys.append(cy)

    # Attach each 2D superscript/subscript word to its nearest parent row
    sub_sup_ids: set[int] = {id(sw) for sw in sub_sup_raws}
    for sw in sub_sup_raws:
        sw_cy = (sw.bbox[1] + sw.bbox[3]) / 2.0
        best_idx = min(range(len(rows)), key=lambda idx: abs(sw_cy - row_cys[idx]))
        rows[best_idx].append(sw)

    span_by_id = {s.span_id: s for s in block.spans}
    tokens: list[WordToken] = []
    for line_index, row in enumerate(rows):
        row.sort(key=lambda w: (round(w.bbox[0], 1), 1 if id(w) in sub_sup_ids else 0))
        row_tokens: list[WordToken] = []
        for w in row:
            fn_lower = (w.font_name or "").lower()
            is_sub_sup = id(w) in sub_sup_ids
            wt_new = WordToken(
                text=w.text,
                bbox=w.bbox,
                font_name=w.font_name,
                font_size=w.font_size,
                flags=w.flags,
                italic=w.italic,
                bold=w.bold,
                span_id=w.span_id,
                has_symbol_font=_font_is_math(fn_lower),
                has_vni_font="vni" in fn_lower,
                has_adjacent_sub_sup=is_sub_sup,
                line_index=line_index,
            )
            # Coalesce touching sub-word fragments split across adjacent spans on the same baseline
            # (e.g. 'f(x' + '₁' + ')<f(x' + '₂' + ');', or 'f’’(x' + '₀' + ')=0', or '(x' + '₁,')
            if (
                row_tokens
                and not is_sub_sup
                and not row_tokens[-1].has_adjacent_sub_sup
                and row_tokens[-1].span_id != wt_new.span_id
                and -1.5 <= (wt_new.bbox[0] - row_tokens[-1].bbox[2]) <= 1.5
            ):
                prev_rt = row_tokens[-1]
                sp_prev = span_by_id.get(prev_rt.span_id)
                sp_curr = span_by_id.get(wt_new.span_id)
                no_boundary_space = (
                    sp_prev is not None
                    and sp_curr is not None
                    and not (sp_prev.text or "").endswith((" ", "\t", "\n", "\xa0"))
                    and not (sp_curr.text or "").startswith((" ", "\t", "\n", "\xa0"))
                )
                prev_is_prose = _is_prose_word(prev_rt.text, prev_rt.has_vni_font) and prev_rt.text.strip().lower() not in _ISO_MATH_FUNCTIONS
                curr_is_prose = _is_prose_word(wt_new.text, wt_new.has_vni_font) and wt_new.text.strip().lower() not in _ISO_MATH_FUNCTIONS
                unmatched_close_delim = (
                    wt_new.text.strip().startswith((")", "]"))
                    and prev_rt.text.count("(") <= prev_rt.text.count(")")
                    and prev_rt.text.count("[") <= prev_rt.text.count("]")
                )
                combined_txt = prev_rt.text + wt_new.text
                if (
                    no_boundary_space
                    and not prev_is_prose
                    and not curr_is_prose
                    and not unmatched_close_delim
                    and (
                        _is_explicit_math(combined_txt)
                        or any(ch in combined_txt for ch in "()[]{}+-*/=<>≤≥≠≈₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶₇⁸⁹ₙₖᵢⱼₘₚₛₜ")
                    )
                ):
                    prev_rt.text = combined_txt
                    prev_rt.bbox = (
                        min(prev_rt.bbox[0], wt_new.bbox[0]),
                        min(prev_rt.bbox[1], wt_new.bbox[1]),
                        max(prev_rt.bbox[2], wt_new.bbox[2]),
                        max(prev_rt.bbox[3], wt_new.bbox[3]),
                    )
                    prev_rt.italic = prev_rt.italic or wt_new.italic
                    prev_rt.has_symbol_font = prev_rt.has_symbol_font or wt_new.has_symbol_font
                    prev_rt.span_id = wt_new.span_id
                    continue
            row_tokens.append(wt_new)
        for idx_t, tok in enumerate(row_tokens):
            if tok.has_adjacent_sub_sup and idx_t > 0:
                prev_tok = row_tokens[idx_t - 1]
                if prev_tok.bbox[0] - 1.0 <= tok.bbox[0] <= prev_tok.bbox[2] + 4.5:
                    prev_clean = re.sub(r"^[(\[{«\"']|[)\]}»\"'.,:;!?…]+$", "", prev_tok.text.strip())
                    if len(prev_clean) <= 2 or not _is_prose_word(prev_clean, prev_tok.has_vni_font):
                        prev_tok.has_adjacent_sub_sup = True
        tokens.extend(row_tokens)
    return tokens


def _classify_word(word: WordToken, line_is_mostly_italic: bool) -> bool:
    """Port of the TS `isMathWordToken` classifier for a single word."""
    raw = decode_symbol_pua(word.text).strip()
    if not raw:
        return False

    # 1. Font-table flags (vflag): Symbol / MT Extra / TeX math fonts
    if word.has_symbol_font or _font_is_math(word.font_name):
        return True

    # 2. Adjacent 2D sub/superscript
    if word.has_adjacent_sub_sup:
        return True

    # 3. Structural numbering & bullet prefixes ("1.", "12.", "a)", "b)", "f)", "I.", "II.", "•", "-")
    if re.match(r"^(?:\d{1,2}\.|[a-zA-Z]\)|[IVX]{1,4}\.|\([a-zA-Z0-9]\)|[-•–])$", raw):
        return False

    # 4. Priority prose check: VNI diacritic words or Unicode Vietnamese/accented prose words
    clean = re.sub(r"^[(\[{«\"']|[)\]}»\"'.,:;!?…]+$", "", raw)
    if not clean:
        return bool(re.match(r"^[+|/\\=<>≤≥≠≈±]+$", raw))

    if has_vni_encoding(clean):
        return False

    # Assembly / shell $-prefixed register or variable identifier (e.g. $zero, $at, $sp, $ra)
    if re.match(r"^\$[a-zA-Z_][a-zA-Z0-9_]*$", clean):
        return True

    if any(ord(ch) > 127 and ch.isalpha() and not (0x0370 <= ord(ch) <= 0x03FF) and not _is_explicit_math(ch) for ch in clean):
        if not re.search(r"[=<>≤≥≠≈±×÷√∑∏∫∞∂∇^_\u00b2\u00b3\u00b9\u2070-\u209f]", clean) and not re.search(r"\d", clean):
            return False

    # Natural language words >= 4 chars with a trailing footnote superscript digit (e.g. "Newton¹", "Pascal²") are prose
    if re.match(r"^[a-zA-ZÀ-ỹ]{4,}[¹²³⁴⁵⁶⁷⁸⁹]$", clean) and _has_vowel(clean[:-1]):
        return False

    # Capitalized natural language words >= 4 chars (e.g. "Translation", "Architecture", "Newton") are prose
    if len(clean) >= 4 and clean.isalpha() and clean[0].isupper() and clean[1:].islower() and clean.lower() not in _ISO_MATH_FUNCTIONS:
        return False

    # Lowercase natural language words >= 4 chars with vowels that are not ISO math functions are prose
    if len(clean) >= 4 and clean.isalpha() and clean.islower() and _has_vowel(clean) and clean.lower() not in _ISO_MATH_FUNCTIONS:
        if not _ISO_FUNC_REGEX.match(clean):
            return False

    # 5. Explicit mathematical operators, relations, Greek letters, or superscripts/subscripts
    if _is_explicit_math(raw) or re.search(r"[\u0370-\u03FF\u2200-\u22FF\u2190-\u21FF\u00b2\u00b3\u00b9\u2070-\u209f]", raw):
        return True

    # 6. Function notation f(x), f'(x), f’’(x), P(A), g(t), sin(x), n(n=0,1,2,…), or parenthesized algebraic expressions (a+b)
    if re.match(r"^[a-zA-Zα-ωΑ-Ω]{0,6}['’′]*\([a-zA-Z0-9α-ωΑ-Ω,+\-*/=\s.…\u00b2\u00b3\u00b9\u2070-\u209f]*\)[.,:;!?]*$", raw):
        alpha_parts = re.findall(r"[a-zA-ZÀ-ỹ]+", clean)
        if not alpha_parts or all(len(p) <= 2 and p.isascii() or p.lower() in _ISO_MATH_FUNCTIONS for p in alpha_parts):
            return True

    # 6b. Inline algebraic expressions with +, -, *, / over 1-2 letter ASCII variables/numbers (e.g. a+b, k-1, n+1, +…+n)
    # Exclude uppercase alphabetical ranges / hyphenated labels (e.g. A-Z, X-Y)
    if re.search(r"[+\-*/]", clean) and not re.match(r"^[A-Z]+-[A-Z]+$", clean):
        alpha_parts = re.findall(r"[a-zA-ZÀ-ỹ]+", clean)
        if alpha_parts and all(len(p) <= 2 and p.isascii() for p in alpha_parts):
            return True

    # 7. Prime derivatives: f', y'', f’, f’’, A', B'
    if re.match(r"^[a-zA-Z]{1,2}[′'’]{1,3}[.,:;]?$", raw):
        return True

    # 8. Geometric dot product / ratio / coordinate notation: A.C, H.C, M.N, a.b, a:b
    if re.match(r"^[a-zA-Z]{1,2}[.:][a-zA-Z]{1,2}[.,:;]?$", raw) and not re.match(r"^(?:e\.g|i\.e|dr|mr|ms|vs|ch|tr|tp|st)$", clean, re.IGNORECASE):
        return True

    # 9. Factorials, indexed variables, differentials, and coordinate tuples: n!, k!, x1, a2, M1, udx, 0,c
    # Exclude English ordinals like 1st, 2nd, 3rd, 4th.
    if not re.match(r"^\d+(?:st|nd|rd|th)[.,:;]?$", raw, re.IGNORECASE) and re.match(
        r"^(?:[a-zA-Z]!(?:[.,:;])?|[a-zA-Z]{1,2}\d+[.,:;]?|\d+[a-zA-Z]{1,2}[.,:;]?|"
        r"[a-z]{1,2}d[xyzuvt][.,:;]?|[a-zA-Z0-9′'’]+(?:[,;][a-zA-Z0-9′'’]+)+[.,:;]?)$",
        raw,
    ):
        if any(c.isdigit() or c in ",;!" for c in raw) or re.match(r"^[a-z]{1,2}d[xyzuvt]$", clean):
            return True

    # 10. ISO 80000-2 function names (incl. fused forms like sinx, cos2x)
    if clean.lower() in _ISO_MATH_FUNCTIONS or _ISO_FUNC_REGEX.match(clean):
        return True

    # 11. Consonant-only lowercase algebraic clusters (kl, mn, pq, xy, bh, ch when italic)
    if (
        2 <= len(clean) <= 4
        and _CONSONANT_CLUSTER.match(clean)
        and not _ROMAN_NUMERAL_RE.match(clean)
        and clean.lower() not in ("vs", "mr", "ms", "dr", "st", "nd", "rd", "th", "pp", "cf")
    ):
        if clean.islower():
            return True

    # 12. Uppercase geometric vertex / segment / triangle / matrix identifiers: AB, ABC, ABCD, MN, PQ
    # Exclude common 3-4 letter upright ALL-CAPS English prose headers (e.g. NAME, SIZE, USE, CALL, TYPE, CODE, DATA)
    if re.match(r"^[A-Z]{2,4}$", clean) and not _ROMAN_NUMERAL_RE.match(clean):
        if not word.italic and (
            re.match(r"^[A-Z]{3}E$", clean)
            or clean in ("USE", "CALL", "WORD", "DATA", "MASK", "TEXT", "TRAP", "SIGN", "ZERO", "HIGH", "LOAD")
        ):
            return False
        if not word.bold or word.italic:
            return True

    # 13. Mixed-case math tokens without diacritics: mA, nB, dC, xOM, yON, cosA, sinB, or italic Ach, Bhc
    if re.match(r"^[a-z]{1,3}[A-Z]{1,3}$", clean):
        return True
    if word.italic and not line_is_mostly_italic and re.match(r"^[A-Z][bcdfghjklmnpqrstvwxz]{1,3}$", clean):
        return True

    # 14. Italic 1-3 letter ASCII variables inside upright paragraphs (x, y, n., ab, ac)
    if word.italic and not line_is_mostly_italic and re.match(r"^[a-zA-Z]{1,3}[.,:;]?$", clean):
        if (len(clean) <= 2 and clean.isascii() and not word.has_vni_font) or not _is_prose_word(clean, word.has_vni_font):
            return True

    # 15. Single ASCII letter variable (recovered in Pass 3 if upright & adjacent to prose)
    if len(clean) == 1 and clean.isalpha():
        return True

    # 16. Prose safeguard: multi-character prose words in any language
    if _is_prose_word(clean, word.has_vni_font):
        return False

    # 17. Sub/superscript-sized short alphanumeric tokens
    if word.has_adjacent_sub_sup and word.font_size <= 8.5 and len(clean) <= 4 and not word.has_vni_font:
        return True

    return False


def classify_word_tokens(tokens: list[WordToken]) -> None:
    """Classify word tokens in place, including 2D sub/sup adjacency and the
    contextual recovery pass from the TS engine."""
    if not tokens:
        return

    # Line-level italic statistics for the contextual recovery pass
    line_stats: dict[int, dict[str, int]] = {}
    for w in tokens:
        st = line_stats.setdefault(w.line_index, {"italic_prose": 0, "upright_prose": 0})
        if _is_prose_word(w.text, w.has_vni_font):
            if w.italic:
                st["italic_prose"] += 1
            else:
                st["upright_prose"] += 1

    def line_is_mostly_italic(li: int) -> bool:
        st = line_stats.get(li)
        if not st:
            return False
        total = st["italic_prose"] + st["upright_prose"]
        return total >= 2 and st["italic_prose"] / total >= 0.6

    # Pass 1: word classification
    for w in tokens:
        w.is_math = _classify_word(w, line_is_mostly_italic(w.line_index))

    # Pass 2: 2D sub/superscript adjacency — small tokens adjacent to a main
    # word mark both as frozen math (P_n., a_i^k, x_0, vector overbars).
    max_tok_fs = max((w.font_size for w in tokens), default=12.0)
    small = [
        w for w in tokens
        if w.font_size < max_tok_fs * 0.82 and w.font_size <= 9.5 and not w.has_vni_font and w.text.strip()
    ]
    for w in tokens:
        if w in small:
            continue
        wx0, wy0, wx1, wy1 = w.bbox
        for s in small:
            if s.line_index != w.line_index:
                continue
            sx0, sy0, sx1, sy1 = s.bbox
            s_center_x = (sx0 + sx1) / 2.0
            if not (wx0 - 3.0 <= s_center_x <= wx1 + 3.0):
                continue
            baseline_shift = abs((sy0 + sy1) / 2.0 - (wy0 + wy1) / 2.0)
            if baseline_shift >= 1.5 or s.font_size < 0.62 * w.font_size:
                w_clean = re.sub(r"^[(\[{«\"']|[)\]}»\"'.,:;!?…]+$", "", w.text.strip())
                if len(w_clean) <= 2 or not _is_prose_word(w_clean, w.has_vni_font):
                    w.has_adjacent_sub_sup = True
                    w.is_math = True
                s.is_math = True
                break

    # Pass 3: Contextual bridge, ALL-CAPS heading recovery, & 1D single-letter prose recovery
    by_line: dict[int, list[WordToken]] = {}
    for w in tokens:
        by_line.setdefault(w.line_index, []).append(w)

    for _li, line_toks in by_line.items():
        all_caps_words = [
            t for t in line_toks
            if len(re.sub(r"[^\w]", "", t.text)) >= 1 and t.text.upper() == t.text and any(c.isalpha() for c in t.text)
        ]
        if len(all_caps_words) >= 2 and any(
            len(re.sub(r"[^\w]", "", t.text)) >= 3 and _is_prose_word(t.text, t.has_vni_font)
            for t in all_caps_words
        ):
            for t in all_caps_words:
                if not t.has_adjacent_sub_sup and not t.has_symbol_font and not _is_explicit_math(t.text):
                    t.is_math = False

        # Recover upright 1D single ASCII letters (like "n" in "f) Đa giác đều n cạnh" or English article "a"/"A"/"I")
        # when directly sandwiched between upright prose words, or when "a"/"A"/"I" precedes an upright ASCII prose word.
        for idx, wt in enumerate(line_toks):
            if not wt.is_math or wt.italic or wt.has_adjacent_sub_sup or wt.has_symbol_font:
                continue
            clean_txt = re.sub(r"^[,.;:()\[\]{}\"'«»—–-]+|[,.;:()\[\]{}\"'«»—–-]+$", "", wt.text.strip())
            if len(clean_txt) == 1 and clean_txt.isalpha() and clean_txt.isascii():
                prev_prose = (
                    idx > 0
                    and not line_toks[idx - 1].is_math
                    and _is_prose_word(line_toks[idx - 1].text, line_toks[idx - 1].has_vni_font)
                )
                next_prose = (
                    idx + 1 < len(line_toks)
                    and not line_toks[idx + 1].is_math
                    and _is_prose_word(line_toks[idx + 1].text, line_toks[idx + 1].has_vni_font)
                )
                next_is_ascii_prose = (
                    next_prose
                    and line_toks[idx + 1].text.strip().isascii()
                    and not line_toks[idx + 1].has_vni_font
                )
                if prev_prose and next_prose:
                    wt.is_math = False
                elif clean_txt in ("a", "A", "I") and next_is_ascii_prose:
                    wt.is_math = False

        # Group tightly attached opening/closing parentheses around math tokens (e.g. "(", "a+b", ")", "ⁿ")
        for idx, wt in enumerate(line_toks):
            if wt.is_math:
                continue
            t_strip = wt.text.strip()
            if t_strip in ("(", "[") and idx + 1 < len(line_toks) and line_toks[idx + 1].is_math:
                if (line_toks[idx + 1].bbox[0] - wt.bbox[2]) <= 2.5:
                    # Check if there is a matching closing bracket after the math run
                    k = idx + 1
                    while k < len(line_toks) and line_toks[k].is_math:
                        k += 1
                    if k < len(line_toks) and line_toks[k].text.strip().startswith((")", "]")):
                        wt.is_math = True
                        line_toks[k].is_math = True
            elif t_strip.startswith((")", "]")) and idx > 0 and line_toks[idx - 1].is_math:
                if (wt.bbox[0] - line_toks[idx - 1].bbox[2]) <= 2.5:
                    if (
                        any("(" in line_toks[m].text or "[" in line_toks[m].text for m in range(max(0, idx - 4), idx) if line_toks[m].is_math)
                        or (idx + 1 < len(line_toks) and line_toks[idx + 1].is_math and (line_toks[idx + 1].bbox[0] - wt.bbox[2]) <= 2.5)
                    ):
                        wt.is_math = True

    # Numeric/operator bridges between math tokens or directly attached to explicit relational operators (e.g. ab ≥ 0)
    for idx, w in enumerate(tokens):
        if w.is_math or not _NUMERIC_BRIDGE.match(w.text):
            continue
        w_strip = w.text.strip()
        prev_math = idx > 0 and tokens[idx - 1].is_math and tokens[idx - 1].line_index == w.line_index
        next_math = idx + 1 < len(tokens) and tokens[idx + 1].is_math and tokens[idx + 1].line_index == w.line_index
        if prev_math and next_math:
            if not (w_strip in (",", ";", ":") and "(" in tokens[idx + 1].text):
                w.is_math = True
        elif (
            prev_math
            and re.search(r"[=<>≤≥≠≈±+\-*/]", tokens[idx - 1].text)
            and any(c.isdigit() for c in w_strip)
            and not w_strip.endswith((",", ";", ":", "…"))
        ):
            w.is_math = True
        elif (
            next_math
            and re.search(r"[=<>≤≥≠≈±+\-*/]", tokens[idx + 1].text)
            and any(c.isdigit() for c in w_strip)
            and not w_strip.endswith((",", ";", ":", "…"))
        ):
            w.is_math = True
