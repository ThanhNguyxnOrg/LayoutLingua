"""LayoutLingua: High-precision document translation engine preserving layout geometry."""

from layoutlingua._version import __version__
from layoutlingua.core.ir import DocumentIR, GlyphSpan, LayoutRegion, PageGeometry, PageIR, TextBlock
from layoutlingua.core.parser import PDFParseError, parse_pdf
from layoutlingua.ipc import JsonRpcServer
from layoutlingua.translation.mock import MockTranslationProvider

__all__ = [
    "__version__",
    "DocumentIR",
    "GlyphSpan",
    "LayoutRegion",
    "PageGeometry",
    "PageIR",
    "TextBlock",
    "PDFParseError",
    "parse_pdf",
    "JsonRpcServer",
    "MockTranslationProvider",
]
