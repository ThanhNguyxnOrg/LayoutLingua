"""LayoutLingua: High-precision document translation engine preserving layout geometry."""

from layoutlingua._version import __version__
from layoutlingua.core.ir import DocumentIR, GlyphSpan, LayoutRegion, PageGeometry, PageIR, TextBlock
from layoutlingua.core.parser import PDFParseError, parse_pdf
from layoutlingua.ipc import JsonRpcServer
from layoutlingua.translation.mock import MockTranslationProvider
from layoutlingua.typesetting import (
    BlockClearanceDecision,
    BlockFittingDetail,
    BlockFittingStatus,
    ClearancePlan,
    ClearancePlanner,
    CollisionDetail,
    ExclusionZone,
    ExclusionZoneType,
    FittingReport,
    FontManager,
    FontValidationError,
    OverflowCause,
    PageFittingSummary,
    TypesetEngine,
    TypesetOptions,
    TypesetResult,
)

__all__ = [
    "__version__",
    "BlockClearanceDecision",
    "BlockFittingDetail",
    "BlockFittingStatus",
    "ClearancePlan",
    "ClearancePlanner",
    "CollisionDetail",
    "DocumentIR",
    "ExclusionZone",
    "ExclusionZoneType",
    "FittingReport",
    "FontManager",
    "FontValidationError",
    "GlyphSpan",
    "JsonRpcServer",
    "LayoutRegion",
    "MockTranslationProvider",
    "OverflowCause",
    "PDFParseError",
    "PageFittingSummary",
    "PageGeometry",
    "PageIR",
    "TextBlock",
    "TypesetEngine",
    "TypesetOptions",
    "TypesetResult",
    "parse_pdf",
]

