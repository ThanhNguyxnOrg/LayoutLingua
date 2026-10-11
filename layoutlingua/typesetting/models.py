"""Data models and options for typesetting, adaptive font fitting, and telemetry reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockFittingStatus(str, Enum):
    """Execution status of a text block during typesetting."""

    SUCCESS = "success"
    OVERFLOW_FALLBACK = "overflow_fallback"
    SKIPPED_EMPTY = "skipped_empty"
    SKIPPED_FORMULA = "skipped_formula"
    SKIPPED_UNCHANGED = "skipped_unchanged"


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
    bbox: tuple[float, float, float, float]
    reason: str = ""


@dataclass(slots=True)
class FittingReport:
    """Aggregate telemetry report of the typesetting process."""

    total_blocks: int = 0
    replaced_blocks: int = 0
    overflow_blocks: int = 0
    skipped_blocks: int = 0
    details: list[BlockFittingDetail] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Percentage of candidate blocks successfully typeset."""
        candidates = self.replaced_blocks + self.overflow_blocks
        if candidates == 0:
            return 100.0
        return (self.replaced_blocks / candidates) * 100.0


@dataclass(slots=True)
class TypesetOptions:
    """Configuration options for the TypesetEngine.
    
    Default bounds:
    - min_font_scale: 0.70 (down to 70% of original font size)
    - min_font_pt: 6.0 pt minimum readability floor
    - fail_closed: True (preserve source text if translated text does not fit)
    - preserve_background: True (use transparent redactions to retain vector art/images)
    """

    min_font_scale: float = 0.70
    min_font_pt: float = 6.0
    fail_closed: bool = True
    preserve_background: bool = True
    font_name: str = "DejaVuSans"
    step_down_ratio: float = 0.95


@dataclass(slots=True)
class TypesetResult:
    """Final output from TypesetEngine containing the rendered PDF and fitting telemetry."""

    pdf_bytes: bytes
    fitting_report: FittingReport
