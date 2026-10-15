# Task Brief: Task 2 — Vector Primitive Filtering & TableGridValidator

- **Base Commit:** `dc342f0`
- **Plan File:** `docs/superpowers/plans/2026-10-11-slice-4c-2-table-cell-isolation.md`
- **Spec File:** `docs/superpowers/specs/2026-10-11-slice-4c-2-table-cell-isolation-design.md` (Section 3.1 & Section 4 Group 1)
- **Scope:** Exactly 6 acceptance tests for vector primitive filtering and `TableGridValidator`. Do NOT implement `TableCellPartitioner` (Task 3).

---

## 1. Context & Objectives
In PDF table handling, naive detection (or unverified `page.find_tables()`) yields false positives from background tint rectangles or arbitrary curves. Furthermore, tables with missing dividers must not be accepted.
Task 2 implements a deep, self-contained module in `layoutlingua/core/tables.py` that corroborates `find_tables()` against physical vector drawings from `page.get_drawings()`.

## 2. Interface Contract (`codebase-design`)
- **Module:** `layoutlingua/core/tables`
- **Dependencies:** Imports only from `layoutlingua.core.table_models` (`BorderLine`, `CellGeometry`, `TableGrid`) and `layoutlingua.core.ir` (`PageIR`). Zero dependencies on `layoutlingua.typesetting`.
- **Public Functions / Classes:**
  1. `extract_valid_vector_segments(drawings: list[dict]) -> list[tuple[float, float, float, float, float]]`
     - Returns list of `(x1, y1, x2, y2, width)`.
     - Stroke check: Drawing admitted ONLY if `drawing.get("type") in ("s", "fs")` or (`drawing.get("color") is not None` and `drawing.get("width", 0) > 0`). Pure fill `type == "f"` without stroke color is strictly ignored.
     - Primitives in `drawing.get("items", [])`:
       - `'l'`: straight line segment $(p_1, p_2)$. Normalized $(x_1 \le x_2, y_1 \le y_2)$. Admitted if collinear with horizontal or vertical axis ($|dx| \le 1.0$ or $|dy| \le 1.0$).
       - `'re'`: rectangle `Rect(item[1])`. Decomposed into 4 orthogonal boundary segments: top, bottom, left, right.
       - `'c'`: cubic bezier curves. STRICTLY REJECTED.
       - `'qu'`: quad bezier curves. STRICTLY REJECTED.
  2. `TableGridValidator(tolerance_pt: float = 2.0, min_edge_coverage: float = 0.90)`
     - `validate_page_tables(self, page: pymupdf.Page, page_ir: PageIR) -> list[TableGrid]`
     - Calls `page.find_tables()`.
     - Dimensions check: `(rows >= 1 and cols >= 2) or (rows >= 2 and cols >= 1)`. Rejects $1 \times 1$.
     - Rejects any table with `None` in `row.cells` (fail-closed merged-cell policy).
     - Corroborates outer bbox: all 4 sides match admitted vector segments within `tolerance_pt <= 2.0` with $\ge 90\%$ coverage.
     - Corroborates internal cell divider edges: $\ge 90\%$ coverage per individual edge segment (collinear segments with gap $\le 2.0\text{ pt}$ merged).
     - On rejection: tags intersecting blocks in `page_ir.blocks` as `block_type="table_rejected"`, adds `block_id` to `page_ir.metadata["preserved_block_ids"]`, adds `table.bbox` to `page_ir.metadata["rejected_table_bboxes"]`.
     - On success: constructs `TableGrid` with `CellGeometry` for each cell, attaches to `page_ir.metadata.setdefault("tables", {})[grid.table_id] = grid`. Returns list of validated `TableGrid`s.

## 3. Test Requirements (6 Tests)
1. `test_table_grid_corroboration_lines_and_rects` (2x2 table, `'l'` and `'re'`, $\ge 90\%$ coverage)
2. `test_table_grid_corroboration_rejects_weak_evidence` (missing internal divider or gap $> 2.0\text{ pt} \to$ rejected)
3. `test_vector_evidence_rejects_fill_only_rectangles` (`drawing["type"] == "f"` without stroke $\to$ ignored)
4. `test_vector_evidence_rejects_curve_bounding_boxes` (bezier curve `'c'` $\to$ strictly ignored)
5. `test_vector_evidence_mixed_path_line_and_curve` (mixed `'l'` and `'c'` items $\to$ admits only `'l'`)
6. `test_table_dimension_varieties_1x2_and_2x1` ($1\times 2$ and $2\times 1$ tables recognized)

## 4. Execution Protocol
- Base commit: `dc342f0`.
- TDD RED $\to$ GREEN $\to$ REFACTOR.
- Regression test suite: all 120 tests must pass (109 baseline + 5 Task 1 + 6 Task 2).
- Commit message: `feat(tables): implement vector primitive filtering and TableGridValidator`.
- Independent review verification.
