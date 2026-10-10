"""Canonical Semantic Document Intermediate Representation (Document IR) for LayoutLingua.

Decouples visual PDF extraction, document-level semantics, translation middleware,
and adaptive typesetting. Inspired by BabelDOC (ACL 2026), Docling, and GROBID.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SemanticRole(str, Enum):
    """Semantic role of a document region or paragraph."""
    UNKNOWN = "unknown"
    TITLE = "title"
    HEADING = "heading"
    PROSE = "prose"
    LIST_ITEM = "list_item"
    FORMULA = "formula"
    INLINE_FORMULA = "inline_formula"
    TABLE = "table"
    CELL = "cell"
    FIGURE = "figure"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"
    CODE = "code"


@dataclass
class RunIR:
    """Atomic text run sharing the same font, size, and style attributes."""
    text: str
    font_name: str = ""
    font_size: float = 0.0
    color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    style: int = 0  # 0: Regular, 1: Bold, 2: Italic, 3: BoldItalic
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    is_formula: bool = False
    formula_id: Optional[int] = None
    cid: Optional[int] = None
    graphic_instruction: str = ""


@dataclass
class ParagraphIR:
    """Logical paragraph composed of one or more runs."""
    id: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    runs: List[RunIR] = field(default_factory=list)
    semantic_role: SemanticRole = SemanticRole.PROSE
    source_text: str = ""
    translated_text: Optional[str] = None
    font_name: str = ""
    font_size: float = 10.0
    orientation: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 1.0)
    anchor: Tuple[float, float] = (0.0, 0.0)
    formula_placeholders: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    is_translatable: bool = True
    target_bounds: Optional[Tuple[float, float, float, float]] = None
    fitted_font_size: Optional[float] = None
    fitted_line_offsets: Optional[List[Tuple[float, float]]] = None


@dataclass
class CellIR:
    """Individual table cell containing local paragraphs and geometric boundaries."""
    id: str
    row_idx: int
    col_idx: int
    bbox: Tuple[float, float, float, float]
    row_span: int = 1
    col_span: int = 1
    paragraphs: List[ParagraphIR] = field(default_factory=list)
    is_header: bool = False
    background_color: Optional[Tuple[float, float, float]] = None


@dataclass
class TableIR:
    """Structure-aware table containing cells and grid metadata."""
    id: str
    bbox: Tuple[float, float, float, float]
    rows: int
    cols: int
    cells: List[CellIR] = field(default_factory=list)
    has_grid: bool = True
    confidence: float = 1.0


@dataclass
class FormulaIR:
    """Mathematical expression preserved at native operator level."""
    id: str
    bbox: Tuple[float, float, float, float]
    is_inline: bool = False
    placeholder_token: str = ""
    source_operators: List[str] = field(default_factory=list)
    anchor_point: Tuple[float, float] = (0.0, 0.0)


@dataclass
class PageIR:
    """Intermediate representation of a single PDF page."""
    page_number: int
    width: float
    height: float
    rotation: int = 0
    paragraphs: List[ParagraphIR] = field(default_factory=list)
    tables: List[TableIR] = field(default_factory=list)
    formulas: List[FormulaIR] = field(default_factory=list)
    reading_order: List[str] = field(default_factory=list)  # IDs in topological order
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentIR:
    """Root canonical representation of an entire document."""
    schema_version: str = "1.0.0"
    pages: List[PageIR] = field(default_factory=list)
    global_glossary: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize DocumentIR to a standard dictionary."""
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Export lossless JSON representation."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentIR:
        """Reconstruct DocumentIR from a dictionary."""
        doc = cls(
            schema_version=data.get("schema_version", "1.0.0"),
            global_glossary=data.get("global_glossary", {}),
            metadata=data.get("metadata", {}),
        )
        for page_dict in data.get("pages", []):
            page = PageIR(
                page_number=page_dict["page_number"],
                width=page_dict["width"],
                height=page_dict["height"],
                rotation=page_dict.get("rotation", 0),
                reading_order=page_dict.get("reading_order", []),
                metadata=page_dict.get("metadata", {}),
            )
            for p in page_dict.get("paragraphs", []):
                para = ParagraphIR(
                    id=p["id"],
                    bbox=tuple(p["bbox"]),
                    semantic_role=SemanticRole(p.get("semantic_role", "prose")),
                    source_text=p.get("source_text", ""),
                    translated_text=p.get("translated_text"),
                    font_name=p.get("font_name", ""),
                    font_size=p.get("font_size", 10.0),
                    orientation=tuple(p.get("orientation", (1.0, 0.0, 0.0, 1.0))),
                    anchor=tuple(p.get("anchor", (0.0, 0.0))),
                    formula_placeholders=p.get("formula_placeholders", {}),
                    confidence=p.get("confidence", 1.0),
                    is_translatable=p.get("is_translatable", True),
                )
                for r in p.get("runs", []):
                    run = RunIR(
                        text=r["text"],
                        font_name=r.get("font_name", ""),
                        font_size=r.get("font_size", 0.0),
                        color=tuple(r.get("color", (0.0, 0.0, 0.0))),
                        style=r.get("style", 0),
                        bbox=tuple(r.get("bbox", (0.0, 0.0, 0.0, 0.0))),
                        is_formula=r.get("is_formula", False),
                        formula_id=r.get("formula_id"),
                        cid=r.get("cid"),
                        graphic_instruction=r.get("graphic_instruction", ""),
                    )
                    para.runs.append(run)
                page.paragraphs.append(para)
            doc.pages.append(page)
        return doc
