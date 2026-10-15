# Task 5 Brief — Geometry & Stroke-Aware Insets

## 1. Overview & Context
- **Slice:** Slice 4C.2 — Table Cell Isolation & Grid Protection
- **Task:** Task 5 — Geometry & Stroke-Aware Insets
- **Base Commit:** `cffa6d5`
- **Dependencies:** Task 1 (`table_models`), Task 2 (`TableGridValidator`), Task 3 (`TableCellPartitioner`), Task 4 (`BlockSuppressionPipeline` & `TranslationService`).

---

## 2. Objectives & Specifications

### 2.1 Stroke-Aware Insets Formula
For each cell border side $s \in \{\text{top}, \text{bottom}, \text{left}, \text{right}\}$ with verified physical vector stroke width $w_s$:
$$p_s = \max(1.0,\; w_s / 2.0 + 0.5)$$

- If $w_s = 0$ (no physical divider on side): $p_s = \max(1.0, 0.5) = 1.0\text{ pt}$.
- If $w_s = 1.0\text{ pt}$ (standard 1pt stroke): $p_s = \max(1.0, 1.0) = 1.0\text{ pt}$.
- If $w_s = 2.0\text{ pt}$: $p_s = \max(1.0, 1.5) = 1.5\text{ pt}$.
- If $w_s = 4.0\text{ pt}$: $p_s = \max(1.0, 2.5) = 2.5\text{ pt}$.

### 2.2 Effective Inner Bounding Box
Given a cell's exterior bounding box $\text{cell\_bbox} = (x_0, y_0, x_1, y_1)$ and insets $(p_{\text{left}}, p_{\text{top}}, p_{\text{right}}, p_{\text{bottom}})$:
$$\text{inner\_bbox} = (x_0 + p_{\text{left}},\; y_0 + p_{\text{top}},\; x_1 - p_{\text{right}},\; y_1 - p_{\text{bottom}})$$

**Narrow / Degenerate Cell Rule (Fail-Closed):**
If $(x_1 - p_{\text{right}}) \le (x_0 + p_{\text{left}})$ or $(y_1 - p_{\text{bottom}}) \le (y_0 + p_{\text{top}})$:
- $\text{inner\_bbox}$ is degenerate / invalid (`None`).
- The cell must fail closed without redacting or corrupting borders. Source text is retained.

### 2.3 Typesetting & Fitting Integration
When `TypesetEngine` processes a candidate block with `block_type == "table_cell"`:
1. Lookup corresponding `CellGeometry` via `page_ir.metadata["tables"]`.
2. If `CellGeometry` is missing, corrupted, or unresolvable:
   - Fail closed: skip block, record `BlockFittingDetail` with `unit_kind="CELL"`, `status=SKIPPED_UNSUPPORTED`.
3. Compute `inner_bbox`:
   - If `inner_bbox is None`: fail closed, record `OVERFLOW_FALLBACK` with `unit_kind="CELL"`.
4. Perform font size fitting strictly within `inner_bbox`:
   - `_fit_tester.test_fit(rect=inner_bbox, text=translated_text, ...)`
5. Redaction and text insertion:
   - Redactions are clamped strictly within `inner_bbox` (so vector borders are 100% protected).
   - Text is inserted into `inner_bbox`.
6. Update Tier 2 cell telemetry:
   - Increment `total_cells`, and either `replaced_cells` or `overflow_cells` / `collision_cells`.

---

## 3. TDD Acceptance Test Plan

1. `test_stroke_aware_insets_calculation`: Verify exact formula computation for asymmetric border stroke widths.
2. `test_stroke_aware_insets_minimum_clamp`: Verify $w \le 1.0$ clamps to $1.0\text{ pt}$ minimum clearance.
3. `test_narrow_cell_fail_closed`: Verify degenerate / narrow cells where padding exceeds dimensions return `None` and fail closed in typesetting.
4. `test_missing_cell_geometry_fail_closed`: Verify `table_cell` blocks without `CellGeometry` fail closed and preserve source text.
5. `test_cell_typesetting_within_inner_bbox`: Verify translated text is typeset strictly inside inner bbox, leaving borders untouched.
6. `test_cell_text_overflow_fail_closed`: Verify cell text that exceeds inner bbox at minimum scale fails closed and increments `overflow_cells`.

---

## 4. Worktree & Commit Constraints
- Work conducted on local repository branch with clean status.
- Commit message: `feat(tables): implement stroke-aware insets and cell geometry protection`.
- Regression check: 132/132 existing tests + new Task 5 acceptance tests = 138+ PASS.
