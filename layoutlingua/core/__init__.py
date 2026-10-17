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
from layoutlingua.core.parser import ParserConfig, parse_pdf

__all__ = [
    "CharInfo",
    "DocumentIR",
    "GlyphSpan",
    "LayoutRegion",
    "PageGeometry",
    "PageIR",
    "TextBlock",
    "ParserConfig",
    "parse_pdf",
]
