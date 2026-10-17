"""High-fidelity PDF document parser using PyMuPDF.

Extracts page geometry, text blocks, glyph/character spans, fonts,
and styling into decoupled DocumentIR data structures.
"""

from __future__ import annotations

import os
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


class PDFParseError(Exception):
    """Raised when a PDF cannot be opened, decrypted, or parsed."""


import logging

logger = logging.getLogger(__name__)


def parse_pdf(
    file_path: str | Path,
    password: str | None = None,
    include_chars: bool = True,
    layout_detector: Any | None = None,
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
                    spans: list[GlyphSpan] = []
                    lines = b.get("lines", [])

                    for line_idx, line in enumerate(lines):
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
                            is_last_line_in_block = (line_idx == len(lines) - 1)
                            if is_last_span_in_line and not is_last_line_in_block:
                                next_starts_with_space = False
                                for ns in lines[line_idx + 1].get("spans", []):
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

                            s_bbox = _sanitize_bbox(s.get("bbox", b_bbox))
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

                            span_id = f"p{page_num}_b{block_idx}_l{line_idx}_s{span_idx}"
                            font_size = float(s.get("size", 10.0))
                            if font_size <= 0:
                                font_size = 10.0

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

                    block_id = f"p{page_num}_block_{block_idx}"
                    text_block = TextBlock(
                        block_id=block_id,
                        bbox=b_bbox,
                        spans=spans,
                        block_type="text",
                    )
                    blocks.append(text_block)

                    # Initial heuristic region from PyMuPDF block
                    regions.append(
                        LayoutRegion(
                            region_id=f"p{page_num}_region_{block_idx}",
                            bbox=b_bbox,
                            category="text",
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
