# SDD ledger — plan: docs/superpowers/plans/2026-10-11-slice-4c-2-table-cell-isolation.md

## Preflight Conflict & Interface Scan

| Task Pair / Focus | Interfaces / Shared Files | Preflight Assessment | Status / Ruling |
|:---|:---|:---|:---|
| Task 1 vs Task 2 | `layoutlingua.core.table_models` -> `layoutlingua.core.tables` | Task 1 defines `BorderLine`, `CellGeometry`, `TableGrid`. Task 2 imports them cleanly in `core.tables`. Core never imports typesetting. | Clean. No circular dependency. |
| Task 2 vs Task 3 | `TableGridValidator` -> `TableCellPartitioner` | Both in `layoutlingua.core.tables`. Validator attaches `TableGrid`s; Partitioner operates on them and refines `page_ir.blocks`. | Clean. Strict topological separation. |
| Task 3 vs Task 4 | Partitioner -> Block Suppression Pipeline | Partitioner tags rejected tables as `table_rejected` and adds IDs to `preserved_block_ids`. Task 4 consumes these sets in Translation & Clearance. | Clean. Unambiguous tag matching. |
| Task 4 vs Task 5 | Suppression -> Geometry & Stroke-Aware Insets | Task 5 operates only on approved `table_cell` blocks; rejected blocks are already excluded by Task 4. | Clean. Geometry lookup from `metadata["tables"]`. |
| Task 6 vs Task 7 | Page Transaction -> Document Accumulator | Boundary contract: `PageTransactionResult(page_number, source_page_index, staging_doc, is_fallback, details, summary)`. | **Ruling: Indexing contract explicitly enforced:** `page_number` is 1-indexed (telemetry, reports, PageIR), `source_page_index` is 0-indexed (PyMuPDF `source_doc[p]`, `insert_pdf`). Invariant: `page_number == source_page_index + 1`. |
| Task 7 vs Task 8 | Document Accumulator -> Link Restoration | Task 7 finishes committing all $N$ pages to `output_doc` before Task 8 runs post-assembly link restoration. | Clean. Sequential execution prevents dropped cross-page links. |
| Task 8 vs Task 9 | Link Restoration -> Visual Integrity & Telemetry | Task 8 preserves form widgets & links; Task 9 verifies structural invariants & multi-tier telemetry stratification. | Clean. Full test suite covers 34 acceptance tests. |

## Preflight Rulings

- **Ruling 1 (Page Indexing Contract):** `PageTransactionResult` carries both `page_number` (1-indexed for telemetry and PageIR) and `source_page_index` (0-indexed for PyMuPDF APIs). Invariant: `page_number == source_page_index + 1`. Cost if wrong: off-by-one page extraction or fallback commit error.
- **Ruling 2 (Telemetry Commit Gate):** `report.details` and `report.pages` must receive `SUCCESS` records ONLY AFTER `output_doc.insert_pdf` completes cleanly. If commit fails and rolls back, emergency fallback source records are committed instead. Cost if wrong: false success telemetry on a page that was reverted.

---

## Task Execution Status

- Task 1: complete (commit dc342f0, review clean)
- Task 2: complete (commits dc342f0..3d2d11d, review clean)
- Task 3: complete (commit 0c7a467, review clean)
- Task 4: complete (commit cffa6d5, review clean)
- Task 5: complete (commit e660676, review clean)
- Task 6: complete (commit d3b00b7, review clean)
- Task 7: complete (commit ae2f080, review clean)
- Task 8: complete (commit fe98241, review clean)
- Task 9: pending
