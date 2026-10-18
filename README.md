# LayoutLingua

<div align="center">

> **State-of-the-Art Academic & Technical PDF Translation Engine** with strict typography geometry preservation, mathematical formula shielding, and deep transactional typesetting.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Test Suite](https://img.shields.io/badge/tests-245%20passed-brightgreen.svg)](tests/)
[![Tauri 2.0](https://img.shields.io/badge/desktop-Tauri%20v2%20%2B%20React%2019-teal.svg)](desktop/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Vision Engine](https://img.shields.io/badge/Vision%20Engine-DocLayout--YOLO%20(ONNX)-green.svg)](https://github.com/opendatalab/DocLayout-YOLO)

[Key Features](#-key-features--architectural-innovations) •
[Installation & Quickstart](#-installation--quickstart) •
[Architecture](#-system-architecture) •
[Benchmarks](#-benchmarks--competitive-comparison) •
[Contributing](#-contributing) •
[License](#-license)

</div>

---

## 🌟 Overview

Translating academic and technical PDFs (papers, textbooks, engineering specifications) is notoriously difficult: standard machine translation destroys multi-column layouts, breaks mathematical equations, splits fractions, and replaces vector diagrams with corrupted visual artifacts.

**LayoutLingua v2.0.0** synthesizes the best design patterns from leading open-source projects (**pdf2zh**, **BabelDOC**, **MinerU**, and **Marker**) into a unified **Deep Module architecture**. It delivers 100% vector graphic preservation, robust mathematical shielding, and automated typographical fitting.

---

## 🚀 Key Features & Architectural Innovations

### 1. Cluster-Level Formula Clearance & Zero Collision Fallback
- **Spatial Span Clustering**: Unlike naive bounding-box union approaches that bridge across multi-line grouping braces (`}`) or fraction bars ($\frac{a}{b}$), LayoutLingua groups glyph spans by baseline alignment ($\le 3.5\text{pt}$) and horizontal proximity ($\le 6.0\text{pt}$).
- **Non-Contracting Layout Expansion**: The expansion algorithm expands single-line and multi-line paragraphs into available right-margin whitespace without ever contracting below the original text width ($x_1$).
- **Zero False-Positive Warnings**: Empirically verified to produce **0 warnings** on complex technical benchmarks (e.g., Pages 1–25 of `Sotaytoanhoc.pdf`).

### 2. Mathematical Symbol & Equation Shielding
- **TeX & Math Font Detection**: Recognizes Computer Modern (`CM[^R]`), AMS, Symbol, and MathType glyphs.
- **Invariant Token Isolation**: Shields equations into opaque tokens (`<b0></b0>`, `⟦LL_FORMULA_N⟧`) before sending them to neural translation providers, preventing LLM equation hallucinations.
- **Self-Healing Token Recovery**: Automatically normalizes and repairs mangled tag syntax, whitespace distortions, and attached punctuation.

### 3. Adaptive Font Downscaling & Elastic Sizing Floors
- **Binary Search Fitting**: Computes optimal font size using sub-pixel binary search combined with dynamic line-height calculation.
- **Elastic Floors for Single-Line Text**: Enables scaling down to `0.50x` (floor `5.0pt`) for single-line math labels and Table of Contents entries, preventing catastrophic vertical wrapping.
- **LaTeX `\dotfill` TOC Harmonization**: Dynamically calculates dot leaders (`.....`) to ensure page numbers align perfectly to the right margin across sibling entries.

### 4. True Bold Font Typography & Heading Casing
- **Bundled TrueType Assets**: Version-pinned `DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` provide full Unicode glyph coverage for mathematical symbols and composite Vietnamese diacritics.
- **Dynamic Bold Mapping**: Automatically resolves and upgrades bold font spans to true bold font files.
- **Heading Casing Preservation**: Preserves uppercase casing (e.g., `V. LƯỢNG GIÁC` $\rightarrow$ `V. TRIGONOMETRY`) to maintain document hierarchy.

### 5. Multi-Provider Translation Pipeline
- **Google Translate RPC (Zero Setup)**: Out-of-the-box translation with intelligent batch packing, zero API key requirements, and rate-limit backoff.
- **Universal OpenAI-Compatible**: Seamlessly connects to OpenAI (GPT-4o, o3-mini), Groq, DeepSeek, and local offline models (Ollama, LM Studio, vLLM) with automatic `/models` discovery.
- **Google AI Studio (Gemini)**: Native support for Gemini 2.5 Flash with privacy disclosure tracking.
- **Argos Translate (100% Offline)**: Complete on-device neural translation using OpenNMT with **zero network connectivity** and zero data leakage.

### 6. Persistent On-Disk Segment Cache
- **ACID SQLite Cache (`translations.db`)**: Indexed by deterministic SHA-256 fingerprint (`source_lang + target_lang + provider + masked_text`).
- **Instantaneous Resumption**: Resuming interrupted sessions or re-translating documents takes `< 0.1s` with zero redundant API calls.

### 7. Modern Tauri 2.0 Desktop Application
- **Zero-Window Python Lifecycle**: Native desktop application (React 19 + TypeScript) that automatically manages the Python backend with zero background console window popups.
- **Dual Synchronized View & Alpha Blend Overlay**: Side-by-side synchronized comparison and an interactive 0–100% opacity slider to inspect layout fidelity.
- **Quality Checks & One-Click Diagnostic Export**: Real-time diagnostic tab with a **"Copy log"** button for immediate structured LLM triage.

---

## 📊 Benchmarks & Competitive Comparison

| Feature | LayoutLingua v2.0 | pdf2zh (PDFMathTranslate) | Nougat / MinerU | Google Translate Web |
|:---|:---:|:---:|:---:|:---:|
| **Vector Background Art Preservation** | **100% (Lossless)** | 90% (Redaction glitches) | ❌ (Converts to text/MD) | ❌ (Rasterizes image) |
| **Mathematical Equation Shielding** | **Token Isolation + Healing** | Font Pattern Matching | LaTeX OCR | ❌ (Corrupts equations) |
| **Subscript / Fraction Clearance** | **Cluster-Level (0 Warnings)** | Coarse Union Box | N/A | ❌ (Overwrites text) |
| **TOC Dot-Leader Adaptation** | **LaTeX `\dotfill` Dynamic** | ❌ (Ragged line wraps) | N/A | ❌ (Broken page refs) |
| **Offline Privacy Mode** | **Yes (Argos OpenNMT)** | ❌ (Requires Cloud API) | Local OCR Only | ❌ (Cloud Only) |
| **Native Desktop App (Tauri v2)** | **Yes (Windows/macOS/Linux)** | ❌ (Python CLI / Web UI) | ❌ (CLI / Gradio) | Browser Only |
| **Persistent Segment Cache** | **SQLite (SHA-256 Keyed)** | In-memory / File | N/A | None |

---

## 🛠 Installation & Quickstart

### Option A: Native Desktop App (Recommended)

Download the latest standalone installer or executable from [Releases](https://github.com/ThanhNguyxnOrg/LayoutLingua/releases):
- **Windows**: `LayoutLingua_Setup_v2.0.0.exe` or standalone `LayoutLingua.exe`
- **macOS / Linux**: Tauri desktop packages

### Option B: Local Development Setup

#### 1. Clone & Set Up Python Engine
```bash
git clone https://github.com/ThanhNguyxnOrg/LayoutLingua.git
cd LayoutLingua

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

#### 2. Run the Verification Suite
```bash
# Run all 245 automated tests
pytest tests/ -v
```

#### 3. Run the Desktop Client
```bash
cd desktop
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 📐 System Architecture

LayoutLingua separates high-level user workflows from low-level PDF typesetting via strict **Deep Module seams**:

```
[Raw PDF Source]
       │
       ▼
 1. DocumentParser (PyMuPDF + DocLayout-YOLO)
       │  ──> Produces DocumentIR
       ▼
 2. FormulaIsolator
       │  ──> Extracts math tokens (<b0></b0>)
       ▼
 3. TranslationService (Persistent SQLite Cache + Providers)
       │  ──> Translates prose; applies academic glossary
       ▼
 4. TypesetEngine
       │  ──> Cluster-Level Clearance
       │  ──> Non-Contracting Box Expansion
       │  ──> Adaptive Binary Search Fitting
       ▼
 5. DocumentAccumulator
       │  ──> Multi-page transactional commit & TOC relinking
       ▼
[Verified Translated PDF]
```

For complete architectural documentation, module contracts, and design rationales, see:
- [ARCHITECTURE.md](ARCHITECTURE.md) — Comprehensive deep module specifications.
- [CONTEXT.md](CONTEXT.md) — Ubiquitous domain language and terminology.
- [docs/adr/](docs/adr/) — Architectural Decision Records (ADRs).

---

## 🤝 Contributing

Contributions are warmly welcomed! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) guide and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a pull request.

- All pull requests are verified across Ubuntu, Windows, and macOS via GitHub Actions.
- Automated PR merge is powered by **`ThanhNguyxnAgent`**.
- Critical reviews are triaged by the core maintainers: **`@ThanhNguyxnOrg/core`** ([@RealThanhNguyxn](https://github.com/RealThanhNguyxn), [@ThanhNguyxn07](https://github.com/ThanhNguyxn07)).

---

## 📄 License

LayoutLingua is open-source software licensed under the **[MIT License](LICENSE)**.
