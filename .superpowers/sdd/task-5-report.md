# Task 5 Report — Geometry & Stroke-Aware Insets

## 1. Executive Summary
- **Task:** Task 5 — Geometry & Stroke-Aware Insets
- **Base Commit:** `cffa6d5`
- **HEAD Commit:** `e660676`
- **Diff:** `cffa6d5..e660676`
- **Regression Suite:** **138/138 PASS** (6 new acceptance tests in `tests/test_slice4c_tables.py`).

---

## 2. Implementation Overview

### 2.1 Domain Models & Formula Implementation
- **File:** `layoutlingua/core/table_models.py` & `layoutlingua/core/tables.py`
- Defined `CellInsets(top, bottom, left, right)` dataclass.
- Implemented `compute_stroke_aware_insets(border_widths)` using the spec formula:
  $$p_{\text{side}} = \max(1.0, w / 2.0 + 0.5)$$
  where hairline borders or missing dividers ($w \le 1.0$) are safely clamped to $1.0\text{ pt}$ minimum clearance.
- Implemented `compute_cell_inner_bbox(cell_bbox, border_widths)` returning $(x_0 + p_{\text{left}}, y_0 + p_{\text{top}}, x_1 - p_{\text{right}}, y_1 - p_{\text{bottom}})$.
- Fail-Closed degenerate handling: If $x_1 - p_{\text{right}} \le x_0 + p_{\text{left}}$ or $y_1 - p_{\text{bottom}} \le y_0 + p_{\text{top}}$, `compute_cell_inner_bbox` returns `None`.
- Extended `CellGeometry` with `.insets` property and `.compute_inner_bbox()` method.

### 2.2 TypesetEngine Cell Isolation & Stroke Protection
- **File:** `layoutlingua/typesetting/engine.py`
- Linked `table_cell` blocks to corroborated `TableGrid` and `CellGeometry` stored in `page_ir.metadata["tables"]`.
- Enforced fail-closed behavior for unresolvable geometry: If `CellGeometry` is missing, block is skipped and source text retained, recording `BlockFittingStatus.SKIPPED_UNSUPPORTED` with `unit_kind="CELL"`.
- Enforced fail-closed behavior for narrow/shallow cells: If `inner_bbox is None`, recorded as `BlockFittingStatus.OVERFLOW_FALLBACK` with `OverflowCause.OVERFLOW_WIDTH_AT_MIN_SIZE`, incrementing `overflow_cells`.
- Precision Binary Search fitting test evaluated strictly within `inner_bbox`: `self._fit_tester.test_fit(rect=inner_bbox, ...)`.
- Redaction clamping: Redaction regions for cell candidates are clamped strictly within `inner_bbox`, guaranteeing physical vector borders are 100% untouched.
- Text placement: Fitted translation text inserted strictly into `inner_bbox`.
- Multi-tier telemetry: Tracked `total_cells`, `replaced_cells`, `overflow_cells`, `skipped_cells`, and `collision_cells` on both `FittingReport` and `PageFittingSummary`.

---

## 3. Test Suite Verification
- **Test Class:** `TestSlice4CStrokeAwareInsets` in `tests/test_slice4c_tables.py`
  1. `test_stroke_aware_insets_calculation`: Verifies asymmetric border stroke widths calculate exact insets and inner bbox.
  2. `test_stroke_aware_insets_minimum_clamp`: Verifies hairline ($w \le 1.0$) clamps to $1.0\text{ pt}$.
  3. `test_narrow_cell_fail_closed`: Verifies degenerate cell fails closed and logs `overflow_cells=1`.
  4. `test_missing_cell_geometry_fail_closed`: Verifies orphan `table_cell` block fails closed and logs `skipped_cells=1`.
  5. `test_cell_typesetting_within_inner_bbox`: Verifies text rendered inside inner bbox without clipping border vector line art.
  6. `test_cell_text_overflow_fail_closed`: Verifies oversized translation text fails closed at minimum font scale.
- **Suite Result:** 138/138 passed in 11.93s.
