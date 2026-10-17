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
    """Compute tight bounding boxes per line/span with minimal padding.

    Groups spans or characters belonging to the same text line, computes the tight union
    bounding box of that line's glyphs, and adds a small safety padding (<= 0.5 pt).
    This prevents redaction from clipping adjacent lines, formulas, or container borders.
    """
    if not block.spans:
        # Fallback to block bbox if spans are empty
        x0, y0, x1, y1 = block.bbox
        return [(x0 - padding, y0 - padding, x1 + padding, y1 + padding)]

    # Group spans by line
    line_groups: dict[str, list[Any]] = {}
    for s_idx, span in enumerate(block.spans):
        # 1. Try extracting line identifier from span_id pattern (e.g. p1_b0_l2_s0)
        match = re.search(r"_l(\d+)_", span.span_id)
        if match:
            line_key = f"line_{match.group(1)}"
        else:
            # 2. Heuristic grouping by vertical baseline / origin (within 3 pt)
            origin_y = span.origin[1] if span.origin != (0.0, 0.0) else span.bbox[1]
            rounded_y = round(origin_y / 3.0) * 3.0
            line_key = f"y_{rounded_y:.1f}"

        line_groups.setdefault(line_key, []).append(span)

    tight_rects: list[tuple[float, float, float, float]] = []

    for _, spans_in_line in line_groups.items():
        char_boxes: list[tuple[float, float, float, float]] = []
        for span in spans_in_line:
            if not span.text.strip():
                continue
            if span.chars:
                for c in span.chars:
                    if c.char.strip() and c.bbox[2] > c.bbox[0] and c.bbox[3] > c.bbox[1]:
                        char_boxes.append(c.bbox)
            else:
                if span.bbox[2] > span.bbox[0] and span.bbox[3] > span.bbox[1]:
                    char_boxes.append(span.bbox)

        if not char_boxes:
            continue

        lx0 = min(b[0] for b in char_boxes) - padding
        ly0 = min(b[1] for b in char_boxes) - padding
        lx1 = max(b[2] for b in char_boxes) + padding
        ly1 = max(b[3] for b in char_boxes) + padding

        # Ensure valid non-inverted bbox
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
        mutual_tolerance = max(1.5, self.padding_pt * 2.5)
        for i, id_a in enumerate(approved_ids):
            dec_a = plan.decisions[id_a]
            for id_b in approved_ids[i + 1 :]:
                dec_b = plan.decisions[id_b]
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
                vector_tol = 1.0 if (dh <= 1.5 or dw <= 1.5) else 0.2
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
                # Check both tight clearance lines and replacement layout box
                formula_tol = max(0.5, self.padding_pt)
                intersects_line = any(rects_intersect(line_rect, zone.bbox, tolerance=formula_tol) for line_rect in tight_line_rects)
                intersects_box = rects_intersect(layout_box, zone.bbox, tolerance=0.1)
                if intersects_line or intersects_box:
                    return CollisionDetail(
                        collision_type=ExclusionZoneType.FORMULA.value,
                        protected_object_id=zone.zone_id,
                        bbox=zone.bbox,
                        confidence=zone.confidence,
                        description=f"Clearance or layout box collides with protected formula ({zone.zone_id}).",
                    )
                continue

            # Check 3: Image collision
            if zone.zone_type == ExclusionZoneType.IMAGE:
                # Any image intersection is forbidden in 4C.1 fail-closed scope
                intersects_line = any(rects_intersect(line_rect, zone.bbox) for line_rect in tight_line_rects)
                intersects_box = rects_intersect(layout_box, zone.bbox)
                if intersects_line or intersects_box:
                    return CollisionDetail(
                        collision_type=ExclusionZoneType.IMAGE.value,
                        protected_object_id=zone.zone_id,
                        bbox=zone.bbox,
                        confidence=zone.confidence,
                        description=f"Clearance or layout box intersects visual image ({zone.zone_id}).",
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
