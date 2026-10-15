# Task Brief: Task 4 — Pipeline Fail-Closed Preservation & Block Suppression

- **Base Commit:** `0c7a467`
- **Plan File:** `docs/superpowers/plans/2026-10-11-slice-4c-2-table-cell-isolation.md`
- **Spec Reference:** `docs/superpowers/specs/2026-10-11-slice-4c-2-table-cell-isolation-design.md` (Section 3.4 & Section 4 Group 3)
- **Scope:** Pipeline fail-closed block suppression and translation isolation. Do NOT implement Task 5 (stroke-aware geometry insets & cell typeset).

---

## 1. Context & Objectives
When tables are rejected by `TableGridValidator` (Task 2) or `TableCellPartitioner` (Task 3) due to weak vector evidence, ambiguous glyph ownership, or crossing formula tokens, their constituent blocks must NOT be fed to `TranslationService`, NOT redacted, and NOT typeset as regular text. Attempting to typeset a rejected table as regular text destroys the visual grid divider lines with redaction rectangles and causes illegible text collisions.

Task 4 implements end-to-end block suppression across the pipeline:
1. **Translation Pipeline (`translate_document` / segment extraction):** Blocks tagged `block_type == "table_rejected"` or present in `preserved_block_ids` are skipped, producing 0 translated mutations for rejected table blocks.
2. **Clearance Planning (`ClearancePlanner`):** Constituent blocks of rejected tables are registered as protected exclusion zones with zero clearance regions.
3. **Typesetting Engine (`TypesetEngine`):** Candidate resolution filters out `table_rejected` blocks and `preserved_block_ids`. Telemetry logs `BlockFittingStatus.SKIPPED_UNSUPPORTED` with zero cell metric inflation and zero redactions. Original source text is 100% retained.
4. **Valid Cell & Text Preservation:** Regular text blocks and valid `table_cell` blocks continue through translation and typesetting normally.
5. **Fail-Closed on Corrupted Metadata:** Missing or malformed metadata gracefully falls back to checking `block.block_type == "table_rejected"`.

## 2. Interface Contract (`codebase-design`)
- **Modules modified:**
  - `layoutlingua/translation/mock.py`: `translate_document` respects `preserved_block_ids` and `block_type == "table_rejected"`.
  - `layoutlingua/typesetting/protection.py`: `_extract_page_exclusion_zones` registers `preserved_block_ids` and `table_rejected` blocks as `ExclusionZoneType.ADJACENT_TEXT`.
  - `layoutlingua/typesetting/engine.py`: filters candidate blocks against `table_rejected` and `preserved_block_ids`; records `SKIPPED_UNSUPPORTED` in `FittingReport`.
- **Telemetry Schema:**
  - `BlockFittingStatus.SKIPPED_UNSUPPORTED`: logged for preserved table blocks.
  - `report.replaced_blocks`: 0 for rejected table blocks.
  - `report.skipped_blocks`: incremented by 1 per rejected table block.
  - `report.total_cells`: 0 (no inflation from rejected tables).

## 3. Test Requirements (in `TestPipelineFailClosedPreservation`)
1. `test_rejected_table_source_blocks_strictly_preserved_fail_closed`: Validator marks blocks as `table_rejected` and records in `page_ir.metadata["preserved_block_ids"]`.
2. `test_rejected_table_pipeline_preservation_contract`: End-to-end integration: rejected block tagged `table_rejected` and in `preserved_block_ids` produces 0 redactions, text is untouched in output PDF, telemetry reports `SKIPPED_UNSUPPORTED`.
3. `test_translation_pipeline_skips_rejected_table_blocks_and_translates_valid_blocks`: Translation preserves rejected table block text exactly while translating normal paragraphs and valid table cells.
4. `test_fail_closed_missing_or_corrupt_metadata`: Even if `doc_ir.metadata` is empty or missing, `block_type == "table_rejected"` blocks are completely skipped and preserved.

## 4. Execution Protocol
- Base commit: `0c7a467`.
- TDD RED verification: add 4 acceptance tests to `tests/test_slice4c_tables.py`, run tests, confirm failure.
- TDD GREEN: implement suppression in `engine.py`, `protection.py`, and `mock.py`.
- Regression: run entire test suite (131 tests).
- Independent review verification.
