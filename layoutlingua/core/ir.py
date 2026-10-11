"""Intermediate Representation (IR) for LayoutLingua.

This module defines decoupled, pure-Python data structures representing
the visual geometry, text spans, layout regions, and document hierarchy.
No PyMuPDF objects (Rect, Page, Document) are stored directly to guarantee
clean JSON serialization and platform independence.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

# Coordinate Convention:
# - Origin (0, 0): Top-Left corner of the page.
# - Unit: Standard typography points (1 pt = 1/72 inch).
# - Axes: X increases rightward, Y increases downward.
# - BBox format: (x0, y0, x1, y1) where x0 <= x1 and y0 <= y1.


@dataclass(slots=True)
class PageGeometry:
    """Dimensions and coordinate conventions of a document page."""

    width: float
    height: float
    rotation: int = 0  # 0, 90, 180, 270
    unit: str = "pt"
    coordinate_origin: str = "top-left"

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Page dimensions must be positive: ({self.width}, {self.height})")
        if self.rotation not in (0, 90, 180, 270):
            raise ValueError(f"Invalid page rotation: {self.rotation}. Must be 0, 90, 180, or 270.")


@dataclass(slots=True)
class CharInfo:
    """Character-level coordinate and geometry details within a span."""

    char: str
    bbox: tuple[float, float, float, float]
    origin: tuple[float, float]

    def __post_init__(self) -> None:
        _validate_bbox(self.bbox)


@dataclass(slots=True)
class GlyphSpan:
    """A contiguous run of text with uniform font, size, and styling properties."""

    span_id: str
    text: str
    bbox: tuple[float, float, float, float]
    font_name: str
    font_size: float
    color: int | str  # sRGB int or hex '#RRGGBB'
    flags: int = 0  # Bit flags for bold, italic, serif, etc.
    origin: tuple[float, float] = (0.0, 0.0)
    chars: list[CharInfo] = field(default_factory=list)
    is_math_or_symbol: bool = False

    def __post_init__(self) -> None:
        _validate_bbox(self.bbox)
        if self.font_size <= 0:
            raise ValueError(f"Font size must be positive, got {self.font_size}")


@dataclass(slots=True)
class TextBlock:
    """A structural block grouping text spans that belong to a single paragraph or element."""

    block_id: str
    bbox: tuple[float, float, float, float]
    spans: list[GlyphSpan] = field(default_factory=list)
    block_type: str = "text"  # "text", "table", "formula", "header", "footer"

    def __post_init__(self) -> None:
        _validate_bbox(self.bbox)

    @property
    def text(self) -> str:
        """Concatenated text of all constituent spans."""
        return "".join(span.text for span in self.spans)


@dataclass(slots=True)
class LayoutRegion:
    """A detected semantic spatial segment on a document page."""

    region_id: str
    bbox: tuple[float, float, float, float]
    category: str  # "text", "title", "figure", "table", "formula", "header", "footer", "abandon"
    confidence: float = 1.0
    source: str = "pymupdf"  # Extensible: "pymupdf", "doclayout_yolo", "heuristic"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_bbox(self.bbox)
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass(slots=True)
class PageIR:
    """Complete geometric and textual intermediate representation of one page."""

    page_number: int  # 1-indexed
    geometry: PageGeometry
    blocks: list[TextBlock] = field(default_factory=list)
    regions: list[LayoutRegion] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError(f"Page number must be >= 1, got {self.page_number}")


@dataclass(slots=True)
class DocumentIR:
    """Full document Intermediate Representation container."""

    doc_id: str
    filename: str
    page_count: int
    pages: list[PageIR] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.page_count < 0:
            raise ValueError(f"Page count cannot be negative, got {self.page_count}")

    def to_dict(self) -> dict[str, Any]:
        """Convert DocumentIR into a JSON-serializable Python dictionary."""
        return asdict(self)

    def to_json(self, indent: int | None = None) -> str:
        """Serialize DocumentIR into a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentIR:
        """Construct a DocumentIR instance from a dictionary."""
        pages: list[PageIR] = []
        for p in data.get("pages", []):
            geom_data = p["geometry"]
            geometry = PageGeometry(
                width=float(geom_data["width"]),
                height=float(geom_data["height"]),
                rotation=int(geom_data.get("rotation", 0)),
                unit=str(geom_data.get("unit", "pt")),
                coordinate_origin=str(geom_data.get("coordinate_origin", "top-left")),
            )

            blocks: list[TextBlock] = []
            for b in p.get("blocks", []):
                spans: list[GlyphSpan] = []
                for s in b.get("spans", []):
                    chars: list[CharInfo] = []
                    for c in s.get("chars", []):
                        chars.append(
                            CharInfo(
                                char=str(c["char"]),
                                bbox=_parse_bbox(c["bbox"]),
                                origin=(float(c["origin"][0]), float(c["origin"][1])),
                            )
                        )
                    spans.append(
                        GlyphSpan(
                            span_id=str(s["span_id"]),
                            text=str(s["text"]),
                            bbox=_parse_bbox(s["bbox"]),
                            font_name=str(s["font_name"]),
                            font_size=float(s["font_size"]),
                            color=s["color"],
                            flags=int(s.get("flags", 0)),
                            origin=(float(s.get("origin", (0, 0))[0]), float(s.get("origin", (0, 0))[1])),
                            chars=chars,
                            is_math_or_symbol=bool(s.get("is_math_or_symbol", False)),
                        )
                    )
                blocks.append(
                    TextBlock(
                        block_id=str(b["block_id"]),
                        bbox=_parse_bbox(b["bbox"]),
                        spans=spans,
                        block_type=str(b.get("block_type", "text")),
                    )
                )

            regions: list[LayoutRegion] = []
            for r in p.get("regions", []):
                regions.append(
                    LayoutRegion(
                        region_id=str(r["region_id"]),
                        bbox=_parse_bbox(r["bbox"]),
                        category=str(r["category"]),
                        confidence=float(r.get("confidence", 1.0)),
                        source=str(r.get("source", "pymupdf")),
                        metadata=dict(r.get("metadata", {})),
                    )
                )

            pages.append(
                PageIR(
                    page_number=int(p["page_number"]),
                    geometry=geometry,
                    blocks=blocks,
                    regions=regions,
                    metadata=dict(p.get("metadata", {})),
                )
            )

        return cls(
            doc_id=str(data["doc_id"]),
            filename=str(data["filename"]),
            page_count=int(data["page_count"]),
            pages=pages,
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def from_json(cls, json_str: str) -> DocumentIR:
        """Construct a DocumentIR instance from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


def _validate_bbox(bbox: tuple[float, float, float, float]) -> None:
    if len(bbox) != 4:
        raise ValueError(f"BBox must contain exactly 4 coordinates, got {bbox}")
    x0, y0, x1, y1 = bbox
    if x0 > x1 or y0 > y1:
        raise ValueError(f"Invalid BBox bounds: ({x0}, {y0}, {x1}, {y1}) requires x0 <= x1 and y0 <= y1")


def _parse_bbox(bbox_data: Any) -> tuple[float, float, float, float]:
    if not isinstance(bbox_data, (list, tuple)) or len(bbox_data) != 4:
        raise ValueError(f"Expected 4-element sequence for bbox, got {bbox_data}")
    return (float(bbox_data[0]), float(bbox_data[1]), float(bbox_data[2]), float(bbox_data[3]))
