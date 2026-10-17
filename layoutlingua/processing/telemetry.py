"""Telemetry and progress tracking for the document translation pipeline.

Provides monotonic progression, exponential moving average (EMA) rate smoothing,
and whole-pipeline ETA estimation with realistic priors.
"""

from __future__ import annotations

import time
from typing import Any


class ExponentialMovingAverage:
    """Exponential moving average with bias correction for rate smoothing.

    Derived from standard EMA implementations (e.g. tqdm / PyTorch).
    """

    def __init__(self, smoothing: float = 0.25, initial_rate: float | None = None):
        self.alpha = max(0.01, min(1.0, smoothing))
        self.initial_rate = float(initial_rate) if initial_rate is not None else 0.0
        self.last: float = self.initial_rate
        self.calls: int = 0

    def update(self, sample: float) -> float:
        """Record a new observation and return the updated smoothed average."""
        beta = 1.0 - self.alpha
        if self.calls == 0 and self.initial_rate <= 0:
            self.last = sample
        else:
            self.last = self.alpha * sample + beta * self.last
        self.calls += 1
        return self.value

    @property
    def value(self) -> float:
        """Return the current smoothed value."""
        if self.calls == 0:
            return self.initial_rate
        if self.initial_rate > 0:
            return self.last
        beta = 1.0 - self.alpha
        denom = 1.0 - (beta**self.calls)
        return self.last / denom if denom > 1e-6 else self.last


class PipelineProgressTracker:
    """Tracks multi-stage translation pipeline progress and calculates holistic ETA.

    Pipeline stages:
      - 0: Reading document structure (0% - 2%)
      - 1: Detecting tables and formulas (2% - 5%)
      - 2: Translating text blocks (5% - 55%)
      - 3: Fitting text to layout (55% - 95%)
      - 4: Writing output PDF (95% - 100%)
    """

    # Stage percentage boundaries
    STAGE_BOUNDS = {
        0: (0, 2),
        1: (2, 5),
        2: (5, 55),
        3: (55, 95),
        4: (95, 100),
    }

    # Realistic fallback baseline priors (seconds per unit)
    PRIOR_SEC_PER_SEGMENT = 0.06  # ~16 segments/sec across concurrent workers
    PRIOR_SEC_PER_PAGE_TYPESET = 0.25  # ~4 pages/sec typeset baseline
    PRIOR_SEC_WRITE_PDF = 1.0

    def __init__(self, total_pages: int, total_segments: int = 0):
        self.total_pages = max(1, total_pages)
        self.total_segments = max(0, total_segments)
        self.stage_index = 0
        self.current_page = 0
        self.segments_done = 0

        self.pipeline_start_time = time.time()
        self.stage_start_time = time.time()
        self.last_item_time = time.time()

        # Initialize EMAs with realistic priors
        init_seg_rate = 1.0 / self.PRIOR_SEC_PER_SEGMENT
        init_page_rate = 1.0 / self.PRIOR_SEC_PER_PAGE_TYPESET
        self.trans_rate_ema = ExponentialMovingAverage(smoothing=0.25, initial_rate=init_seg_rate)
        self.typeset_rate_ema = ExponentialMovingAverage(smoothing=0.25, initial_rate=init_page_rate)

        self._last_calc_eta: int = int(
            (self.total_segments * self.PRIOR_SEC_PER_SEGMENT)
            + (self.total_pages * self.PRIOR_SEC_PER_PAGE_TYPESET)
            + self.PRIOR_SEC_WRITE_PDF
        )

    def set_stage(self, stage_index: int, message: str = "") -> dict[str, Any]:
        """Transition pipeline to a new stage."""
        self.stage_index = stage_index
        self.stage_start_time = time.time()
        self.last_item_time = time.time()
        return self.snapshot(message=message)

    def update_translation(self, done_segments: int, total_segments: int | None = None) -> dict[str, Any]:
        """Record translation progress (Stage 2)."""
        now = time.time()
        if total_segments is not None:
            self.total_segments = max(1, total_segments)

        prev_done = self.segments_done
        self.segments_done = min(self.total_segments, max(0, done_segments))
        delta_segs = self.segments_done - prev_done
        delta_time = max(0.01, now - self.last_item_time)

        if delta_segs > 0:
            instant_rate = delta_segs / delta_time
            self.trans_rate_ema.update(instant_rate)
            self.last_item_time = now

        # In stage 2, calculate proportional page for integrity context
        ratio = self.segments_done / max(1, self.total_segments)
        self.current_page = max(1, min(self.total_pages, int(ratio * self.total_pages)))

        return self.snapshot(
            message=f"Translating text blocks ({self.segments_done}/{self.total_segments} segments)..."
        )

    def update_typesetting(self, done_pages: int) -> dict[str, Any]:
        """Record typesetting progress (Stage 3)."""
        now = time.time()
        prev_pages = self.current_page
        self.current_page = min(self.total_pages, max(1, done_pages))
        delta_pages = self.current_page - prev_pages
        delta_time = max(0.01, now - self.last_item_time)

        if delta_pages > 0:
            instant_rate = delta_pages / delta_time
            # Cap extreme instant rates (e.g. from completely blank pages) to avoid skewing EMA
            capped_rate = min(instant_rate, 25.0)
            self.typeset_rate_ema.update(capped_rate)
            self.last_item_time = now

        return self.snapshot(
            message=f"Fitting text to layout for page {self.current_page} of {self.total_pages}..."
        )

    def calculate_eta(self) -> int:
        """Calculate whole-pipeline remaining seconds smoothly."""
        if self.stage_index >= 4:
            return 1 if self.stage_index == 4 else 0

        rem_time: float = 0.0

        if self.stage_index <= 2:
            # Remaining in Stage 2
            rem_segs = max(0, self.total_segments - self.segments_done)
            seg_rate = max(1.0, self.trans_rate_ema.value)
            rem_time += rem_segs / seg_rate

            # Upcoming Stage 3
            page_rate = max(0.5, self.typeset_rate_ema.value)
            rem_time += self.total_pages / page_rate

            # Upcoming Stage 4
            rem_time += self.PRIOR_SEC_WRITE_PDF

        elif self.stage_index == 3:
            # Remaining in Stage 3
            rem_pages = max(0, self.total_pages - self.current_page)
            # Use typeset rate with realistic upper bound on speed (max 12 p/s)
            page_rate = max(0.5, min(12.0, self.typeset_rate_ema.value))
            rem_time += rem_pages / page_rate

            # Upcoming Stage 4
            rem_time += self.PRIOR_SEC_WRITE_PDF

        raw_eta = max(1, int(round(rem_time)))

        # Dampen drastic jumps: prevent ETA from swinging wildly in one step
        if abs(raw_eta - self._last_calc_eta) > 8:
            smoothed_eta = int(0.35 * raw_eta + 0.65 * self._last_calc_eta)
        else:
            smoothed_eta = raw_eta

        self._last_calc_eta = smoothed_eta
        return smoothed_eta

    def calculate_overall_pct(self) -> int:
        """Calculate monotonic overall progress percentage (0-100%)."""
        start_pct, end_pct = self.STAGE_BOUNDS.get(self.stage_index, (0, 100))
        span = end_pct - start_pct

        if self.stage_index == 2:
            ratio = self.segments_done / max(1, self.total_segments)
            return min(end_pct, start_pct + int(ratio * span))
        elif self.stage_index == 3:
            ratio = self.current_page / max(1, self.total_pages)
            return min(end_pct, start_pct + int(ratio * span))
        elif self.stage_index == 4:
            return 97
        elif self.stage_index > 4:
            return 100

        return start_pct

    def snapshot(
        self,
        message: str = "",
        integrity: dict[str, Any] | None = None,
        status: str = "processing",
    ) -> dict[str, Any]:
        """Generate a complete progress snapshot dictionary."""
        overall_pct = self.calculate_overall_pct()
        eta = self.calculate_eta()

        if self.stage_index == 2:
            speed = round(self.trans_rate_ema.value, 1)
            speed_unit = "seg/s"
            subtitle = f"segment {self.segments_done} of {self.total_segments}"
        elif self.stage_index == 3:
            speed = round(self.typeset_rate_ema.value, 1)
            speed_unit = "p/s"
            subtitle = f"page {self.current_page} of {self.total_pages}"
        elif self.stage_index == 4:
            speed = 1.0
            speed_unit = "p/s"
            subtitle = "saving PDF"
        else:
            speed = 0.0
            speed_unit = "p/s"
            subtitle = f"page {self.current_page} of {self.total_pages}"

        snap: dict[str, Any] = {
            "stage_index": self.stage_index,
            "stage_name": [
                "Reading document structure",
                "Detecting tables and formulas",
                "Translating text blocks",
                "Fitting text to layout",
                "Writing output PDF",
            ][min(4, self.stage_index)],
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "segments_done": self.segments_done,
            "segments_total": self.total_segments,
            "overall_pct": overall_pct,
            "status": status,
            "speed": speed,
            "speed_unit": speed_unit,
            "eta_seconds": eta,
            "message": message or f"Processing stage {self.stage_index + 1}...",
            "subtitle": subtitle,
        }

        if integrity is not None:
            snap["integrity"] = integrity

        return snap
