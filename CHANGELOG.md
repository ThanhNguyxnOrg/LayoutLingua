# 📋 Changelog & Release Notes

<p align="left">
  <img src="https://img.shields.io/badge/Version-v1.0.0-blue?style=flat-square" alt="Version 1.0.0">
  <img src="https://img.shields.io/badge/Release_Status-Production_Ready-brightgreen?style=flat-square" alt="Production Ready">
  <img src="https://img.shields.io/badge/SemVer-2.0.0-informational?style=flat-square" alt="SemVer">
</p>

All notable changes to **LayoutLingua** across Windows, macOS, Linux, and Android are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-09-05 — The Genesis Release 🚀✨

> **LayoutLingua v1.0.0** is the world-class, SOTA scientific document layout & math preservation translation engine. Designed from foundational research of ACL 2026 (BabelDOC), IBM Research (Docling), Surya, Marker, TATR, and PDFMathTranslate.

### 🌟 Highlights & Key Innovations

* 📐 **100% Vector Geometry & Operator Preservation**: Formulas are never rasterized into blurry images; native PDF vector streams are preserved with bit-level accuracy.
* 🧠 **Topological Reading Order DAG**: Multi-column whitespace gutter slicing and topological sorting prevent cross-column text bleeding and order jumping.
* 📊 **Structure-Aware Table Isolation**: Cell-level coordinate containment with automatic protection for numeric values, p-values, tolerances, currencies, and chemical units.
* 🛡️ **Absolute Fail-Closed Safety**: In the event of a damaged token or ambiguity, source text is preserved rather than corrupting formatting or math.
* ⚡ **70% Network Overhead Reduction**: High-throughput translation batching pipeline with automatic segment serialization.
* 🌐 **Universal Coverage for 48 Languages**: Comprehensive typography support for Vietnamese stacked tone marks, CJK ideographs, Cyrillic, Arabic, Hebrew, and European Latin scripts.

---

### 🚀 Core Architecture & Features

#### 🧠 Semantic Document Intermediate Representation (IR)
* 🧩 **Decoupled 3-Stage IR (`pdf2zh/ir.py`)**: Implemented `DocumentIR`, `PageIR`, `ParagraphIR`, `RunIR`, `TableIR`, `CellIR`, and `FormulaIR`.
* 💾 **Lossless JSON Interchange**: Export and import document models conforming to BabelDOC ACL 2026 and Docling specifications.
* 🎯 **Semantic Role Labeling**: High-precision tags (`TITLE`, `HEADING`, `PROSE`, `TABLE`, `CELL`, `FORMULA`, `CAPTION`, `FOOTNOTE`) tethered to physical bounding boxes.

#### 📐 Layout & Reading Order Intelligence
* 🔍 **Gutter Detection & Column Slicing (`pdf2zh/reading_order.py`)**: Automated vertical whitespace analysis eliminating reading order jumping across multi-column layouts (addressing Docling #3422).
* 🔄 **Topological Sorting Graph (DAG)**: Computes strict linear reading sequences while respecting cross-column banner barriers (titles, abstracts, wide equations).
* 🔗 **Cross-Page Paragraph Stitcher (`pdf2zh/stitcher.py`)**: Seamlessly connects sentences that wrap across page boundaries to ensure coherent document-level MT context.

#### 📊 Structure-Aware Table Engine & Cell Fitting
* 🗂️ **Cell Boundary Containment (`pdf2zh/tables.py`)**: Independent cell extraction preserving table grid lines, borders, and striped alternating fills.
* 🔒 **Data & Unit Protection Shield**: Automated detection for numerical ranges (`$1,250.00 ± 0.05%`), p-values (`p < 0.001`), temperature (`25°C`), and chemical formulas (`H2O`, `CaCO3`) to prevent accidental translation into data columns.
* 📈 **GriTS Structural Integrity Scoring**: Automated calculation of table precision and recall inspired by CVPR 2022 PubTables-1M metrics.

#### 📐 Mathematics & Formula Protection Normalizer
* 🛡️ **Zero-Loss Vector Preservation**: Inline and block formulas remain native PDF streams without quality loss or OCR re-rendering.
* 🩹 **Heuristic MT Formatting Repair (`pdf2zh/formula.py`)**: Automatically repairs spaces inserted by MT engines into placeholder tags (`< b 1 >` → `<b1>`), HTML entity escapes (`&lt;b1&gt;` → `<b1>`), and recovers generic style closures (`</s1>`, `</s2>`).
* 🔀 **Grammar-Aware Tag Reordering**: Allows natural grammatical permutations between languages while maintaining strict tag balance.

#### ⚡ Performance, Resilience & Batch Pipeline
* 📦 **Bulk Translation Batcher (`pdf2zh/batch.py`)**: Bundles paragraphs using delimiter `\n\n===LL_SPLIT===\n\n`, slashing network requests by up to 70% with automatic formula isolation.
* 💾 **Atomic Disk Checkpointing (`pdf2zh/checkpoint.py`)**: Zero-loss session resumption (`.checkpoint.json`) for large monographs and textbooks (100–1000+ pages) preventing lost quota on network dropouts (addressing Marker #885).
* 📝 **Transparent Defect Manifest**: Complete audit report detailing every segment kept in the source language and its explicit technical reason (addressing Immersive Translate #3874).
* 📚 **Global Terminology Glossary (`pdf2zh/glossary.py`)**: User-customizable CSV/JSON glossary matching with acronym auto-extraction (`CNN`, `LSTM`, `BLEU`, `GPU`).

#### 🎨 Desktop & Mobile Experience
* 🖥️ **Dark Obsidian Desktop GUI (`app/gui.py`)**: Premium high-contrast dark theme built with CustomTkinter, featuring real-time progress meters, smooth drag-and-drop file queueing, and new vector upload illustration.
* 📋 **In-App What's New & Changelog Viewer**: One-click interactive modal displaying release notes and project updates.
* 🎖️ **Credits & Open-Source Acknowledgements**: Built-in attribution honoring foundational open-source and research works.
* 🐞 **One-Click GitHub Issue Tracker**: Auto-detects system diagnostics (OS, Python, PyMuPDF) and launches pre-filled issue templates with error log copying.
* 📱 **Native Android Companion**: Android app with Google Translate integration and PDFBox layout preservation engine.

---

### 📦 Synchronized Multi-Platform Release Assets

| Platform | Package Format | Architecture | Filename |
| :--- | :--- | :--- | :--- |
| **Windows** | Portable Zip | x86_64 | `LayoutLingua-windows-x86_64.zip` |
| **Linux** | Tarball | x86_64 | `LayoutLingua-linux-x86_64.tar.gz` |
| **macOS (Apple Silicon)** | Disk Image (DMG) | ARM64 (M1/M2/M3/M4) | `LayoutLingua-macos-apple-silicon.dmg` |
| **macOS (Intel)** | Disk Image (DMG) | x86_64 | `LayoutLingua-macos-intel.dmg` |
| **Android** | APK | Universal (ARM & x86) | `LayoutLingua-android-universal.apk` |

---

[1.0.0]: https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/tag/v1.0.0
