# Review Report: Task 4 — Pipeline Fail-Closed Preservation & Block Suppression

- **Target Range:** `0c7a467..cffa6d5`
- **Plan File:** `docs/superpowers/plans/2026-10-11-slice-4c-2-table-cell-isolation.md`
- **Spec Reference:** `docs/superpowers/specs/2026-10-11-slice-4c-2-table-cell-isolation-design.md` (Section 3.4 & Section 4 Group 3)
- **Base Commit:** `0c7a467`
- **Task Commits:** `3526490` -> `cffa6d5`
- **Regression Suite:** 132/132 tests PASS (0 failures, 0 errors)

---

## 1. Architectural Seam & Data Flow Verification

Following the reviewer's inquiry regarding data path protection before reaching translation providers:

```
[DocumentIR with table_rejected / preserved_block_ids]
                       │
                       ▼
    extract_document_segments(doc_ir)  ◄── FAIL-CLOSED FILTER GATE 1
    (skips table_rejected, formulas, preserved_ids)
                       │
                       ├─ Rejected blocks: 0 segments extracted
                       ├─ Valid table cells: TextSegment extracted
                       └─ Normal text blocks: TextSegment extracted
                       │
                       ▼
            TranslationJob(segments)
                       │
                       ▼
         TranslationService.translate_job()
                       │
                       ▼
       BaseTranslationProvider.translate_batch() ◄── SPY PROVIDER BOUNDARY
       (receives ONLY valid blocks; 0 calls for rejected blocks)
                       │
                       ▼
                 TypesetEngine ◄── DEFENSE-IN-DEPTH GATE 2
                 (candidate blocks filter table_rejected;
                  zero redactions, source text preserved intact)
```

### Verification Evidence:
- **`layoutlingua/translation/service.py`:** Added `extract_document_segments(doc_ir)` and `TranslationService.translate_document(doc_ir, ...)`. Filters blocks at the source, preventing `table_rejected` blocks from ever entering a `TranslationJob` or batch request.
- **`layoutlingua/translation/mock.py`:** `MockTranslationProvider.translate_document` also updated with identical fail-closed suppression for backward compatibility.
- **Spy Provider Integration Test (`test_translation_service_spy_verifies_rejected_blocks_never_sent_to_provider`):** Uses a custom `SpyTranslationProvider` implementing `BaseTranslationProvider` to inspect every segment received at the service provider boundary.
  - Verified: `b_rejected_table` and `"Secret Table Data"` are NOT in `received_segment_ids` or `received_texts`.
  - Verified: `b_normal` and `b_valid_cell` ARE in `received_segment_ids` and are translated.
  - Verified: translated map has 0 entries for the rejected block.

---

## 2. Spec Compliance Review

| Requirement / Acceptance Test | Spec Criteria | Status | Evidence / Verification |
|:---|:---|:---|:---|
| 1. Rejection & Preservation Registry (`test_rejected_table_source_blocks_strictly_preserved_fail_closed`) | Table rejected by validator tags intersecting blocks as `table_rejected` and records them in `preserved_block_ids`. | PASS | Intersecting block tagged `table_rejected` and registered in `page_ir.metadata["preserved_block_ids"]`. |
| 2. End-to-End Pipeline Preservation Contract (`test_rejected_table_pipeline_preservation_contract`) | Preserved table blocks produce 0 segments for translation, 0 redactions in `TypesetEngine`, 100% original text in output PDF, and telemetry `SKIPPED_UNSUPPORTED`. | PASS | Output PDF verified via PyMuPDF: source text untouched, translated string absent, `replaced_blocks == 0`, `skipped_blocks == 1`, `total_cells == 0`. |
| 3. Selective Translation Flow (`test_translation_pipeline_skips_rejected_table_blocks_and_translates_valid_blocks`) | Translation preserves rejected table blocks exactly while translating normal paragraphs and valid table cells. | PASS | `translate_document` ignores `table_rejected` blocks while modifying `text` and `table_cell` blocks as expected. |
| 4. Fail-Closed on Corrupted/Missing Metadata (`test_fail_closed_missing_or_corrupt_metadata`) | Even with empty/corrupted metadata dictionary, blocks tagged `table_rejected` are strictly preserved fail-closed. | PASS | Fallback directly checks `block.block_type == "table_rejected"`; zero redactions and zero replacements occur. |
| 5. Translation Service Boundary Protection (`test_translation_service_spy_verifies_rejected_blocks_never_sent_to_provider`) | Spy provider confirms rejected blocks never reach external or production translation providers. | PASS | Provider seam verified: 0 calls for rejected blocks; normal blocks and valid table cells dispatched cleanly. |
| 6. Boundary & Isolation | Scope strictly limited to Task 4. Zero modifications to cell typesetting or stroke-aware insets (Task 5). | PASS | Cell layout calculation, border stroke insets, and fitting testing untouched; strictly deferred to Task 5. |

---

## 3. Code Quality & Architecture Review

| Dimension | Assessment | Status | Notes |
|:---|:---|:---|:---|
| Interface Cohesion | Clean seam between IR data structures and TranslationService facade. | PASS | `extract_document_segments` uses pure IR and `FormulaIsolator`, preserving decoupled module architecture. |
| Multi-tier Defense | Defense-in-depth at both TranslationService entry and TypesetEngine clearance. | PASS | An unexpected block slipping through translation is still stopped by TypesetEngine without page damage. |
| Fail-Closed Integrity | Complete tolerance for missing/malformed metadata. | PASS | Gracefully handles empty dicts, missing keys, non-set collections. |

---

## 4. Verdict & Readiness

- **Spec Compliance:** APPROVED (All 5 acceptance tests pass; translation seam fully guarded)
- **Code Quality:** APPROVED (Clean, decoupled, 132/132 tests pass)
- **Ready for Task 5:** YES (Base commit `cffa6d5`, pending user approval)
