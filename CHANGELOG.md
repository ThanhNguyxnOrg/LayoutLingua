# 📋 Changelog & Release Notes

<p align="left">
  <img src="https://img.shields.io/badge/Version-v1.0.0-blue?style=flat-square" alt="Version 1.0.0">
  <img src="https://img.shields.io/badge/Release_Status-Production_Ready-brightgreen?style=flat-square" alt="Production Ready">
  <img src="https://img.shields.io/badge/SemVer-2.0.0-informational?style=flat-square" alt="SemVer">
</p>

All notable changes to **LayoutLingua** across Windows, macOS, Linux, and Android are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Canonical Semantic Document IR (`pdf2zh/ir.py`)**: Unified intermediate representation decoupling layout geometry from linguistic content with lossless JSON serialization.
- **Layout-Aware Reading Order Engine (`pdf2zh/reading_order.py`)**: Column slicing, vertical gutter analysis, and topological sorting to eliminate multi-column reading jumps.
- **Structure-Aware Table Engine (`pdf2zh/tables.py`)**: Cell-level boundary isolation, automatic numerical/unit protection, adaptive cell fitting, and GriTS structural similarity scoring.
- **Resilience & Session Checkpoint Manager (`pdf2zh/checkpoint.py`)**: Atomic session persistence for large documents (100–1000+ pages), instant crash resumption, and transparent defect manifests.
- **Enhanced Formula Recovery Normalizer (`pdf2zh/formula.py`)**: Heuristic MT artifact repair (HTML entities, rogue tag spaces) with 100% fail-closed safety for damaged formulas.
- **Adaptive Typesetting & Multi-Space Constraint Solver (`pdf2zh/typesetting.py`)**: Multi-variable fitting with safe whitespace spillover (addressing BabelDOC #89) and diacritic headroom clearance.
- **Cross-Page Paragraph Stitcher (`pdf2zh/stitcher.py`)**: Sentence boundary continuity detection across page breaks with proportional word-boundary rendering.
- **Document-Level Terminology Memory (`pdf2zh/glossary.py`)**: Global glossary enforcement supporting JSON/CSV dictionaries and automatic technical acronym discovery.
- **Bulk Translation Batcher (`pdf2zh/batch.py`)**: Multi-segment bulk translation with special delimiters, reducing HTTP requests by 70% while protecting formula markers.
- **CLI Options (`scripts/translate_pdf.py`)**: New flags `--glossary`, `--manifest`, `--skip-references`, and `--verify`.

## [1.0.0] - 2026-09-05

### Added
- **4-Platform Native Releases**: First official stable release supporting Windows (`.zip`), macOS (`.dmg` for Apple Silicon & Intel), Linux (`.tar.gz`), and Android (`.apk`).
- **Universal Multi-lingual Prose Recognition**: Advanced regex engine for isolating prose blocks from math formulas across Vietnamese with diacritics/tone marks, CJK (Chinese, Japanese, Korean), Cyrillic (Russian, Ukrainian), Arabic, Hebrew, and European Latin languages.
- **Smart Automated Release CI/CD**: Keyword-triggered GitHub Actions pipeline (`release: X.Y.Z`) with automatic version synchronization across all platforms, automated tagging, and multi-platform release asset bundling.
- **Dark Obsidian UI**: Refined cross-platform desktop user interface featuring high-contrast sleek design tokens, crisp vector icons, and real-time per-page translation progress.
- **Native Android Companion**: Android app with Google Translate integration and PDFBox layout preservation engine.
- **Grammar-Aware Formula Placeholders**: Resilient tag balancing allowing target language grammatical permutations while strictly protecting inline vectors and formulas.
- **TOC & Link Preservation**: Full preservation of PDF Table of Contents (TOC) link annotations and visual formatting geometry.

[1.0.0]: https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/tag/v1.0.0

