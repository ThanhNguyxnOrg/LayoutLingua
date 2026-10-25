"""Word-level math tokenization ported from the TS engine's Sub-Line Formula Pinning.

Splits GlyphSpans into word tokens using char-level geometry, classifies each word
with the TS `isMathWordToken` rules (vflag fonts, explicit operators, ISO function
names, consonant clusters, italic style-switch, 2D sub/superscript adjacency), and
runs the contextual recovery pass. Zero hardcoded natural-language word lists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from layoutlingua.core.ir import TextBlock

_MATH_FONTS = (
    "math", "symbol", "cmmi", "cmsy", "cmex", "msam", "msbm", "mt2", "mt ",
    "mathtype", "eufm", "euex", "wasy", "rsfs", "txsy", "stmary", "mt extra",
)

_EXPLICIT_MATH_OPS = re.compile(r"[=<>≠≤≥±∑∏∫√∞∂∇∈⊂⇒⇔≡−–—^]")

_ISO_MATH_FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "lim",
    "max", "min", "det", "deg", "rad", "gcd", "lcm", "sinh", "cosh", "tanh",
    "dx", "dy", "dt",
}

_CONSONANT_CLUSTER = re.compile(r"^[bcdfghjklmnpqrstvwxz]+$")

_NUMERIC_BRIDGE = re.compile(r"^[\d.,:;+=\-*/_~^…≤≥()\[\]{} ]+$")

_VOWELS = set("aeiouàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựýỳỷỹỵ")


@dataclass
class WordToken:
    """A word-level token with geometry and math classification."""

    text: str
    bbox: tuple[float, float, float, float]
    font_name: str
    font_size: float
    flags: int
    italic: bool
    span_id: str
    is_math: bool = False
    has_adjacent_sub_sup: bool = False
    line_index: int = 0


def _font_is_math(font_name: str) -> bool:
    f = (font_name or "").lower()
    return any(mf in f for mf in _MATH_FONTS)


def _is_explicit_math(text: str) -> bool:
    return bool(_EXPLICIT_MATH_OPS.search(text))


def _has_vowels(text: str) -> bool:
    return any(ch.lower() in _VOWELS for ch in text)


def _is_prose_word(text: str) -> bool:
    """A word is prose when it is a 3+ letter alphabetic token containing vowels."""
    core = re.sub(r"[^\w]", "", text, flags=re.UNICODE)
    if len(core) < 3 or not core.isalpha():
        return False
    if core.lower() in _ISO_MATH_FUNCTIONS:
        return False
    return _has_vowels(core)


@dataclass
class _RawWord:
    text: str
    bbox: tuple[float, float, float, float]
    font_name: str
    font_size: float
    flags: int
    italic: bool
    span_id: str


def _words_from_span(span) -> list[_RawWord]:
    """Split a span's text into word boxes using char geometry when available."""
    chars = getattr(span, "chars", None) or []
    words: list[_RawWord] = []

    joined = "".join(c.char for c in chars)
    if joined != span.text:
        # Char data does not reconstruct the span text (combining marks or
        # synthetic test spans): fall back to span-level tokenization.
        pass
    elif chars:
        cur: list = []
        for ch in chars:
            if ch.char == " " or ch.char == "\u00a0":
                if cur:
                    words.append(cur)
                    cur = []
                continue
            cur.append(ch)
        if cur:
            words.append(cur)
        out: list[_RawWord] = []
        for group in words:
            text = "".join(c.char for c in group)
            x0 = min(c.bbox[0] for c in group)
            y0 = min(c.bbox[1] for c in group)
            x1 = max(c.bbox[2] for c in group)
            y1 = max(c.bbox[3] for c in group)
            out.append(_RawWord(text, (x0, y0, x1, y1), span.font_name, span.font_size, span.flags, "ital" in span.font_name.lower() or bool(span.flags & 2), span.span_id))
        return out

    # Fallback: no char geometry — treat the whole span as one word
    return [
        _RawWord(
            span.text,
            span.bbox,
            span.font_name,
            span.font_size,
            span.flags,
            "ital" in span.font_name.lower() or bool(span.flags & 2),
            span.span_id,
        )
    ]


def build_word_tokens(block: TextBlock) -> list[WordToken]:
    """Flatten block spans into reading-ordered word tokens with line indices."""
    raws: list[_RawWord] = []
    for span in block.spans:
        raws.extend(_words_from_span(span))

    # Reading order: sequential baseline-row clustering (top to bottom, 3pt
    # tolerance), then x within each row — a coarse y-bucket sort scrambles
    # same-line items whose baselines differ by a point.
    raws.sort(key=lambda w: w.bbox[1])
    rows: list[list[_RawWord]] = []
    for w in raws:
        cy = (w.bbox[1] + w.bbox[3]) / 2.0
        if rows:
            last = rows[-1][-1]
            last_cy = (last.bbox[1] + last.bbox[3]) / 2.0
            if abs(cy - last_cy) <= 3.0:
                rows[-1].append(w)
                continue
        rows.append([w])

    tokens: list[WordToken] = []
    for line_index, row in enumerate(rows):
        row.sort(key=lambda w: w.bbox[0])
        for w in row:
            tokens.append(
                WordToken(
                    text=w.text,
                    bbox=w.bbox,
                    font_name=w.font_name,
                    font_size=w.font_size,
                    flags=w.flags,
                    italic=w.italic,
                    span_id=w.span_id,
                    line_index=line_index,
                )
            )
    return tokens


def _classify_word(word: WordToken, line_is_mostly_italic: bool) -> bool:
    """Port of the TS isMathWordToken classifier for a single word."""
    text = word.text.strip()
    if not text:
        return False

    # 1. Font-table flags (vflag): Symbol / MT Extra / TeX math fonts
    if _font_is_math(word.font_name):
        return True

    # 2. Explicit mathematical operators and differentials
    if _is_explicit_math(text):
        return True

    # 3. ISO 80000-2 function names (incl. fused forms like sinx)
    if text.lower() in _ISO_MATH_FUNCTIONS:
        return True

    # 4. Consonant-only lowercase algebraic clusters (kl, mn, pq, xy) without vowels
    if 2 <= len(text) <= 4 and _CONSONANT_CLUSTER.match(text):
        return True

    # 5. Italic 1-3 letter ASCII variables inside upright paragraphs (x, y, n., ab)
    if word.italic and not line_is_mostly_italic and re.match(r"^[a-z]{1,3}[.,:;]?$", text, re.IGNORECASE):
        return True

    # 6. Prose safeguard: multi-character prose words in any language
    if _is_prose_word(text):
        return False

    # 7. Sub/superscript-sized short alphanumeric tokens
    if word.font_size <= 8.5 and len(text) <= 4:
        return True

    # 8. Short numeric tokens act as math only when bridging math neighbours
    #    (handled by the caller's grouping pass).
    return False


def classify_word_tokens(tokens: list[WordToken]) -> None:
    """Classify word tokens in place, including 2D sub/sup adjacency and the
    contextual recovery pass (paragraph-relative italic switch)."""
    if not tokens:
        return

    # Line-level italic statistics for the contextual recovery pass
    line_stats: dict[int, dict[str, int]] = {}
    for w in tokens:
        st = line_stats.setdefault(w.line_index, {"italic_prose": 0, "upright_prose": 0})
        if _is_prose_word(w.text):
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
    small = [w for w in tokens if w.font_size <= 8.5 and w.text.strip()]
    for w in tokens:
        if w in small:
            continue
        wx0, wy0, wx1, wy1 = w.bbox
        for s in small:
            # Sub/superscript adjacency is strictly intra-line: a small glyph on
            # the NEXT line shares the x-window and would otherwise flag every
            # prose word of the line above as math.
            if s.line_index != w.line_index:
                continue
            sx0, sy0, sx1, sy1 = s.bbox
            s_center_x = (sx0 + sx1) / 2.0
            # The small glyph's center must sit within +-3pt of the word's own
            # box: a looser forward pad reaches across into the NEXT word's
            # subscript (e.g. 'và n1' flagging 'và').
            if not (wx0 - 3.0 <= s_center_x <= wx1 + 3.0):
                continue
            baseline_shift = abs((sy0 + sy1) / 2.0 - (wy0 + wy1) / 2.0)
            if baseline_shift >= 1.5 or s.font_size < 0.62 * w.font_size:
                w.has_adjacent_sub_sup = True
                w.is_math = True
                s.is_math = True
                break

    # Pass 3: contextual recovery — leading parenthetical numeric variables
    # followed immediately by math stay math; isolated pure numbers between two
    # math tokens inherit math classification (bridges).
    for idx, w in enumerate(tokens):
        if w.is_math or not _NUMERIC_BRIDGE.match(w.text):
            continue
        prev_math = idx > 0 and tokens[idx - 1].is_math
        next_math = idx + 1 < len(tokens) and tokens[idx + 1].is_math
        if prev_math and next_math:
            w.is_math = True
