# Task 6 Brief — Page-Level Transactional Staging & Rollback

## 1. Overview & Context
- **Slice:** Slice 4C.2 — Table Cell Isolation & Grid Protection
- **Task:** Task 6 — Page-Level Transactional Staging & Rollback
- **Base Commit:** `e660676`
- **Dependencies:** Task 1 (`table_models`), Task 2 (`TableGridValidator`), Task 3 (`TableCellPartitioner`), Task 4 (`BlockSuppressionPipeline` & `TranslationService`), Task 5 (`CellInsets` & Stroke-Aware Insets).

---

## 2. Objectives & Specifications

### 2.1 Single-Page Isolated Staging
- Typeset each document page on an isolated single-page PyMuPDF scratch document (`staging_doc`).
- Scratch document is constructed by copying `source_doc[source_page_index]` via:
  ```python
  staging_doc = pymupdf.open()
  staging_doc.insert_pdf(source_doc, from_page=source_page_index, to_page=source_page_index)
  ```
- All clearance calculations, font registrations, redactions, and binary search insertions occur strictly on `staging_doc[0]`.
- The source document and source PDF bytes remain 100% pristine and unmodified.

### 2.2 Clean Rollback & Zero Partial Mutations
- If an unhandled exception or critical error occurs during staging:
  - The contaminated `staging_doc` is immediately discarded.
  - A fresh, pristine single-page fallback document is constructed:
    ```python
    fallback_doc = pymupdf.open()
    fallback_doc.insert_pdf(source_doc, from_page=source_page_index, to_page=source_page_index)
    ```
  - Zero partial redactions, half-typeset text, or visual corruption persist.

### 2.3 Indexing & Telemetry Contract
- Strict Invariant:
  $$\text{page\_number} == \text{source\_page\_index} + 1$$
  - `page_number`: 1-indexed (used for PageIR, Telemetry, and user-facing reporting).
  - `source_page_index`: 0-indexed (used for PyMuPDF indexing: `source_doc[source_page_index]`, `insert_pdf`).
- Output Contract:
  ```python
  @dataclass(slots=True)
  class PageTransactionResult:
      page_number: int
      source_page_index: int
      staging_doc: pymupdf.Document
      is_fallback: bool
      details: list[BlockFittingDetail]
      summary: PageFittingSummary
  ```
- Telemetry Commit Gate:
  - When `is_fallback == False`: details contain `BlockFittingStatus.SUCCESS` (or specific block skips/overflows).
  - When `is_fallback == True`:
    - `summary.transaction_fallback_blocks` reflects the reverted candidate blocks.
    - If cells were candidates, `summary.transaction_fallback_cells` reflects reverted cells.
    - `details` contains `status=BlockFittingStatus.TRANSACTION_FALLBACK`.
    - No false `SUCCESS` records exist in `details`.

---

## 3. TDD Acceptance Test Plan

1. `test_page_transaction_staging_success`: Verify successful staging returns `is_fallback=False`, invariant `page_number == source_page_index + 1`, and translated text on `staging_doc[0]`.
2. `test_page_transaction_indexing_contract_multipage`: Verify invariant holds across multi-page indices (e.g. page 2 -> source_page_index 1).
3. `test_page_transaction_rollback_on_exception`: Verify unhandled error during staging cleanly rolls back to pristine source page with `is_fallback=True`.
4. `test_page_transaction_fallback_telemetry_accuracy`: Verify rollback telemetry logs `transaction_fallback_blocks`, zero false `SUCCESS` statuses in details.
5. `test_page_transaction_zero_source_mutation`: Verify staging operations leave `source_doc` bytes completely unmodified.

---

## 4. Worktree & Commit Constraints
- Commit message: `feat(typesetting): implement page-level transactional staging and rollback`.
- Regression check: 138 existing tests + new Task 6 acceptance tests = 143+ PASS.
