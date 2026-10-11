"""Data models, configuration options, and multi-tier telemetry for typesetting and fitting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockFittingStatus(str, Enum):
    """Execution status of a text block during typesetting."""

    SUCCESS = "success"
    OVERFLOW_FALLBACK = "overflow_fallback"
    COLLISION_FALLBACK = "collision_fallback"
    SKIPPED_EMPTY = "skipped_empty"
    SKIPPED_FORMULA = "skipped_formula"
    SKIPPED_UNCHANGED = "skipped_unchanged"
    SKIPPED_UNSUPPORTED = "skipped_unsupported"


class OverflowCause(str, Enum):
    """Classified root cause when a translated block fails to fit within bounds."""

    NONE = "none"
    OVERFLOW_HEIGHT = "overflow_height"
    OVERFLOW_WIDTH_AT_MIN_SIZE = "overflow_width_at_min_size"
    OVERFLOW_UNDETERMINED = "overflow_undetermined"


@dataclass(frozen=True)
class CollisionDetail:
    """Structured telemetry data describing a geometric collision event."""

    collision_type: str  # "FORMULA", "ADJACENT_TEXT", "IMAGE", "VECTOR_ART", "UNKNOWN"
    protected_object_id: str | None
    bbox: tuple[float, float, float, float]
    confidence: float | None = None
    description: str = ""


@dataclass(slots=True)
class BlockFittingDetail:
    """Detailed telemetry record for an individual layout block."""

    block_id: str
    page_number: int
    status: BlockFittingStatus
    original_text: str
    translated_text: str
    original_font_size: float
    final_font_size: float
    shrink_ratio: float = 1.0
    line_height_em: float = 1.20
    line_count: int = 1
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    overflow_cause: OverflowCause = OverflowCause.NONE
    collision_detail: CollisionDetail | None = None
    reason: str = ""


@dataclass(slots=True)
class PageFittingSummary:
    """Aggregated typesetting metrics for a single document page."""

    page_number: int
    total_blocks: int = 0
    replaced_blocks: int = 0
    overflow_blocks: int = 0
    collision_blocks: int = 0
    skipped_blocks: int = 0
    avg_shrink_ratio: float = 1.0
    worst_shrink_ratio: float = 1.0
    has_severe_shrink_warning: bool = False
    line_count_delta: int = 0


@dataclass(slots=True)
class FittingReport:
    """Document-wide and page-stratified aggregate telemetry report."""

    total_blocks: int = 0
    replaced_blocks: int = 0
    overflow_blocks: int = 0
    collision_blocks: int = 0
    skipped_blocks: int = 0
    avg_shrink_ratio: float = 1.0
    worst_shrink_ratio: float = 1.0
    severe_shrink_blocks_count: int = 0
    line_count_delta: int = 0
    pages: list[PageFittingSummary] = field(default_factory=list)
    details: list[BlockFittingDetail] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Percentage of candidate blocks successfully typeset."""
        candidates = self.replaced_blocks + self.overflow_blocks + self.collision_blocks
        if candidates == 0:
            return 100.0
        return (self.replaced_blocks / candidates) * 100.0


@dataclass(slots=True)
class TypesetOptions:
    """Configuration options for the TypesetEngine and binary search fitting."""

    min_font_scale: float = 0.70
    min_font_pt: float = 6.0
    fail_closed: bool = True
    preserve_background: bool = True
    font_name: str = "DejaVuSans"
    binary_search_epsilon: float = 0.2
    max_search_iterations: int = 7
    base_lineheight_ratio: float = 1.20
    safety_padding_em: float = 0.03
    severe_shrink_threshold: float = 0.75
    step_down_ratio: float = 0.95
    clearance_padding_pt: float = 0.5


@dataclass(slots=True)
class TypesetResult:
    """Final output from TypesetEngine containing the rendered PDF and fitting telemetry."""

    pdf_bytes: bytes
    fitting_report: FittingReport
