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
    "sin", "cos", "tan", "cot", "sec", "csc",
    "arcsin", "arccos", "arctan", "arccot",
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
    r"(CM[^R]|AMS|MS.M|XY|MT|BL|RM|EU|LA|RS|LINE|LCIRCLE|TeX-|rsfs|txsy|wasy|stmary|.*Mono|.*Code|.*Ital|.*Sym|.*Math)",
    re.IGNORECASE,
)

# Standard international mathematical functions pattern
MATH_FUNC_PATTERN = re.compile(
    r"\b(?:" + "|".join(sorted(_ISO_MATH_FUNCTIONS, key=len, reverse=True)) + r")\b",
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


def _extract_prose_tokens(text: str) -> list[str]:
    """Extract natural language prose words (language-agnostic across all Unicode scripts).

    A prose word consists of consecutive Unicode alphabetic letters >= 3 chars
    that are NOT international mathematical function names.
    """
    # Strip superscripts, subscripts, fractions, degree marks, and mathematical symbols
    t_clean = re.sub(
        r"[\u00b0-\u00be\u2070-\u209f\u0370-\u03ff\u2100-\u22ff=≈≤≥<>±∓∫∑∏√°′″^_\-+*/÷%|~¬∂∇∅∈∉∋∩∪⊂⊃⊆⊇⊕⊗⊥∠≠≡!\\…∗;()\[\]{}|^_~:,]",
        " ",
        text,
    )
    # Strip standard ISO math functions
    t_clean = MATH_FUNC_PATTERN.sub(" ", t_clean)
    raw_tokens = re.findall(r"\b[^\W\d_]{3,}\b", t_clean, re.UNICODE)
    return [t for t in raw_tokens if t.lower() not in _ISO_MATH_FUNCTIONS]


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

    # 1. Font metadata check: if all meaningful spans use recognized math/formula/symbol fonts
    if all(s.is_math_or_symbol or bool(config.formula_font_pattern.search(s.font_name)) for s in meaningful_spans):
        return True

    # 2. Structural equation & token analysis
    has_rel = bool(MATH_RELATION_PATTERN.search(full_text))
    math_density, math_sym_count, prose_count = _compute_math_metrics(full_text, spans)

    # Pure equation with mathematical relation and zero prose words
    if has_rel and prose_count == 0:
        return True

    # Equation with relation operator and at most 1 short non-prose variable cluster (e.g. S = abc / 4R = pr)
    prose_tokens = _extract_prose_tokens(full_text)
    if has_rel and len(prose_tokens) <= 1 and math_sym_count >= 2 and all(len(w) <= 3 for w in prose_tokens):
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
        if tokens and all(len(t) <= 2 or t.isdigit() or t.startswith(".") for t in tokens):
            return True

    return False


def _is_raw_line_math(line: dict, config: ParserConfig = ParserConfig()) -> bool:
    """Check if an individual line within a raw text block is purely mathematical/symbolic."""
    l_spans = line.get("spans", [])
    meaningful = [
        s for s in l_spans
        if (s.get("text") or ("".join(c.get("c", "") for c in s.get("chars", [])) if "chars" in s else "")).strip()
    ]
    if not meaningful:
        return False
    if all(bool(config.formula_font_pattern.search(s.get("font", ""))) for s in meaningful):
        return True
    from layoutlingua.processing.text_sanitizer import sanitize_extracted_text

    full_text = "".join(
        sanitize_extracted_text(s.get("text") or ("".join(c.get("c", "") for c in s.get("chars", [])) if "chars" in s else ""))
        for s in meaningful
    ).strip()

    prose_tokens = _extract_prose_tokens(full_text)
    if prose_tokens:
        return False

    has_rel = bool(MATH_RELATION_PATTERN.search(full_text))
    words = re.findall(r"\b[^\W\d_]+\b", full_text, re.UNICODE)
    return has_rel or len(words) == 0


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

            for block_idx, b in enumerate(raw_blocks):
                block_type = b.get("type", 0)
                raw_bbox = b.get("bbox", (0.0, 0.0, 0.0, 0.0))
                b_bbox = _sanitize_bbox(raw_bbox)

                # Type 0: Text Block
                if block_type == 0:
                    lines = b.get("lines", [])

                    # Sort spans in each line left-to-right (x0) to restore reading order
                    for line in lines:
                        l_spans = line.get("spans", [])
                        l_spans.sort(key=lambda s: s.get("bbox", (0.0, 0.0, 0.0, 0.0))[0])

                    # Group lines with matching predominant colors and matching math/prose modality
                    line_color_groups: list[list[dict]] = []
                    curr_state = None
                    curr_lines: list[dict] = []

                    # Only split by math modality if the raw block is tall enough to contain multi-line formulas + separate headings
                    split_by_math = (b_bbox[3] - b_bbox[1] > config.min_block_height_for_split_pt)

                    for line in lines:
                        l_spans = line.get("spans", [])
                        predom_c = None
                        for s in l_spans:
                            txt = s.get("text") or ("".join(c.get("c", "") for c in s.get("chars", [])) if "chars" in s else "")
                            if txt.strip():
                                predom_c = s.get("color", 0)
                                break
                        if predom_c is None and l_spans:
                            predom_c = l_spans[0].get("color", 0)

                        line_math = _is_raw_line_math(line, config=config) if split_by_math else False
                        state = (predom_c, line_math)

                        # Disjoint column check: do not merge lines across large horizontal gutters
                        col_break = False
                        if curr_lines:
                            g_x0 = min(l.get("bbox", (0.0, 0.0, 0.0, 0.0))[0] for l in curr_lines)
                            g_x1 = max(l.get("bbox", (0.0, 0.0, 0.0, 0.0))[2] for l in curr_lines)
                            l_x0 = line.get("bbox", (0.0, 0.0, 0.0, 0.0))[0]
                            l_x1 = line.get("bbox", (0.0, 0.0, 0.0, 0.0))[2]
                            if (l_x1 < g_x0 - 15.0) or (l_x0 > g_x1 + 15.0):
                                col_break = True

                        if (curr_state is None or state == curr_state) and not col_break:
                            curr_state = state
                            curr_lines.append(line)
                        else:
                            line_color_groups.append(curr_lines)
                            curr_lines = [line]
                            curr_state = state

                    if curr_lines:
                        line_color_groups.append(curr_lines)

                    for sub_idx, sub_lines in enumerate(line_color_groups):
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

                        suffix = f"_{sub_idx}" if len(line_color_groups) > 1 else ""
                        block_id = f"p{page_num}_block_{block_idx}{suffix}"
                        is_formula = _is_pure_formula_block(spans, config=config)
                        text_block = TextBlock(
                            block_id=block_id,
                            bbox=sub_bbox,
                            spans=spans,
                            block_type="formula" if is_formula else "text",
                        )
                        blocks.append(text_block)

                        # Initial heuristic region from PyMuPDF block
                        regions.append(
                            LayoutRegion(
                                region_id=f"p{page_num}_region_{block_idx}{suffix}",
                                bbox=sub_bbox,
                                category="formula" if is_formula else "text",
                                confidence=1.0,
                                source="pymupdf",
                                metadata={"span_count": len(spans)},
                            )
                        )

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

            pages.append(
                PageIR(
                    page_number=page_num,
                    geometry=geometry,
                    blocks=blocks,
                    regions=regions,
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
