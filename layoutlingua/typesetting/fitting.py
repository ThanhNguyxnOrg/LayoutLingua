"""Adaptive font fitting using binary search, dynamic lineheight, and overflow classification."""

from __future__ import annotations

import re

import pymupdf

from layoutlingua.typesetting.fonts import BUILTIN_OR_CJK_FONTS, FontManager
from layoutlingua.typesetting.models import OverflowCause, TypesetOptions

# Standard Table of Contents dot leader pattern:
# Matches either Title + 2+ dots/dashes + page number, OR Title + 5+ trailing dots (when page number is in a separate right-hand block)
TOC_LEADER_PATTERN = re.compile(r"^(.*?\S)(?:(\s*[\.\:\-_–—…]{2,}\s*)(\d+)|(\s*[\.\…]{5,}))\s*$")


class TextFitTester:
    """Evaluates whether text fits within a bounding box using precision binary search."""

    def __init__(self, font_manager: FontManager, font_name: str = "DejaVuSans") -> None:
        self.font_manager = font_manager
        self.font_name = font_name
        self._doc = pymupdf.open()
        self._page = self._doc.new_page(width=1000, height=1000)
        self.font_manager.register_on_page(self._page, font_name=self.font_name)
        self.font_manager.register_on_page(self._page, font_name=f"{self.font_name}-Bold")
        self._registered_fonts: set[str] = {self.font_name, f"{self.font_name}-Bold"}

    def adapt_dot_leader_if_needed(
        self,
        text: str,
        target_width: float,
        font_size: float,
        font_name: str | None = None,
    ) -> str:
        """Dynamically adjust dot leader length for Table of Contents lines (LaTeX \\dotfill pattern).

        Prevents line-wrapping which causes catastrophic single-line OVERFLOW_FALLBACK.
        """
        if not text or target_width <= 0:
            return text

        match = TOC_LEADER_PATTERN.match(text.strip())
        if not match:
            return text

        prefix = match.group(1).rstrip()
        suffix = (match.group(3) or "").strip()

        active_font = font_name or self.font_name
        prefix_len = self.font_manager.measure_text_length(prefix, font_size, active_font)
        suffix_len = self.font_manager.measure_text_length(suffix, font_size, active_font) if suffix else 0.0
        space_len = self.font_manager.measure_text_length(" ", font_size, active_font)
        dot_len = max(1.0, self.font_manager.measure_text_length(".", font_size, active_font))

        if suffix:
            # Available width for dot leader + page number with a safety cushion of 8.0pt
            avail_width = target_width - prefix_len - suffix_len - (2 * space_len) - 8.0
            if avail_width <= dot_len * 2:
                return f"{prefix} ... {suffix}"

            num_dots = int(avail_width / dot_len)
            num_dots = max(3, min(num_dots, 120))
            dots_str = "." * num_dots
            return f"{prefix} {dots_str} {suffix}"
        else:
            # Trailing dot leader without inline page number (page number in separate right-hand block)
            avail_width = target_width - prefix_len - space_len - 4.0
            if avail_width <= dot_len * 3:
                return f"{prefix} ..."

            num_dots = int(avail_width / dot_len)
            num_dots = max(3, min(num_dots, 120))
            dots_str = "." * num_dots
            return f"{prefix} {dots_str}"

    def hyphenate_word(
        self,
        word: str,
        avail_w: float,
        font_size: float,
        font_name: str | None = None,
    ) -> list[str]:
        """Split a long alphabetic word into hyphenated syllable segments that each fit within avail_w."""
        active_font = font_name or self.font_name
        if (
            self.font_manager.measure_text_length(word, font_size, active_font) <= avail_w
            or len(word) < 5
            or not any(c.isalpha() for c in word)
            or any(0x2E80 <= ord(c) <= 0x9FFF or 0x3040 <= ord(c) <= 0x30FF or 0xAC00 <= ord(c) <= 0xD7AF for c in word)
        ):
            return [word]

        vowels = set(
            "aeiouyàáâãäåæèéêëìíîïòóôõöøùúûüýÿăơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
            "AEIOUYÀÁÂÃÄÅÆÈÉÊËÌÍÎÏÒÓÔÕÖØÙÚÛÜÝŸĂƠƯ"
        )
        inseparable = {
            "ch", "ph", "th", "sh", "gn", "qu", "tr", "pl", "pr", "bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr",
        }
        parts: list[str] = []
        rem = word
        while self.font_manager.measure_text_length(rem, font_size, active_font) > avail_w and len(rem) >= 5:
            best_k: int | None = None
            best_score = -1e9
            for k in range(2, len(rem) - 1):
                piece = rem[:k] + "-"
                if self.font_manager.measure_text_length(piece, font_size, active_font) <= avail_w:
                    c_prev = rem[k - 1]
                    c_curr = rem[k]
                    c_next = rem[k + 1] if k + 1 < len(rem) else ""
                    pair = (c_prev + c_curr).lower()
                    score = k * 3.0
                    if pair in inseparable:
                        score -= 40.0
                    elif c_prev in vowels and c_curr not in vowels and c_next in vowels:
                        score += 30.0  # V-CV open syllable boundary (e.g. Hexa-déci-mal)
                    elif c_prev not in vowels and c_curr not in vowels and any(ch in vowels for ch in rem[:k]):
                        score += 25.0  # VC-CV closed syllable boundary (e.g. opéra-tion-nel)
                    elif c_prev in vowels and c_curr not in vowels:
                        score += 12.0
                    if len(rem) - k == 2:
                        score -= 8.0
                    if score > best_score:
                        best_score = score
                        best_k = k
            if best_k is None:
                break
            parts.append(rem[:best_k] + "-")
            rem = rem[best_k:]
        parts.append(rem)
        return parts

    def adapt_narrow_multiline_if_needed(
        self,
        text: str,
        target_width: float,
        target_height: float,
        font_size: float,
        font_name: str | None = None,
    ) -> str:
        """Hyphenate words that exceed the column width inside a narrow multi-line bounding box."""
        if not text or target_width <= 0 or target_height < font_size * 1.80 or "\n" in text:
            return text
        active_font = font_name or self.font_name
        avail_w = max(4.0, target_width - 2.5)
        tokens = text.split()
        if not any(self.font_manager.measure_text_length(t, font_size, active_font) > avail_w for t in tokens):
            return text
        out_tokens: list[str] = []
        for tok in tokens:
            if self.font_manager.measure_text_length(tok, font_size, active_font) > avail_w:
                out_tokens.extend(self.hyphenate_word(tok, avail_w, font_size, active_font))
            else:
                out_tokens.append(tok)
        return " ".join(out_tokens)

    def test_fit(
        self,
        rect: tuple[float, float, float, float],
        text: str,
        orig_font_size: float,
        options: TypesetOptions,
        font_name: str | None = None,
    ) -> tuple[bool, float, OverflowCause, int, float]:
        """Determine if text fits within rect using bounded binary search.

        Returns:
            (fits, final_font_size, overflow_cause, line_count, effective_lineheight)
        """
        x0, y0, x1, y1 = rect
        width = x1 - x0
        height = y1 - y0

        effective_lineheight = self.font_manager.calculate_effective_lineheight(
            configured_ratio=options.base_lineheight_ratio,
            safety_padding_em=options.safety_padding_em,
        )

        if width <= 0 or height <= 0 or not text.strip():
            return False, orig_font_size, OverflowCause.OVERFLOW_UNDETERMINED, 0, effective_lineheight

        active_font = font_name or self.font_name
        if active_font not in self._registered_fonts:
            self.font_manager.register_on_page(self._page, font_name=active_font)
            self._registered_fonts.add(active_font)

        is_toc = bool(TOC_LEADER_PATTERN.match(text.strip()))
        # Narrow multi-line column detection: a block with height >= 1.85*orig_font_size whose text is
        # wider than 1.25x box width is a multi-line box (e.g. 2- or 3-line column header), not a single-line row.
        is_multiline_box = height >= orig_font_size * 1.85
        raw_orig_w = self.font_manager.measure_text_length(text.strip(), orig_font_size, active_font)
        is_single_line = (
            (height <= 1.75 * orig_font_size)
            or (height <= 2.2 * orig_font_size and raw_orig_w <= width * 1.25)
            or is_toc
        )

        # For Table of Contents dot-leader lines and single-line labels with default min_font_pt, allow flexible font floor (down to 0.50x or 5.0pt)
        # to prevent catastrophic 2-line wrapping in a 1-line bounding box.
        effective_min_scale = (
            min(options.min_font_scale, 0.50)
            if (is_toc or (is_single_line and options.min_font_pt <= 6.0))
            else options.min_font_scale
        )
        effective_min_pt = (
            min(options.min_font_pt, max(4.2, round(orig_font_size * effective_min_scale, 4) + 1e-5))
            if (is_single_line or is_toc or orig_font_size <= 8.5) and options.min_font_pt <= 6.0
            else options.min_font_pt
        )
        min_font_size = max(effective_min_pt, round(effective_min_scale * orig_font_size, 4) + 1e-5)
        test_rect = pymupdf.Rect(x0, y0, x1, y1)

        fontfile_arg = (
            None
            if active_font.lower() in BUILTIN_OR_CJK_FONTS
            else str(self.font_manager.get_font_path(active_font))
        )

        def _extract_non_cjk_words(txt_val: str) -> list[str]:
            return [
                w for w in txt_val.split()
                if len(w) >= 2 and not any(0x2E80 <= ord(c) <= 0x9FFF or 0x3040 <= ord(c) <= 0x30FF or 0xAC00 <= ord(c) <= 0xD7AF for c in w)
            ]

        words_for_width = _extract_non_cjk_words(text)

        def _longest_word_fits(sz: float, box_w: float, txt_val: str | None = None) -> bool:
            cand_words = _extract_non_cjk_words(txt_val) if txt_val is not None else words_for_width
            if not cand_words:
                return True
            max_word_w = max(self.font_manager.measure_text_length(w, sz, active_font) for w in cand_words)
            # PyMuPDF insert_textbox has internal side margins (~2pt); any word wider than box_w - 2.0
            # will be broken mid-word across lines (e.g. "MATHEMATIC" + "S").
            return max_word_w <= max(4.0, box_w - 2.5)

        # For single-line boxes, if a long word at min_font_size is still wider than box_w - 2.5,
        # allow scaling down to 0.55x so the word fits on one line. For multi-line boxes, keep
        # min_font_size at options.min_font_scale (0.70x) first so step 2c condensed wrapping is tried
        # before ever dropping below the 70% shrink-notice threshold.
        if not is_multiline_box and words_for_width and not _longest_word_fits(min_font_size, width):
            min_font_size = max(effective_min_pt, min(min_font_size, 0.55 * orig_font_size))

        # Enable syllabic hyphenation in narrow multi-line boxes where at min_font_size
        # a single word exceeds the column width (e.g. "Hexadécimal" in a 17pt 3-line column header).
        needs_narrow_hyphenation = (
            is_multiline_box
            and bool(words_for_width)
            and not _longest_word_fits(min_font_size, width)
        )

        def get_text_for_size(sz: float, box_w: float = width) -> str:
            if is_toc:
                return self.adapt_dot_leader_if_needed(text, box_w, sz, active_font)
            if needs_narrow_hyphenation:
                return self.adapt_narrow_multiline_if_needed(text, box_w, height, sz, active_font)
            return text

        def _try_textbox(box_rect: pymupdf.Rect, txt: str, sz: float, lh: float) -> float:
            if not _longest_word_fits(sz, box_rect.width, txt):
                return -1.0
            rc_val = self._page.insert_textbox(
                box_rect,
                txt,
                fontsize=sz,
                fontname=active_font,
                fontfile=fontfile_arg,
                lineheight=lh,
            )
            if rc_val >= 0 and (box_rect.height <= 1.65 * orig_font_size):
                # In a strict single-line row slot, do not allow wrapping into 2+ lines
                est_lines = self._estimate_lines(box_rect.height, rc_val, sz, lh)
                if est_lines > 1 and self.font_manager.measure_text_length(txt, sz, active_font) > box_rect.width * 1.03:
                    return -1.0
            return rc_val

        # 1. Test original size
        text_orig = get_text_for_size(orig_font_size)
        rc_orig = _try_textbox(test_rect, text_orig, orig_font_size, effective_lineheight)
        if rc_orig >= 0:
            lines = self._estimate_lines(height, rc_orig, orig_font_size, effective_lineheight)
            return True, orig_font_size, OverflowCause.NONE, max(1, lines), effective_lineheight

        # 1b. Single-line ink-height & BabelDOC hanging punctuation accommodation:
        # Allow trailing punctuation (.,:;!?)]}) to hang up to 0.35 * font_size outside the right box edge.
        hang_allowance = (
            orig_font_size * 0.35
            if (text_orig.strip() and text_orig.strip()[-1] in ".,:;!?)]}»”’、。，：；！？）》】」』")
            else 0.0
        )
        text_advance = self.font_manager.measure_text_length(text_orig, orig_font_size, active_font)
        if text_advance <= (width * 1.02 + hang_allowance) and abs(rc_orig) <= (orig_font_size * 0.60) and _longest_word_fits(orig_font_size, width + hang_allowance, text_orig):
            return True, orig_font_size, OverflowCause.NONE, 1, effective_lineheight

        # 1c. Multi-line tight ink-bbox accommodation:
        # PyMuPDF's get_text("dict") returns tight glyph boxes whose height is ~0.35-0.40*font_size shorter
        # than insert_textbox's internal lineheight*(asc-desc) requirement for the same N lines.
        natural_lh = min(effective_lineheight, 1.15)
        ink_padded_rect = pymupdf.Rect(x0, y0, x1, y1 + orig_font_size * 0.40) if is_multiline_box else test_rect
        if is_multiline_box and _longest_word_fits(orig_font_size, width, text_orig):
            rc_nat = _try_textbox(ink_padded_rect, text_orig, orig_font_size, natural_lh)
            if rc_nat >= 0:
                lines = self._estimate_lines(ink_padded_rect.height, rc_nat, orig_font_size, natural_lh)
                return True, orig_font_size, OverflowCause.NONE, max(1, lines), natural_lh

        # 2. Test minimum font size floor and determine active search geometry (search_rect, search_lh)
        search_rect = test_rect
        search_lh = effective_lineheight
        text_min = get_text_for_size(min_font_size)
        rc_min = _try_textbox(search_rect, text_min, min_font_size, search_lh)
        if rc_min < 0 and is_multiline_box:
            rc_min_nat = _try_textbox(ink_padded_rect, text_min, min_font_size, natural_lh)
            if rc_min_nat >= 0:
                search_rect = ink_padded_rect
                search_lh = natural_lh
                rc_min = rc_min_nat

        if rc_min < 0:
            # 2a. Lineheight micro-compaction: try tighter lineheight (down to 1.05x)
            compact_lh = max(1.02, effective_lineheight * 0.90)
            cand_rect = ink_padded_rect if is_multiline_box else test_rect
            rc_compact = _try_textbox(cand_rect, text_min, min_font_size, compact_lh)
            if rc_compact >= 0:
                search_rect = cand_rect
                search_lh = compact_lh
                rc_min = rc_compact
            else:
                # 2b. Soft Margin Absorption:
                # Absorb minor vertical overflow (within 1.2 * min_font_size or 15% box height)
                slight_overflow_threshold = 1.2 * min_font_size
                if abs(rc_compact) <= slight_overflow_threshold and _longest_word_fits(min_font_size, width, text_min):
                    soft_pad = min(max(3.0, height * 0.15), slight_overflow_threshold)
                    soft_rect = pymupdf.Rect(x0, y0, x1, y1 + soft_pad)
                    rc_soft = _try_textbox(soft_rect, text_min, min_font_size, compact_lh)
                    if rc_soft >= 0:
                        search_rect = soft_rect
                        search_lh = compact_lh
                        rc_min = rc_soft

            # 2c. Narrow Multi-Line Horizontal Condensation + Syllabic Hyphenation:
            # When a narrow multi-line box (e.g. a 2-line column header) still overflows vertically
            # because uncondensed wrapping splits into too many lines, allow per-line horizontal
            # condensation (down to 0.70x Tz) combined with syllabic hyphenation.
            if rc_min < 0 and is_multiline_box and width < orig_font_size * 8.0:
                cond_w = width / 0.70
                cond_rect = pymupdf.Rect(x0, y0, x0 + cond_w, ink_padded_rect.y1)
                text_cond_min = get_text_for_size(min_font_size, cond_w)
                rc_cond = _try_textbox(cond_rect, text_cond_min, min_font_size, compact_lh)
                if rc_cond >= 0:
                    c_low = min_font_size
                    c_high = min(orig_font_size * 0.90, min_font_size * 1.22)
                    c_best = min_font_size
                    c_best_rc = rc_cond
                    for _ in range(8):
                        c_mid = (c_low + c_high) * 0.5
                        t_mid = get_text_for_size(c_mid, cond_w)
                        rc_m = _try_textbox(cond_rect, t_mid, c_mid, compact_lh)
                        if rc_m >= 0:
                            c_best = c_mid
                            c_best_rc = rc_m
                            c_low = c_mid
                        else:
                            c_high = c_mid
                    lines = self._estimate_lines(cond_rect.height, c_best_rc, c_best, compact_lh)
                    return True, c_best, OverflowCause.NONE, max(1, lines), compact_lh

            if rc_min < 0:
                # Overflow event at minimum scale: classify cause
                cause = self._classify_overflow_cause(text_min, width, min_font_size)
                return False, orig_font_size, cause, 0, effective_lineheight

        # If multi-line box passed at min_font_size on raw test_rect, still allow ink_padded_rect + natural_lh
        # during binary search so 2-line paragraphs are not artificially shrunk by raw ink-bbox height
        if is_multiline_box and search_rect == test_rect:
            search_rect = ink_padded_rect
            search_lh = natural_lh

        # 3. Binary Search in [min_font_size, orig_font_size]
        low = min_font_size
        high = orig_font_size
        best_size = min_font_size
        best_rc = rc_min
        iteration = 0

        while (high - low) > options.binary_search_epsilon and iteration < options.max_search_iterations:
            mid = (low + high) / 2.0
            text_mid = get_text_for_size(mid)
            rc = _try_textbox(search_rect, text_mid, mid, search_lh)
            if rc >= 0:
                best_size = mid
                best_rc = rc
                low = mid  # text fits; attempt a larger size for better legibility
            else:
                high = mid  # text overflowed; must reduce size
            iteration += 1

        # 4. Verification pass on scratch page
        text_best = get_text_for_size(best_size)
        confirm_rc = _try_textbox(search_rect, text_best, best_size, search_lh)
        if confirm_rc >= 0:
            lines = self._estimate_lines(search_rect.height, confirm_rc, best_size, search_lh)
            return True, best_size, OverflowCause.NONE, max(1, lines), search_lh

        # Fallback to confirmed min_font_size
        lines = self._estimate_lines(search_rect.height, rc_min, min_font_size, search_lh)
        return True, min_font_size, OverflowCause.NONE, max(1, lines), search_lh

    def _estimate_lines(
        self,
        box_height: float,
        rc: float,
        font_size: float,
        lineheight: float,
    ) -> int:
        """Estimate line count from bounding box height and leftover vertical space."""
        used_height = max(0.0, box_height - rc)
        line_height_pt = max(1.0, font_size * lineheight)
        return max(1, round(used_height / line_height_pt))

    def _classify_overflow_cause(
        self,
        text: str,
        box_width: float,
        min_font_size: float,
    ) -> OverflowCause:
        """Classify why text failed to fit within bounds at minimum font floor."""
        try:
            tokens = text.split()
            for token in tokens:
                token_width = self.font_manager.measure_text_length(token, fontsize=min_font_size)
                if token_width > box_width:
                    return OverflowCause.OVERFLOW_WIDTH_AT_MIN_SIZE
            return OverflowCause.OVERFLOW_HEIGHT
        except Exception:
            return OverflowCause.OVERFLOW_UNDETERMINED


def parse_color(color_val: int | str | None) -> tuple[float, float, float]:
    """Parse color into normalized RGB tuple (0.0 to 1.0)."""
    if color_val is None:
        return (0.0, 0.0, 0.0)

    if isinstance(color_val, int):
        r = ((color_val >> 16) & 0xFF) / 255.0
        g = ((color_val >> 8) & 0xFF) / 255.0
        b = (color_val & 0xFF) / 255.0
        return (r, g, b)

    if isinstance(color_val, str):
        c = color_val.strip()
        if c.startswith("#"):
            c = c[1:]
        if len(c) == 6:
            try:
                r = int(c[0:2], 16) / 255.0
                g = int(c[2:4], 16) / 255.0
                b = int(c[4:6], 16) / 255.0
                return (r, g, b)
            except ValueError:
                pass

    return (0.0, 0.0, 0.0)
