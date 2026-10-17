"""Clean Markdown extraction and export from DocumentIR and translated segments."""

from __future__ import annotations

import re
from layoutlingua.core.ir import DocumentIR


def export_document_markdown(
    doc_ir: DocumentIR,
    translated_segments: dict[str, str] | None = None,
) -> str:
    """Export document contents as clean, structured Markdown.

    Preserves headings (based on font size hierarchy), paragraphs, and mathematical equations.
    """
    segments = translated_segments or {}
    lines: list[str] = []

    from layoutlingua.processing.reading_order import sort_blocks_reading_order

    for page in doc_ir.pages:
        lines.append(f"<!-- Page {page.page_number} -->\n")
        page_w = page.geometry.width if hasattr(page, "geometry") and page.geometry else 595.0
        sorted_blocks = sort_blocks_reading_order(page.blocks, page_width=page_w)

        for block in sorted_blocks:
            # Mathematical display equation
            if block.block_type == "formula":
                eq_text = block.text.strip()
                if eq_text:
                    lines.append(f"\n\n{eq_text}\n\n")
                continue

            # Resolve text (translated if present, else original)
            block_text = segments.get(block.block_id) or block.text
            clean_text = block_text.strip()
            if not clean_text:
                continue

            max_font_size = max((s.font_size for s in block.spans), default=10.0) if block.spans else 10.0
            is_bold = any(s.flags & 2 or "bold" in (s.font_name or "").lower() for s in block.spans) if block.spans else False

            # Heading hierarchy detection
            if max_font_size >= 18.0:
                lines.append(f"\n# {clean_text}\n")
            elif max_font_size >= 14.0 or (max_font_size >= 12.5 and is_bold):
                lines.append(f"\n## {clean_text}\n")
            elif max_font_size >= 11.5 and is_bold:
                lines.append(f"\n### {clean_text}\n")
            else:
                lines.append(f"{clean_text}\n")

        lines.append("\n---\n")

    return "\n".join(lines)