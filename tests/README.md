# LayoutLingua Test Suite (`tests`)

This directory contains the automated test suite for LayoutLingua, spanning unit tests, integration tests, preservation invariants, and visual regression suites.

## Running Tests

Run the full discovery test suite using Python 3.12:

```bash
# Full test suite discovery
python -m unittest discover -s tests

# Run a specific test module
python -m unittest tests/test_reading_order.py
python -m unittest tests/test_glossary.py
python -m unittest tests/test_translate_pdf.py
```

---

## Test Directory Overview

| Test Module | Coverage Area |
|---|---|
| [`test_reading_order.py`](test_reading_order.py) | Multi-gutter detection, 2-column & 3-column layouts, Spatial DAG directed edges, Kahn's topological sort, cycle resilience. |
| [`test_glossary.py`](test_glossary.py) | `GlossaryManager`, sub-sentence `<gN>` token masking, longest-match priority, JSON/CSV/JSONL loading, thread-zero guards. |
| [`test_translate_pdf.py`](test_translate_pdf.py) | CLI argument parsing, failure reporting, dual output generation (`--dual`), glossary forwarding (`--glossary`), image-only detection. |
| [`test_preservation_rules.py`](test_preservation_rules.py) | Fail-closed preservation detector: TOC, Index, Nomenclature, References, CJK line wrapping rules. |
| [`test_tables.py`](test_tables.py) | Table grid reconstruction, cell extraction, cell text fitting, and GRITS table score evaluation. |
| [`test_formula.py`](test_formula.py) | Invariant formula extraction, MT placeholder normalization, `{vN}` tag protection. |
| [`test_perf_guards.py`](test_perf_guards.py) | Circuit breaker, exponential backoff with jitter, HTTP 429 Retry-After header parsing, rate limit resilience. |
| [`test_typesetting.py`](test_typesetting.py) | Adaptive typesetting constraint solver, font scaling, word wrapping. |
| [`test_stitcher.py`](test_stitcher.py) | Cross-page sentence continuation detection and stitching. |
| [`test_batch.py`](test_batch.py) | Segment batching, batch delimiters, individual fallback on mismatch. |
| [`test_checkpoint.py`](test_checkpoint.py) | Resumable document translation checkpoints. |
| [`test_document_ir.py`](test_document_ir.py) | Semantic document intermediate representation (IR). |
| [`test_handoff_translator.py`](test_handoff_translator.py) | Offline JSONL segment translation handoff engine. |
| [`test_inline_formula_layout.py`](test_inline_formula_layout.py) | Glyph positioning, font style mapping, inline math rendering. |
| [`test_large_document_finalization.py`](test_large_document_finalization.py) | Large document memory efficiency, font subsetting bypass rules. |
| [`test_app_gui.py`](test_app_gui.py) | Desktop GUI event queue, state transitions, language dropdown. |
| [`test_update.py`](test_update.py) | Self-update version comparison and platform synchronizer. |

---

## Invariant Testing Principles

- **Deterministic Assertions**: No flaky sleep timers; background tasks and threads use synchronization barriers and events.
- **Fail-Closed Verification**: Tests assert that formula corrupted tokens `{vN}` and malformed XML tags raise `FormulaPlaceholderError` and fall back to source text.
