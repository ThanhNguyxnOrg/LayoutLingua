# Task Brief: Task 3 — Pre-Translation Cell Partitioner & Glyph Provenance Invariant

- **Base Commit:** `3d2d11d`
- **Plan File:** `docs/superpowers/plans/2026-10-11-slice-4c-2-table-cell-isolation.md`
- **Spec File:** `docs/superpowers/specs/2026-10-11-slice-4c-2-table-cell-isolation-design.md` (Section 3.2 & Section 4 Group 2)
- **Scope:** Exactly 7 acceptance tests for `TableCellPartitioner` and glyph provenance conservation invariant. Do NOT implement Task 4 (block suppression pipeline / translation clearance).

---

## 1. Context & Objectives
In PDF extraction, text spans frequently extend across multiple table columns on the same horizontal baseline (e.g., `"Col1 Col2"` extracted as a single TextBlock/GlyphSpan). If fed directly to translation, text from adjacent cells merges into a single string, destroying table structure and causing translation overlap or bleed across cell borders.

Task 3 implements `TableCellPartitioner` in `layoutlingua/core/tables.py`. It partitions blocks and spans that intersect validated `TableGrid`s down to individual cell boundaries before translation occurs, while strictly preserving every single glyph's identity and provenance.

## 2. Interface Contract (`codebase-design`)
- **Module:** `layoutlingua/core/tables`
- **Dependencies:** `layoutlingua.core.table_models` (`CellGeometry`, `TableGrid`), `layoutlingua.core.ir` (`CharInfo`, `GlyphSpan`, `PageIR`, `TextBlock`). No dependencies on typesetting.
- **Public Functions / Classes:**
  1. `TableCellPartitioner(tolerance_pt: float = 1.0)`
     - `partition_cells(self, page_ir: PageIR, grids: list[TableGrid]) -> bool`
     - Operates on each `TableGrid` in `grids`.
     - Identifies blocks intersecting the table grid bbox.
     - Builds glyph provenance multiset $C_{\text{in}}$ across all candidate blocks intersecting the grid:
       $$\text{id} = \text{f"p{page_number}_b{block_id}_s{span_id}_c{char_index}"}$$
     - Checks cell geometry validity (e.g., checks merged cells without full coverage $\to$ abort).
     - Inspects each span for atomic formula tokens (e.g. `⟦LL_FORMULA_\d+⟧` or `⟦...⟧`). If any formula token intersects a cell boundary line or straddles two cells, table partitioning fails closed.
     - Partitions glyphs into cells using character bbox / center point. If a glyph straddles a cell border ambiguously (within tolerance or overlap without clear containment), table partitioning fails closed.
     - Reconstructs `TextBlock` for each non-empty cell:
       - `block_id = cell.cell_id`
       - `bbox = cell.bbox`
       - `block_type = "table_cell"`
       - `spans`: reconstructed `GlyphSpan`s grouping contiguous characters inside the cell.
     - Verifies glyph provenance conservation invariant:
       $$C_{\text{out}} == C_{\text{in}}$$
       using `collections.Counter`. If $C_{\text{out}} \ne C_{\text{in}}$, aborts partitioning fail-closed.
     - On abort / fail-closed for a table:
       - Restores or leaves original intersecting blocks intact.
       - Tags intersecting blocks as `block_type = "table_rejected"`.
       - Adds block IDs to `page_ir.metadata.setdefault("preserved_block_ids", set())`.
       - Adds table bbox to `page_ir.metadata.setdefault("rejected_table_bboxes", [])`.
       - Returns `False` (or marks table rejected).
     - On success:
       - Replaces original intersecting blocks in `page_ir.blocks` with the generated `table_cell` blocks (maintaining non-table blocks unchanged).
       - Attaches cells to table metadata.
       - Returns `True`.

## 3. Test Requirements (7 Tests in `TestTableCellPartitioner`)
1. `test_pre_translation_cell_partitioning_same_baseline`: Text across columns on identical baseline splits into distinct cell TextBlocks with stable IDs (`p{p}_t{t}_r{r}_c{c}`).
2. `test_character_level_span_splitting_across_border`: Continuous span across border partitioned cleanly using `CharInfo` bboxes.
3. `test_glyph_identity_and_provenance_conservation`: Glyph provenance multiset $C_{\text{out}} == C_{\text{in}}$ preserved.
4. `test_glyph_conservation_detects_drop_and_duplicate_with_same_count`: Synthetic multiset tampering detected fail-closed.
5. `test_atomic_formula_token_crossing_border_fails_closed`: Formula token `⟦LL_FORMULA_0001⟧` straddling divider aborts partitioning, marks blocks `table_rejected`.
6. `test_ambiguous_glyph_ownership_fails_closed`: Ambiguous glyph ownership straddling divider aborts partitioning, marks blocks `table_rejected`.
7. `test_unsupported_merged_cells_fail_closed`: Unverified merged cell grid fails closed, marks blocks `table_rejected`.

## 4. Execution Protocol
- Base commit: `3d2d11d`.
- TDD RED verification: run test suite and confirm failure of 7 new tests (due to missing `TableCellPartitioner`).
- Implementation: implement `TableCellPartitioner` in `layoutlingua/core/tables.py`.
- TDD GREEN verification: all 7 new tests pass, plus all 120 regression tests (total 127 PASS).
- Review & Verification before completion.
