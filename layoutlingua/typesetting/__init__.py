"""Typesetting, text clearance, and layout-preserving PDF reflow engine for LayoutLingua."""

from layoutlingua.typesetting.accumulator import DocumentAccumulator
from layoutlingua.typesetting.engine import TypesetEngine
from layoutlingua.typesetting.fonts import FontManager, FontValidationError
from layoutlingua.typesetting.models import (
    BlockFittingDetail,
    BlockFittingStatus,
    CollisionDetail,
    FittingReport,
    OverflowCause,
    PageFittingSummary,
    TypesetOptions,
    TypesetResult,
)
from layoutlingua.typesetting.protection import (
    BlockClearanceDecision,
    ClearancePlan,
    ClearancePlanner,
    ExclusionZone,
    ExclusionZoneType,
    compute_tight_line_clearance_regions,
    is_background_container,
)

__all__ = [
    "BlockClearanceDecision",
    "BlockFittingDetail",
    "BlockFittingStatus",
    "ClearancePlan",
    "ClearancePlanner",
    "CollisionDetail",
    "DocumentAccumulator",
    "ExclusionZone",
    "ExclusionZoneType",
    "FittingReport",
    "FontManager",
    "FontValidationError",
    "OverflowCause",
    "PageFittingSummary",
    "TypesetEngine",
    "TypesetOptions",
    "TypesetResult",
    "compute_tight_line_clearance_regions",
    "is_background_container",
]
