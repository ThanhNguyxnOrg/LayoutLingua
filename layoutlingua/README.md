# LayoutLingua Core Engine (`layoutlingua`)

The `layoutlingua` package provides the core document translation, layout preservation, spatial reading-order inference, and formula recovery engine for LayoutLingua.

## Architecture Overview

```
                                      [Input PDF]
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │ high_level.translate │
                                └──────────┬───────────┘
                                           │
                     ┌─────────────────────┴─────────────────────┐
                     ▼                                           ▼
          ┌─────────────────────┐                     ┌─────────────────────┐
          │ doclayout.OnnxModel │                     │ rules.classify_page │
          │  (DocLayout-YOLO)   │                     │  (TOC/Ref/Index/...)│
          └──────────┬──────────┘                     └──────────┬──────────┘
                     │                                           │
                     ▼                                           │
          ┌─────────────────────┐                                │
          │ reading_order.py    │                                │
          │ (Spatial DAG Engine)│                                │
          └──────────┬──────────┘                                │
                     │                                           │
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                               ┌──────────────────────┐
                               │ TranslateConverter   │
                               │  (converter.py)      │
                               └──────────┬───────────┘
                                          │
                 ┌────────────────────────┼────────────────────────┐
                 ▼                        ▼                        ▼
      ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
      │ formula / vflag      │ │ glossary.py          │ │ batch.py             │
      │ LaTeX placeholder    │ │ Sub-term masking     │ │ Multi-segment        │
      │ protection {vN}      │ │ <gN> / exact match   │ │ batching             │
      └──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘
                 │                        │                        │
                 └────────────────────────┼────────────────────────┘
                                          │
                                          ▼
                               ┌──────────────────────┐
                               │ translator.py        │
                               │ (Google/DeepLX/...)  │
                               └──────────┬───────────┘
                                          │
                                          ▼
                               ┌──────────────────────┐
                               │ typeset & font-scale │
                               │ (typesetting.py)     │
                               └──────────┬───────────┘
                                          │
                                          ▼
                              [Output Translated PDF]
```

---

## Core Modules

| Module | Purpose |
|---|---|
| [`high_level.py`](high_level.py) | Main translation orchestration (`translate`, `translate_stream`), PDF/A conversion, document repair, page classification. |
| [`converter.py`](converter.py) | `TranslateConverter`, paragraph construction (`pstk`), line wrapping, visual glyph extraction, coordinate transformation. |
| [`reading_order.py`](reading_order.py) | Multi-gutter detection (`detect_column_gutters`), Spatial DAG construction, Kahn's topological sort for 2-column & 3-column layouts. |
| [`doclayout.py`](doclayout.py) | ONNX Runtime session management for DocLayout-YOLO document region detection. |
| [`translator.py`](translator.py) | Machine translation backends (Google, DeepLX, Handoff), formula placeholder validation, exponential backoff with jitter. |
| [`glossary.py`](glossary.py) | `GlossaryManager`, sub-sentence terminology masking (`<gN>`), longest-match replacement, acronym extraction. |
| [`batch.py`](batch.py) | `TranslationBatcher`, combines short prose segments into delimiter-separated payloads to minimize HTTP roundtrips. |
| [`rules.py`](rules.py) | Fail-closed preservation detectors (TOC, Index, References, Nomenclature), CJK word break rules, font classification. |
| [`tables.py`](tables.py) | Structure-aware table cell extraction, table grid reconstruction, and text fitting. |
| [`typesetting.py`](typesetting.py) | Adaptive typesetting constraint solver, font scale search (1.0 down to min-scale), margin fitting. |
| [`stitcher.py`](stitcher.py) | Cross-page paragraph continuation detection and unified translation stitching. |
| [`checkpoint.py`](checkpoint.py) | Session checkpointing and resumable state tracking for large multi-page documents. |
| [`cache.py`](cache.py) | Thread-safe SQLite translation memory cache (`~/.cache/layoutlingua/cache.v1.db`). |
| [`ir.py`](ir.py) | Canonical semantic Document Intermediate Representation (IR). |
| [`formula.py`](formula.py) | Invariant LaTeX formula extraction, MT placeholder normalization, and recovery. |
| [`pdfinterp.py`](pdfinterp.py) | Extended PDF page interpreter preserving background graphics and vector drawings. |

---

## Key Invariants

1. **Fail-Closed Formula Preservation**: Any translation result that drops, duplicates, or mangles `{vN}` formula tokens is rejected; the source text is preserved unchanged.
2. **Column Isolation**: Text across column gutters is never interleaved or grouped into a single paragraph.
3. **Deterministic Reading Order**: Reading order is determined by topological sorting over spatial precedence edges, never by raw PDF content stream order.
4. **Thread Safety**: Workers are guaranteed `thread >= 1` and shared caches use process/thread locks.
