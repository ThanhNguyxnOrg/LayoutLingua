"""Core package for LayoutLingua PDF document layout and intermediate representation."""

from layoutlingua.core.ir import (
    CharInfo,
    DocumentIR,
    GlyphSpan,
    LayoutRegion,
    PageGeometry,
    PageIR,
    TextBlock,
)

__all__ = [
    "CharInfo",
    "DocumentIR",
    "GlyphSpan",
    "LayoutRegion",
    "PageGeometry",
    "PageIR",
    "TextBlock",
]
