"""Geometric clustering for lines, fraction-aware grouping, and tabular isolation.

All clustering decisions utilize relative tolerances based on font size and
page metrics rather than fixed absolute thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from layoutlingua.core.ir import GlyphSpan


@dataclass(slots=True)
class ClusteredLine:
    """A horizontally ordered sequence of spans forming a coherent line."""

    line_id: str
    bbox: tuple[float, float, float, float]
    spans: list[GlyphSpan] = field(default_factory=list)
    baseline_y: float = 0.0
    has_fraction: bool = False

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.spans if s.text.strip())


@dataclass(slots=True)
class TabularCell:
    """An isolated cell within a borderless or bordered table structure."""

    row_index: int
    col_index: int
    bbox: tuple[float, float, float, float]
    spans: list[GlyphSpan] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.spans if s.text.strip())


class GeometricGrouper:
    """Groups glyph spans into lines and separates tabular rows/columns."""

    def __init__(
        self,
        line_tolerance_ratio: float = 0.35,
        fraction_tolerance_ratio: float = 0.75,
        gutter_ratio: float = 1.8,
    ) -> None:
        self.line_tolerance_ratio = line_tolerance_ratio
        self.fraction_tolerance_ratio = fraction_tolerance_ratio
        self.gutter_ratio = gutter_ratio

    def cluster_spans_into_lines(self, spans: Sequence[GlyphSpan]) -> list[ClusteredLine]:
        """Group spans into lines using relative vertical tolerance and fraction clustering."""
        if not spans:
            return []

        # Sort spans primarily by vertical origin y, secondarily by x0
        sorted_spans = sorted(spans, key=lambda s: (s.origin[1] if s.origin[1] > 0 else s.bbox[1], s.bbox[0]))

        lines: list[list[GlyphSpan]] = []
        for span in sorted_spans:
            ref_y = span.origin[1] if span.origin[1] > 0 else (span.bbox[1] + span.bbox[3]) / 2.0
            font_size = max(span.font_size, 8.0)

            # Check if this span fits into an existing line
            matched_line: list[GlyphSpan] | None = None
            for line in lines:
                line_avg_y = sum(
                    s.origin[1] if s.origin[1] > 0 else (s.bbox[1] + s.bbox[3]) / 2.0 for s in line
                ) / len(line)
                line_max_size = max(s.font_size for s in line)

                # Relative tolerance scaled to local font size
                effective_tolerance = self.line_tolerance_ratio * max(font_size, line_max_size)

                # Check if span is a fraction component (tolerating larger vertical step if x overlaps)
                is_fraction_candidate = (
                    span.is_math_or_symbol
                    or any(s.is_math_or_symbol for s in line)
                    or "/" in span.text
                    or "_" in span.text
                )
                if is_fraction_candidate:
                    # Check horizontal overlap or close proximity
                    line_x0 = min(s.bbox[0] for s in line)
                    line_x1 = max(s.bbox[2] for s in line)
                    if not (span.bbox[2] < line_x0 - 20.0 or span.bbox[0] > line_x1 + 20.0):
                        effective_tolerance = self.fraction_tolerance_ratio * max(font_size, line_max_size)

                min_dist = min(
                    abs(ref_y - (s.origin[1] if s.origin[1] > 0 else (s.bbox[1] + s.bbox[3]) / 2.0))
                    for s in line
                )
                if min_dist <= effective_tolerance:
                    matched_line = line
                    break

            if matched_line is not None:
                matched_line.append(span)
            else:
                lines.append([span])

        # Convert span lists into ClusteredLine objects, sorted left-to-right by x0
        clustered_lines: list[ClusteredLine] = []
        for idx, span_group in enumerate(lines):
            span_group.sort(key=lambda s: s.bbox[0])
            min_x0 = min(s.bbox[0] for s in span_group)
            min_y0 = min(s.bbox[1] for s in span_group)
            max_x1 = max(s.bbox[2] for s in span_group)
            max_y1 = max(s.bbox[3] for s in span_group)
            avg_origin_y = sum(s.origin[1] for s in span_group) / len(span_group)
            has_fraction = any(
                s.is_math_or_symbol or "/" in s.text or "_" in s.text for s in span_group
            )

            clustered_lines.append(
                ClusteredLine(
                    line_id=f"line_{idx}",
                    bbox=(min_x0, min_y0, max_x1, max_y1),
                    spans=span_group,
                    baseline_y=avg_origin_y,
                    has_fraction=has_fraction,
                )
            )

        # Sort lines vertically from top to bottom
        clustered_lines.sort(key=lambda cl: cl.bbox[1])
        return clustered_lines

    def isolate_tabular_cells(self, spans: Sequence[GlyphSpan]) -> list[TabularCell]:
        """Detect tabular structure and isolate cells using horizontal back-jumps and gutters."""
        if not spans:
            return []

        # Sort spans primarily by y, then by x
        sorted_spans = sorted(spans, key=lambda s: (s.bbox[1], s.bbox[0]))
        cells: list[TabularCell] = []

        # Identify horizontal column gutters across the span set
        x_positions = sorted(s.bbox[0] for s in sorted_spans)
        avg_font_size = sum(s.font_size for s in sorted_spans) / len(sorted_spans)
        gutter_threshold = self.gutter_ratio * max(avg_font_size, 8.0)

        # Build column bounds by clustering x0 positions
        col_boundaries: list[float] = []
        for x in x_positions:
            if not col_boundaries or (x - col_boundaries[-1]) > gutter_threshold:
                col_boundaries.append(x)

        # Group spans into rows and columns
        current_row = 0
        last_x0 = -1.0
        row_spans: list[GlyphSpan] = []

        for span in sorted_spans:
            x0 = span.bbox[0]
            # Significant horizontal back-jump indicates a new table row
            if last_x0 >= 0 and (x0 < last_x0 - gutter_threshold):
                current_row += 1

            # Match column index based on closest column boundary
            col_idx = 0
            for i, boundary in enumerate(col_boundaries):
                if x0 >= boundary - 5.0:
                    col_idx = i

            cells.append(
                TabularCell(
                    row_index=current_row,
                    col_index=col_idx,
                    bbox=span.bbox,
                    spans=[span],
                )
            )
            last_x0 = x0

        return cells
