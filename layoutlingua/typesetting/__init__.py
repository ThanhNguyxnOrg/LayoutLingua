"""Typesetting, text clearance, and layout-preserving PDF reflow engine for LayoutLingua."""

from layoutlingua.typesetting.engine import TypesetEngine
from layoutlingua.typesetting.fonts import FontManager, FontValidationError
from layoutlingua.typesetting.models import (
    BlockFittingDetail,
    BlockFittingStatus,
    FittingReport,
    OverflowCause,
    PageFittingSummary,
    TypesetOptions,
    TypesetResult,
)

__all__ = [
    "BlockFittingDetail",
    "BlockFittingStatus",
    "FittingReport",
    "FontManager",
    "FontValidationError",
    "OverflowCause",
    "PageFittingSummary",
    "TypesetEngine",
    "TypesetOptions",
    "TypesetResult",
]
