# LayoutLingua Documentation

This directory contains technical architecture documentation, decision records (ADRs), research analyses, and development guides for the LayoutLingua translation and layout-preservation engine.

## Table of Contents

- [Core Architecture](#core-architecture)
- [Architecture Decision Records (ADRs)](#architecture-decision-records-adrs)
- [Technical Research](#technical-research)
- [Implementation Plans](#implementation-plans)
- [Platform & Build Guides](#platform--build-guides)

---

## Core Architecture

- **[Architecture Roadmap](architecture-roadmap.md)**: High-level system architecture, engine pipeline milestones, translation concurrency, and quality assurance framework.
- **[Development Guide](development.md)**: Local developer setup, Python 3.12 virtual environment, testing workflow, and coding conventions.
- **[Web Architecture](web-architecture.md)**: Architecture design for web integration and document translation endpoints.
- **[Android Release](android-release.md)**: Android client architecture, build instructions, and local ONNX runtime bundling.

---

## Architecture Decision Records (ADRs)

Documented architectural choices in `docs/adr/`:

- **[0001: Spatial DAG Reading Order and Multi-Column Splitting](adr/0001-spatial-dag-reading-order-and-column-splitting.md)**: Hybrid approach using multi-gutter projection scanning, 2D slice partitioning, and Kahn's topological sort over spatial relation graphs to eliminate cross-column interleaving.

---

## Technical Research

Deep-dive research reports and comparative analyses in `docs/research/`:

| Topic | Document | Focus |
|---|---|---|
| **Reading Order & Columns** | [`reading-order-and-column-preservation.md`](research/reading-order-and-column-preservation.md) | BabelDOC (`layoutreader`), Surya/Marker Recursive XY-Cut, and Docling reading order integration. |
| **Formula Preservation** | [`chinese-formula-repos.md`](research/chinese-formula-repos.md) | LaTeX font detection (`vflag`), formula grouping, and placeholder token recovery. |
| **Rate Limit Mitigations** | [`429-mitigations.md`](research/429-mitigations.md) | Adaptive exponential backoff, jitter, and HTTP 429 Retry-After handling. |
| **Column Splitting** | [`column-split.md`](research/column-split.md) | Vertical gutter projection analysis and multi-column bounding box partitioning. |
| **Translation Engine Benchmarks** | [`opensource-translation.md`](research/opensource-translation.md) | Evaluation of Google Translate, DeepLX, LibreTranslate, and Handoff engines. |
| **Concurrency & Pooling** | [`pool-android.md`](research/pool-android.md) | ThreadPoolExecutor resource limits and cross-platform process pooling. |
| **Performance Optimizations** | [`followup-optimizations.md`](research/followup-optimizations.md) | Latency analysis, caching layers, and throughput improvements. |
| **Performance Regressions** | [`review-slowness.md`](research/review-slowness.md) | Investigation of PDF font embedding bottlenecks and GIL contention. |
| **Translation Unblocking** | [`unblock-translation.md`](research/unblock-translation.md) | Fail-closed preservation, circuit breakers, and timeout policies. |

---

## Implementation Plans

Detailed action plans in `docs/plans/`:

- **[2026-10-09 Retry Jitter & Retry-After](plans/2026-10-09-retry-jitter-retry-after.md)**: Implementation plan for resilient network retry policies across MT backends.
