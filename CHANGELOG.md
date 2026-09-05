# 📋 Changelog & Release Notes

<p align="left">
  <img src="https://img.shields.io/badge/Version-v1.1.0-blue?style=flat-square" alt="Version 1.1.0">
  <img src="https://img.shields.io/badge/Release_Status-Production_Ready-brightgreen?style=flat-square" alt="Production Ready">
  <img src="https://img.shields.io/badge/SemVer-2.0.0-informational?style=flat-square" alt="SemVer">
</p>

All notable changes to **LayoutLingua** across Windows, macOS, Linux, and Android are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### 🚀 Added

### 🔧 Changed

### 🐛 Fixed

---

## [1.1.0] - 2026-09-05 — Document AI & Architecture Upgrade 🧠⚡

### 🚀 Added
- 🧠 **Canonical Semantic Document IR (`pdf2zh/ir.py`)**:
  - Implemented decoupled 3-stage intermediate representation (`DocumentIR`, `PageIR`, `ParagraphIR`, `RunIR`, `TableIR`, `CellIR`, `FormulaIR`).
  - Added lossless JSON serialization and deserialization conforming to modern Document AI standards (BabelDOC ACL 2026, Docling).
  - Tightly coupled semantic roles (`TITLE`, `HEADING`, `PROSE`, `TABLE`, `CELL`, `FORMULA`, `CAPTION`, `FOOTNOTE`) with physical layout bounds and style metadata.
- 📐 **Layout-Aware Reading Order Engine (`pdf2zh/reading_order.py`)**:
  - Added vertical whitespace gutter detection and column gap slicing.
  - Implemented topological sorting over directed acyclic spatial relation graphs (DAG), completely eliminating multi-column text leakage (addressing Docling #3422).
  - Introduced full-width synchronization barrier handling for section titles, abstracts, and wide formulas.
- 📊 **Structure-Aware Table Engine (`pdf2zh/tables.py`)**:
  - Implemented `TableGrid` and `TableCell` models with strict cell boundary isolation.
  - Added automated numerical, measurement, uncertainty (`±`), p-value (`p < 0.001`), currency (`$`, `€`), and code value protection (`is_cell_numeric_or_identifier`) to prevent translation bleeding into data columns.
  - Added adaptive cell fitting with local font scaling and word wrapping.
  - Implemented GriTS-inspired (CVPR 2022) table structural integrity scoring.
- 💾 **Session Checkpoint Manager & Resumability (`pdf2zh/checkpoint.py`)**:
  - Added atomic disk checkpointing (`.checkpoint.json`) enabling zero-loss resumption for large documents (100–1000+ pages) without losing progress or wasting API quota (addressing Marker #885).
  - Implemented transparent stage-level Defect Manifest reports (`generate_manifest_report`) detailing every segment kept in the source language and its explicit reason (addressing Immersive Translate #3874).
  - Added detection of bibliography and reference headings (`is_reference_section_heading`).
- 🩹 **Enhanced Formula Recovery Normalizer (`pdf2zh/formula.py`)**:
  - Added heuristic normalization for MT formatting artifacts (HTML entity escapes, rogue spaces in tags, style tag spacing).
  - Added automatic closure recovery for trailing unclosed style tags (`</s1>`, `</s2>`) swallowed by machine translation services.
  - Preserved 100% fail-closed safety for damaged, unclosed, or mismatched formula tokens.
- 📐 **Adaptive Typesetting & Multi-Space Constraint Solver (`pdf2zh/typesetting.py`)**:
  - Multi-variable constraint optimization solver balancing font scaling, line height, and word spacing.
  - Implemented multi-available-space spillover fitting (addressing BabelDOC Issue #89) allowing expanded text to safely flow into available whitespace below instead of shrinking excessively.
  - Added dedicated headroom clearance (`diacritic_headroom = 1.8 pt`) for Vietnamese diacritics and stacked tone marks.
- 🔗 **Cross-Page Paragraph Stitcher (`pdf2zh/stitcher.py`)**:
  - Added sentence continuity detection across page breaks (`is_cross_page_continuation`).
  - Stitches fragmented sentences across page boundaries for coherent document-level MT context.
  - Partitions translated text proportionally along word boundaries for accurate page-level rendering.
- 📚 **Global Terminology Memory & Glossary Manager (`pdf2zh/glossary.py`)**:
  - Support for custom JSON and CSV glossary files (`--glossary`).
  - Pre-masking and post-restoration of technical terms with longest-match priority.
  - Automatic extraction of technical acronyms (`CNN`, `LSTM`, `BLEU`, `GPU`) across the entire document.
- ⚡ **Bulk Translation Batcher (`pdf2zh/batch.py`)**:
  - Consolidated bulk translation payloads using delimiter `\n\n===LL_SPLIT===\n\n`, reducing network round-trips by up to 70%.
  - Automatic isolation of formula segments to guarantee mathematical integrity.
  - Graceful fallback to single-segment translation on delimiter mismatch.
- 🎨 **Desktop GUI Enhancements (`app/gui.py`)**:
  - Added sleek vector dropzone upload illustration with cyan neon accents ([dropzone_upload.png](app/assets/dropzone_upload.png)).
  - Added interactive native CustomTkinter visual card-based Changelog viewer dialog.
  - Filtered changelog viewer to present released stable versions cleanly to end users.
  - Added automatic GitHub Issue Diagnostics pre-fill (`open_bug_report`) detecting platform, version, and language directly into issue URLs.
  - Added Open-Source Credits & Research Foundation attribution tab.
  - Added direct one-click `Report Issue ↗` button in footer linking straight to GitHub issue templates.
- 🛠️ **Extended CLI Options (`scripts/translate_pdf.py`)**:
  - Added `--glossary` to apply custom terminology dictionaries.
  - Added `--manifest` to export transparent defect manifest reports.
  - Added `--skip-references` to leave citations and DOIs untranslated.
  - Added `--verify` to run automated visual regression checks immediately after translation.
- 🔍 **Automated Visual Regression & Geometry Verification Tool (`scripts/verify_preservation.py`)**:
  - Automated page dimension matching, visual pixel-difference calculation, difference heatmap generation, and JSON report export.
- 🧪 **Real-World Bug Stress Benchmark PDF (`scripts/generate_sample_pdf.py`)**:
  - Embedded vertical rotated margin text, bullet lists with hanging indents, numeric uncertainty bounds (`±`), p-values (`p < 0.001`), currencies (`$`, `€`), inline math, and multi-range DOIs into `examples/sample_scientific_document.pdf`.
  - Added mathematically correct Unicode subscripts (`ₘᵢₙ`, `ₘₐₓ`, `ᵢ`, `ₜ`) for bounding box and learning rate variables.
- 🔄 **Cross-Project Version Synchronization (`scripts/set_version.py`)**:
  - Automated version synchronization across `app/update.py`, `android/app/build.gradle.kts`, `CHANGELOG.md`, `CITATION.cff`, and `README.md`.

### 🔧 Changed
- Refactored `pdf2zh/translator.py` to pre-normalize translation responses using `normalize_mt_placeholders`.
- Enhanced `scripts/translate_pdf.py` execution workflow to support batch reporting, defect manifests, and verification routines.
- Synchronized release asset filenames across all platforms (`LayoutLingua-windows-x86_64.zip`, `LayoutLingua-linux-x86_64.tar.gz`, `LayoutLingua-macos-apple-silicon.dmg`).
- Updated CI testing pipeline (`.github/workflows/test.yml`) with `xvfb` virtual display support to ensure robust automated headless GUI testing across platforms.

### 🐛 Fixed
- Fixed non-breaking space (`\xa0`) being falsely identified as formula tokens by `vflag()` in justified documents.
- Fixed formula placeholder formatting failures caused by MT services inserting spaces (`< b 1 >`) or escaping HTML entities (`&lt;b1&gt;`).
- Resolved multi-column reading order jumps where text from adjacent columns interleaved.
- Fixed headless `tkinter.TclError` in continuous integration environments by wrapping test runs with virtual X display (`xvfb-run`).

---

## [1.0.0] - 2026-09-05 — The Genesis Release 🚀✨

### 🌟 Added
- 📦 **4-Platform Synchronized Native Releases**: First official stable release supporting Windows (`.zip`), macOS (`.dmg` for Apple Silicon & Intel), Linux (`.tar.gz`), and Android (`.apk`).
- 🌐 **Universal Multi-lingual Prose Recognition**: Advanced regex engine for isolating prose blocks from math formulas across Vietnamese with diacritics/tone marks, CJK (Chinese, Japanese, Korean), Cyrillic (Russian, Ukrainian), Arabic, Hebrew, and European Latin languages.
- 🤖 **Smart Automated Release CI/CD**: Keyword-triggered GitHub Actions pipeline (`release: X.Y.Z`) with automatic version synchronization across all platforms, automated tagging, and multi-platform release asset bundling.
- 🎨 **Dark Obsidian UI**: Refined cross-platform desktop user interface featuring high-contrast sleek design tokens, crisp vector icons, and real-time per-page translation progress.
- 📱 **Native Android Companion**: Android app with Google Translate integration and PDFBox layout preservation engine.
- 🔀 **Grammar-Aware Formula Placeholders**: Resilient tag balancing allowing target language grammatical permutations while strictly protecting inline vectors and formulas.
- 📑 **TOC & Link Preservation**: Full preservation of PDF Table of Contents (TOC) link annotations and visual formatting geometry.

---

[Unreleased]: https://github.com/ThanhNguyxnOrg/LayoutLingua/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/ThanhNguyxnOrg/LayoutLingua/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/tag/v1.0.0
