"""Structural protection, exclusion zones, and pre-computed clearance planning.

Ensures that text clearance and replacement never corrupt formulas, adjacent text glyphs,
embedded images, or non-container vector drawings. All decisions are planned on the
pristine, unmodified page geometry before any redactions are applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pymupdf

from layoutlingua.core.ir import PageIR, TextBlock
from layoutlingua.typesetting.models import CollisionDetail


class ExclusionZoneType(str, Enum):
    """Categorized source of a protected geometry region."""

    FORMULA = "FORMULA"
    ADJACENT_TEXT = "ADJACENT_TEXT"
    IMAGE = "IMAGE"
    VECTOR_ART = "VECTOR_ART"
    UNKNOWN = "UNKNOWN"


class VectorRole(str, Enum):
    """Semantic role of a vector drawing on a page."""

    BACKGROUND_CONTAINER = "BACKGROUND_CONTAINER"
    FORBIDDEN_VECTOR_ART = "FORBIDDEN_VECTOR_ART"
    UNKNOWN_AMBIGUOUS = "UNKNOWN_AMBIGUOUS"


@dataclass(frozen=True)
class ExclusionZone:
    """A spatial region that must not be clipped, redacted, or overwritten."""

    zone_id: str
    zone_type: ExclusionZoneType
    bbox: tuple[float, float, float, float]
    source_id: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BlockClearanceDecision:
    """Clearance evaluation outcome for an individual candidate text block."""

    block_id: str
    is_approved: bool
    tight_line_rects: list[tuple[float, float, float, float]]
    layout_box: tuple[float, float, float, float]
    collision_detail: CollisionDetail | None = None
    conflicting_zone_ids: list[str] = field(default_factory=list)


@dataclass
class ClearancePlan:
    """Complete pre-computed clearance plan for an entire page."""

    page_number: int
    exclusion_zones: list[ExclusionZone] = field(default_factory=list)
    decisions: dict[str, BlockClearanceDecision] = field(default_factory=dict)

    @property
    def approved_blocks(self) -> list[str]:
        """IDs of blocks approved for safe redaction and replacement."""
        return [b_id for b_id, dec in self.decisions.items() if dec.is_approved]

    @property
    def collision_blocks(self) -> list[str]:
        """IDs of blocks rejected due to geometric collisions with protected zones."""
        return [
            b_id
            for b_id, dec in self.decisions.items()
            if not dec.is_approved and dec.collision_detail is not None
        ]


def rects_intersect(
    r1: tuple[float, float, float, float],
    r2: tuple[float, float, float, float],
    tolerance: float = 1e-3,
) -> bool:
    """Return True if two axis-aligned bounding boxes overlap by more than tolerance points."""
    x0 = max(r1[0], r2[0])
    y0 = max(r1[1], r2[1])
    x1 = min(r1[2], r2[2])
    y1 = min(r1[3], r2[3])
    return (x1 - x0 > tolerance) and (y1 - y0 > tolerance)


def compute_tight_line_clearance_regions(
    block: TextBlock,
    padding: float = 0.5,
) -> list[tuple[float, float, float, float]]:
    """Compute tight bounding boxes per visual glyph cluster with minimal padding.

    Groups glyphs by baseline alignment and horizontal proximity (BabelDOC / pdf2zh cluster pattern).
    Uses character-level bounding boxes for non-whitespace characters when available to prevent
    trailing/leading space advance widths from bridging across protected formula symbols or inline variables.
    """
    if not block.spans:
        x0, y0, x1, y1 = block.bbox
        return [(x0 - padding, y0 - padding, x1 + padding, y1 + padding)]

    # Collect meaningful character glyphs (excluding non-printing whitespace)
    all_chars: list[Any] = []
    for s in block.spans:
        if s.chars:
            all_chars.extend([c for c in s.chars if not c.char.isspace()])
        elif s.text.strip():
            all_chars.append(type("CharProxy", (), {"bbox": s.bbox, "char": s.text.strip()}))

    if not all_chars:
        x0, y0, x1, y1 = block.bbox
        return [(x0 - padding, y0 - padding, x1 + padding, y1 + padding)]

    # Cluster characters by baseline alignment (within 3.5pt) and horizontal proximity (within 4.5pt)
    clusters: list[dict[str, Any]] = []
    for c in all_chars:
        cb = c.bbox
        c_mid_y = (cb[1] + cb[3]) / 2.0
        placed = False
        for cl in clusters:
            cl_mid_y = (cl["bbox"][1] + cl["bbox"][3]) / 2.0
            if abs(c_mid_y - cl_mid_y) <= 3.5:
                gap = max(0.0, max(cb[0] - cl["bbox"][2], cl["bbox"][0] - cb[2]))
                if gap <= 4.5:
                    cl["chars"].append(c)
                    cl["bbox"] = (
                        min(cl["bbox"][0], cb[0]),
                        min(cl["bbox"][1], cb[1]),
                        max(cl["bbox"][2], cb[2]),
                        max(cl["bbox"][3], cb[3]),
                    )
                    placed = True
                    break
        if not placed:
            clusters.append({"chars": [c], "bbox": cb})

    tight_rects: list[tuple[float, float, float, float]] = []
    for cl in clusters:
        cb = cl["bbox"]
        lx0 = cb[0] - padding
        ly0 = cb[1] - padding
        lx1 = cb[2] + padding
        ly1 = cb[3] + padding
        if lx1 > lx0 and ly1 > ly0:
            tight_rects.append((lx0, ly0, lx1, ly1))

    if not tight_rects:
        x0, y0, x1, y1 = block.bbox
        return [(x0 - padding, y0 - padding, x1 + padding, y1 + padding)]

    return tight_rects


def is_background_container(
    drawing_rect: tuple[float, float, float, float],
    block_bbox: tuple[float, float, float, float],
    drawing_seqno: int | None = None,
    text_seqno: int | None = None,
    margin_tolerance: float = 1.0,
) -> bool:
    """Determine whether a vector drawing serves as a background container for a text block.

    A drawing is classified as a Background Container if:
    1. It spatially encloses the text block with reasonable tolerance.
    2. Paint order: If sequence numbers are available, the drawing was rendered before the text.
    """
    dx0, dy0, dx1, dy1 = drawing_rect
    bx0, by0, bx1, by1 = block_bbox

    # Spatial enclosure check
    encloses = (
        (dx0 <= bx0 + margin_tolerance)
        and (dy0 <= by0 + margin_tolerance)
        and (dx1 >= bx1 - margin_tolerance)
        and (dy1 >= by1 - margin_tolerance)
    )

    if not encloses:
        return False

    # Paint order verification: background must precede text
    if drawing_seqno is not None and text_seqno is not None:
        if drawing_seqno > text_seqno:
            # Drawing was painted after the text (overlay/foreground) -> NOT a background container
            return False

    return True


class ClearancePlanner:
    """Deep module planning read-only structural clearance across all page elements.

    Evaluates candidate text blocks against formulas, adjacent text glyphs, displayed images,
    and vector graphics, guaranteeing that no destructive redaction occurs without verified
    safe clearance.
    """

    def __init__(self, padding_pt: float = 0.5) -> None:
        self.padding_pt = padding_pt

    def plan_page_clearance(
        self,
        page_ir: PageIR,
        page: pymupdf.Page | None,
        candidate_blocks: list[TextBlock],
    ) -> ClearancePlan:
        """Create a complete, pre-computed clearance plan for the specified page.

        Args:
            page_ir: Geometric intermediate representation of the page.
            page: PyMuPDF Page object for accessing raw image/drawing streams (can be None in unit tests).
            candidate_blocks: Text blocks proposed for translation replacement.

        Returns:
            ClearancePlan containing approved blocks, collision details, and tight line rects.
        """
        plan = ClearancePlan(page_number=page_ir.page_number)
        exclusion_zones = self._collect_exclusion_zones(page_ir, page, candidate_blocks)
        plan.exclusion_zones = exclusion_zones

        # Pre-compute text sequence numbers if page texttrace is accessible
        block_seqno_map: dict[str, int] = {}
        if page is not None and hasattr(page, "get_texttrace"):
            try:
                texttrace = page.get_texttrace()
                for trace in texttrace:
                    t_bbox = trace.get("bbox")
                    t_seq = trace.get("seqno")
                    if t_bbox and t_seq is not None:
                        for block in candidate_blocks:
                            if rects_intersect(t_bbox, block.bbox):
                                if block.block_id not in block_seqno_map or t_seq < block_seqno_map[block.block_id]:
                                    block_seqno_map[block.block_id] = t_seq
            except Exception:
                pass

        # Evaluate each candidate block independently on pristine geometry
        for block in candidate_blocks:
            tight_line_rects = compute_tight_line_clearance_regions(block, padding=self.padding_pt)
            layout_box = block.bbox

            collision = self._check_block_collision(
                block=block,
                tight_line_rects=tight_line_rects,
                layout_box=layout_box,
                exclusion_zones=exclusion_zones,
                block_seqno=block_seqno_map.get(block.block_id),
            )

            if collision is not None:
                plan.decisions[block.block_id] = BlockClearanceDecision(
                    block_id=block.block_id,
                    is_approved=False,
                    tight_line_rects=tight_line_rects,
                    layout_box=layout_box,
                    collision_detail=collision,
                    conflicting_zone_ids=[collision.protected_object_id] if collision.protected_object_id else [],
                )
            else:
                plan.decisions[block.block_id] = BlockClearanceDecision(
                    block_id=block.block_id,
                    is_approved=True,
                    tight_line_rects=tight_line_rects,
                    layout_box=layout_box,
                    collision_detail=None,
                )

        # Mutual interaction check: ensure approved candidate clearance rects do not overlap
        approved_ids = [b_id for b_id, dec in plan.decisions.items() if dec.is_approved]
        mutual_tolerance = max(2.5, self.padding_pt * 3.0)
        block_map = {b.block_id: b for b in candidate_blocks}
        for i, id_a in enumerate(approved_ids):
            dec_a = plan.decisions[id_a]
            b_a = block_map.get(id_a)
            mid_y_a = (b_a.bbox[1] + b_a.bbox[3]) / 2.0 if b_a else None
            for id_b in approved_ids[i + 1 :]:
                dec_b = plan.decisions[id_b]
                b_b = block_map.get(id_b)
                mid_y_b = (b_b.bbox[1] + b_b.bbox[3]) / 2.0 if b_b else None
                # Separate vertical lines with standard line-feed (> 10pt) cannot mutually collide
                if mid_y_a is not None and mid_y_b is not None and abs(mid_y_a - mid_y_b) > 10.0:
                    continue
                # Check if any tight line rect of block A intersects any tight line rect of block B
                overlap = any(
                    rects_intersect(ra, rb, tolerance=mutual_tolerance)
                    for ra in dec_a.tight_line_rects
                    for rb in dec_b.tight_line_rects
                )
                if overlap:
                    # Ambiguous mutual collision: fail-closed rejects both to prevent destructive corruption
                    plan.decisions[id_a] = BlockClearanceDecision(
                        block_id=id_a,
                        is_approved=False,
                        tight_line_rects=dec_a.tight_line_rects,
                        layout_box=dec_a.layout_box,
                        collision_detail=CollisionDetail(
                            collision_type=ExclusionZoneType.ADJACENT_TEXT.value,
                            protected_object_id=id_b,
                            bbox=dec_b.layout_box,
                            confidence=1.0,
                            description=f"Mutual clearance collision between candidate blocks {id_a} and {id_b}.",
                        ),
                        conflicting_zone_ids=[id_b],
                    )
                    plan.decisions[id_b] = BlockClearanceDecision(
                        block_id=id_b,
                        is_approved=False,
                        tight_line_rects=dec_b.tight_line_rects,
                        layout_box=dec_b.layout_box,
                        collision_detail=CollisionDetail(
                            collision_type=ExclusionZoneType.ADJACENT_TEXT.value,
                            protected_object_id=id_a,
                            bbox=dec_a.layout_box,
                            confidence=1.0,
                            description=f"Mutual clearance collision between candidate blocks {id_b} and {id_a}.",
                        ),
                        conflicting_zone_ids=[id_a],
                    )

        return plan

    def _collect_exclusion_zones(
        self,
        page_ir: PageIR,
        page: pymupdf.Page | None,
        candidate_blocks: list[TextBlock],
    ) -> list[ExclusionZone]:
        """Aggregate all 4 sources of protected geometry on the page."""
        zones: list[ExclusionZone] = []
        candidate_ids = {b.block_id for b in candidate_blocks}

        # 1. Formula regions: from IR blocks, IR regions, and math spans
        block_by_id = {b.block_id: b for b in page_ir.blocks}
        for b in page_ir.blocks:
            if b.block_type == "formula" and b.text.strip():
                if b.spans:
                    f_line_rects = compute_tight_line_clearance_regions(b, padding=self.padding_pt)
                    for l_idx, l_rect in enumerate(f_line_rects):
                        zones.append(
                            ExclusionZone(
                                zone_id=f"formula_block_{b.block_id}_l{l_idx}",
                                zone_type=ExclusionZoneType.FORMULA,
                                bbox=l_rect,
                                source_id=b.block_id,
                                confidence=1.0,
                                metadata={"block_type": "formula"},
                            )
                        )
                else:
                    zones.append(
                        ExclusionZone(
                            zone_id=f"formula_block_{b.block_id}",
                            zone_type=ExclusionZoneType.FORMULA,
                            bbox=b.bbox,
                            source_id=b.block_id,
                            confidence=1.0,
                            metadata={"block_type": "formula"},
                        )
                    )

        for r in page_ir.regions:
            if r.category == "formula":
                matching_block = block_by_id.get(
                    r.region_id.replace("_region_", "_block_")
                )
                if matching_block and matching_block.spans:
                    f_line_rects = compute_tight_line_clearance_regions(matching_block, padding=self.padding_pt)
                    for l_idx, l_rect in enumerate(f_line_rects):
                        zones.append(
                            ExclusionZone(
                                zone_id=f"formula_region_{r.region_id}_l{l_idx}",
                                zone_type=ExclusionZoneType.FORMULA,
                                bbox=l_rect,
                                source_id=r.region_id,
                                confidence=r.confidence,
                                metadata={"category": "formula"},
                            )
                        )
                else:
                    zones.append(
                        ExclusionZone(
                            zone_id=f"formula_region_{r.region_id}",
                            zone_type=ExclusionZoneType.FORMULA,
                            bbox=r.bbox,
                            source_id=r.region_id,
                            confidence=r.confidence,
                            metadata={"category": "formula"},
                        )
                    )

        # 1b. Preserved rejected tables and constituent blocks (fail-closed)
        preserved_ids = set()
        if hasattr(page_ir, "metadata") and isinstance(page_ir.metadata, dict):
            p_ids = page_ir.metadata.get("preserved_block_ids", set())
            if isinstance(p_ids, (set, list, tuple)):
                preserved_ids.update(p_ids)
            for rej_idx, rej_bbox in enumerate(page_ir.metadata.get("rejected_table_bboxes", [])):
                zones.append(
                    ExclusionZone(
                        zone_id=f"rejected_table_{rej_idx}",
                        zone_type=ExclusionZoneType.VECTOR_ART,
                        bbox=rej_bbox,
                        source_id=f"rejected_table_{rej_idx}",
                        confidence=1.0,
                        metadata={"type": "rejected_table"},
                    )
                )

        for b in page_ir.blocks:
            if b.block_type == "table_rejected" or b.block_id in preserved_ids:
                zones.append(
                    ExclusionZone(
                        zone_id=f"preserved_{b.block_id}",
                        zone_type=ExclusionZoneType.ADJACENT_TEXT,
                        bbox=b.bbox,
                        source_id=b.block_id,
                        confidence=1.0,
                        metadata={"block_id": b.block_id, "block_type": "table_rejected"},
                    )
                )

        # 2. Adjacent text: tight line bounds of all non-candidate text blocks
        for b in page_ir.blocks:
            if (
                b.block_id not in candidate_ids
                and b.block_type not in ("formula", "table_rejected")
                and b.block_id not in preserved_ids
                and b.text.strip()
            ):
                line_rects = compute_tight_line_clearance_regions(b, padding=self.padding_pt)
                for l_idx, l_rect in enumerate(line_rects):
                    zones.append(
                        ExclusionZone(
                            zone_id=f"text_{b.block_id}_l{l_idx}",
                            zone_type=ExclusionZoneType.ADJACENT_TEXT,
                            bbox=l_rect,
                            source_id=b.block_id,
                            confidence=1.0,
                            metadata={"block_id": b.block_id},
                        )
                    )

        # 3. Images: from page.get_image_info() (actual displayed images)
        if page is not None and hasattr(page, "get_image_info"):
            try:
                for img_idx, img in enumerate(page.get_image_info()):
                    raw_bbox = img.get("bbox")
                    if raw_bbox:
                        zones.append(
                            ExclusionZone(
                                zone_id=f"image_{img_idx}",
                                zone_type=ExclusionZoneType.IMAGE,
                                bbox=(float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3])),
                                source_id=str(img.get("number", img_idx)),
                                confidence=1.0,
                                metadata=img,
                            )
                        )
            except Exception:
                pass

        # Also include any IR regions flagged as figure/image
        for r in page_ir.regions:
            if r.category in ("figure", "image"):
                zones.append(
                    ExclusionZone(
                        zone_id=f"region_figure_{r.region_id}",
                        zone_type=ExclusionZoneType.IMAGE,
                        bbox=r.bbox,
                        source_id=r.region_id,
                        confidence=r.confidence,
                        metadata=r.metadata,
                    )
                )

        # 4. Vector drawings: from page.get_drawings()
        if page is not None and hasattr(page, "get_drawings"):
            try:
                for d_idx, drawing in enumerate(page.get_drawings()):
                    # Ignore pure white background fill rectangles (canvas erasers or label contrast boxes)
                    d_type = drawing.get("type")
                    d_fill = drawing.get("fill")
                    d_color = drawing.get("color")
                    if d_type == "f" and d_color is None and d_fill in ((1.0, 1.0, 1.0), [1.0, 1.0, 1.0], (1, 1, 1), [1, 1, 1]):
                        continue

                    d_rect = drawing.get("rect")
                    if d_rect:
                        stroke_w = float(drawing.get("width") or 1.0)
                        # Expand stroke bounds so horizontal/vertical lines have real visual geometry
                        half_w = max(stroke_w / 2.0, 0.5) if drawing.get("color") or drawing.get("type") in ("s", "fs") else 0.0
                        rect_tuple = (
                            float(d_rect.x0) - half_w,
                            float(d_rect.y0) - half_w,
                            float(d_rect.x1) + half_w,
                            float(d_rect.y1) + half_w,
                        )
                        zones.append(
                            ExclusionZone(
                                zone_id=f"drawing_{d_idx}",
                                zone_type=ExclusionZoneType.VECTOR_ART,
                                bbox=rect_tuple,
                                source_id=str(d_idx),
                                confidence=1.0,
                                metadata=drawing,
                            )
                        )
            except Exception:
                pass

        return zones

    def _check_block_collision(
        self,
        block: TextBlock,
        tight_line_rects: list[tuple[float, float, float, float]],
        layout_box: tuple[float, float, float, float],
        exclusion_zones: list[ExclusionZone],
        block_seqno: int | None = None,
    ) -> CollisionDetail | None:
        """Verify candidate block against all exclusion zones.

        Returns CollisionDetail on first detected violation, or None if completely clear.
        """
        for zone in exclusion_zones:
            # Ignore self-referential text exclusion zones
            if zone.source_id == block.block_id:
                continue

            # Check 1: Vector art background container exception
            if zone.zone_type == ExclusionZoneType.VECTOR_ART:
                drawing_seqno = zone.metadata.get("seqno")
                if is_background_container(
                    drawing_rect=zone.bbox,
                    block_bbox=block.bbox,
                    drawing_seqno=drawing_seqno,
                    text_seqno=block_seqno,
                ):
                    # It encloses the block as a valid container -> safe, not a collision
                    continue

                # Not a background container: check if drawing intersects tight clearance lines
                dw = zone.bbox[2] - zone.bbox[0]
                dh = zone.bbox[3] - zone.bbox[1]
                vector_tol = 1.2 if (dh <= 2.5 or dw <= 2.5) else 0.5
                intersects_clearance = any(rects_intersect(line_rect, zone.bbox, tolerance=vector_tol) for line_rect in tight_line_rects)
                if intersects_clearance:
                    return CollisionDetail(
                        collision_type=ExclusionZoneType.VECTOR_ART.value,
                        protected_object_id=zone.zone_id,
                        bbox=zone.bbox,
                        confidence=zone.confidence,
                        description=f"Tight clearance region intersects forbidden vector drawing ({zone.zone_id}).",
                    )
                continue

            # Check 2: Formula collision
            if zone.zone_type == ExclusionZoneType.FORMULA:
                # Distinguish genuine destructive 2D intrusion from natural adjacent neighbor boundary contact.
                # In math textbooks and tables, labels naturally sit adjacent to math symbols (e.g. '=', '-', 'Δ').
                # Skip inline diacritics / accents / vector arrows (width <= 15pt) horizontally within the block
                zw = zone.bbox[2] - zone.bbox[0]
                if zw <= 15.0 and zone.bbox[0] >= block.bbox[0] - 1.0 and zone.bbox[2] <= block.bbox[2] + 1.0:
                    continue

                def has_destructive_formula_overlap(r1: tuple[float, float, float, float], r2: tuple[float, float, float, float]) -> bool:
                    x_ov = min(r1[2], r2[2]) - max(r1[0], r2[0])
                    y_ov = min(r1[3], r2[3]) - max(r1[1], r2[1])
                    if x_ov <= 0.5 or y_ov <= 0.5:
                        return False
                    return (x_ov > 2.0 and y_ov > 2.0) or (x_ov > 10.0 and y_ov > 1.5)

                intersects_line = any(has_destructive_formula_overlap(line_rect, zone.bbox) for line_rect in tight_line_rects)
                # When tight_line_rects are available, they accurately represent the actual text glyphs.
                # Only check layout_box if tight_line_rects is empty (fallback).
                intersects_box = has_destructive_formula_overlap(layout_box, zone.bbox) if not tight_line_rects else False
                if intersects_line or intersects_box:
                    return CollisionDetail(
                        collision_type=ExclusionZoneType.FORMULA.value,
                        protected_object_id=zone.zone_id,
                        bbox=zone.bbox,
                        confidence=zone.confidence,
                        description=f"Clearance collides with protected formula ({zone.zone_id}).",
                    )
                continue

            # Check 3: Image collision
            if zone.zone_type == ExclusionZoneType.IMAGE:
                # Require genuine intrusion into image pixels rather than sub-point clearance padding contact
                def has_destructive_image_overlap(r1: tuple[float, float, float, float], r2: tuple[float, float, float, float]) -> bool:
                    x_ov = min(r1[2], r2[2]) - max(r1[0], r2[0])
                    y_ov = min(r1[3], r2[3]) - max(r1[1], r2[1])
                    return (x_ov > 1.5) and (y_ov > 1.5)

                intersects_line = any(has_destructive_image_overlap(line_rect, zone.bbox) for line_rect in tight_line_rects)
                intersects_box = has_destructive_image_overlap(layout_box, zone.bbox) if not tight_line_rects else False
                if intersects_line or intersects_box:
                    return CollisionDetail(
                        collision_type=ExclusionZoneType.IMAGE.value,
                        protected_object_id=zone.zone_id,
                        bbox=zone.bbox,
                        confidence=zone.confidence,
                        description=f"Clearance intersects visual image ({zone.zone_id}).",
                    )
                continue

            # Check 4: Adjacent text collision
            if zone.zone_type == ExclusionZoneType.ADJACENT_TEXT:
                adj_tolerance = max(1.0, self.padding_pt * 2.0)
                intersects_line = any(rects_intersect(line_rect, zone.bbox, tolerance=adj_tolerance) for line_rect in tight_line_rects)
                if intersects_line:
                    return CollisionDetail(
                        collision_type=ExclusionZoneType.ADJACENT_TEXT.value,
                        protected_object_id=zone.zone_id,
                        bbox=zone.bbox,
                        confidence=zone.confidence,
                        description=f"Tight clearance region intersects adjacent text line ({zone.zone_id}).",
                    )
                continue

            # Check 5: Unknown / ambiguous collision
            if any(rects_intersect(line_rect, zone.bbox) for line_rect in tight_line_rects):
                return CollisionDetail(
                    collision_type=ExclusionZoneType.UNKNOWN.value,
                    protected_object_id=zone.zone_id,
                    bbox=zone.bbox,
                    confidence=zone.confidence,
                    description=f"Clearance region intersects ambiguous protected zone ({zone.zone_id}).",
                )

        return None
