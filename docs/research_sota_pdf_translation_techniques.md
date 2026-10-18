# In-Depth Technical Research: State-of-the-Art Techniques in Open-Source Academic PDF Translation

**Primary Source Investigation & Architectural Analysis**  
**Project:** LayoutLingua  
**Surveyed Codebases:** `pdf2zh` (PDFMathTranslate), `BabelDOC`, `MinerU` (Magic-PDF), `Marker` (DataLab), `Nougat` (Meta AI).

---

## 1. Executive Summary

Translating technical, scientific, and mathematical PDF documents while preserving their original visual layout is an inherently complex challenge because the PDF format **completely lacks any semantic concepts of paragraphs, text flow, or equations**. A PDF file is merely an arbitrary stream of absolute coordinate drawing operators (`Tj`, `Tm`, `cm`).

By investigating the official source code and architecture of leading open-source projects, a key architectural principle emerges:
> **Top-tier translation engines DO NOT solve layout preservation by hardcoding hundreds of thousands of static glossary entries into the core engine.**  
> Instead, they solve four fundamental engineering challenges:
> 1. **Formula & Inline Equation Isolation**: Identifying and shielding math expressions without destroying syntax or layout hierarchy.
> 2. **Baseline Fragment Merging**: Reassembling fragmented character spans into coherent sentences before translation.
> 3. **Adaptive Typesetting & Elastic Spacing**: Downscaling and micro-compacting text dynamically to prevent bounding box overflow when translating into longer target languages.
> 4. **Special Element Formatting**: Protecting Table of Contents dot leaders (`.....`) and tabular columns.

---

## 2. Primary Source Analysis of Leading Open-Source Projects

### 2.1. `pdf2zh` (PDFMathTranslate) — 15,000+ ⭐
* **Repository:** `ByByMe/pdf2zh` (formerly `Byaidu/PDFMathTranslate`)
* **Core Architecture:** PyMuPDF (`fitz`) + PDFMiner + DocLayout-YOLO + LLM/NMT.

#### 🎯 Technique 1: Font & Character Heuristics (`--vfont` & `--vchar`)
Rather than relying on heavy AI vision models for every single symbol, `pdf2zh` inspects embedded font tables within each text `span` via PyMuPDF:
```python
# Extracted from pdf2zh codebase:
math_font_regex = r"(CM[^RT].*|MS.*|XY.*|MT.*|BL.*|.*0700|.*0500|.*Math.*|.*Italic)"
math_char_regex = r"(\(|\)|\[|\]|\+|=|\d|[\u0080-\ufaff])"
```
* **Principle**: In LaTeX and ArXiv papers, mathematical variables and symbols are typeset using specialized font families (such as Computer Modern: `CMMI10`, `CMSY10`, MathTime: `MTMI`, MathType). When a span matches these descriptors, `pdf2zh` marks it as an immutable mathematical entity, excluding it from the translation payload.

#### 🎯 Technique 2: Token Masking `[v:N]`
* `pdf2zh` aggregates mathematical formulas (both inline and display math) and replaces them with token identifiers: `[v:0]`, `[v:1]`, `[v:2]`.
* In the system prompt sent to the LLM, `pdf2zh` enforces strict rules:
  > *"Rule 1: Preserve all formatting and placeholders [v:N] exactly. Do not translate, do not remove, do not reorder them."*
* Upon receiving the translated output, it extracts `[v:N]` tokens and re-anchors them back to their original vector coordinates on the PDF page.

---

### 2.2. `BabelDOC` (ACL 2024 / funstory-ai)
* **Repository:** `funstory-ai/BabelDOC`
* **Publication:** ACL 2024 (*"BabelDOC: An Open-Source Framework for Layout-Preserving PDF Translation via Intermediate Representation Layer"* - ArXiv: 2404.13840).

#### 🎯 Technique: Intermediate Representation (IR Layer) & 2-Step Adaptive Typesetting
BabelDOC decouples the extraction and typesetting phases using an explicit `Intermediate Representation (IR)`:

```
[Raw PDF] ──► [IR Extractor] ──► [IR Document (JSON / Decoupled Data Objects)]
                                          │
                                    [Translator]
                                          ▼
[Translated PDF] ◄── [Adaptive Typesetter] ◄── [Translated IR]
```

#### 🎯 BabelDOC Adaptive Typesetting Algorithm:
When text expands in translation (e.g., Vietnamese or German expanding 25–35% compared to English):
1. **Step 1 (Line Wrapping & Typesetting Units):** Computes the paragraph bounding box, setting words horizontally and auto-wrapping at the right boundary.
2. **Step 2 (Dynamic Tightening Floor):** If the translated paragraph vertically overflows the original bounding box:
   - First, **tightens line spacing (line height)** down to a minimum ratio (e.g., from `1.4` to `1.15`).
   - Second, **downscales font size in `0.5pt` increments** (down to a maximum shrink ratio of 70%, with a hard floor of `min_font = 7.0pt`).
   - Third, expands the bounding box vertically into available white space below (Margin Expansion) before triggering fallback.

---

### 2.3. `MinerU` (Magic-PDF / OpenDataLab)
* **Repository:** `opendatalab/MinerU`
* **Components:** Math Formula Detection (YOLO-MFD) + UniMERNet (Math Formula Recognition) + LayoutReader.

#### 🎯 Technique: Inline vs. Display Math Separation & Baseline Stitching
In `mineru/backend/pipeline/para_split.py`, MinerU addresses baseline jitter caused by sub/superscripts:
* **The Problem**: When a line contains math symbols (such as $C_n^k$), PyMuPDF detects baseline vertical offsets, fragmenting what should be a single line into 3–5 fragmented text blocks:
  - Block 1: `"Number of combinations"`
  - Block 2: `"C_n^k"`
  - Block 3: `"elements from n elements is:"`
* **MinerU Solution (Span-Level Baseline Stitching)**:
  MinerU inspects the Y-coordinates of adjacent spans:
  $$\Delta Y = |Y_{\text{bottom}, 1} - Y_{\text{bottom}, 2}| \le 0.35 \times \text{font\_size}$$
  $$\text{Gap}_X = X_{\text{left}, 2} - X_{\text{right}, 1} \le 1.5 \times \text{font\_size}$$
  If satisfied, MinerU **merges these spans into a single continuous sentence**, embedding the math symbol as a child element. This ensures the entire sentence is translated cohesively.

---

### 2.4. `Marker` (VikParuchuri / DataLab)
* **Repository:** `datalab-to/marker`
* **Key Module:** `marker/processors/line_merge.py`

#### 🎯 Technique: Line Merging & Hyphenation Rebuilding
Marker reassembles text broken across line boundaries by hyphens (`-`):
1. Detects soft hyphens or line-ending hyphens matching `r"(\w+)-\s*$"`.
2. Verifies lexical validity against dictionaries before joining the words across the line break.
3. Collapses lines within the same paragraph into a unified text run, preserving real paragraph boundaries.

---

## 3. Comparative Synthesis & Architectural Matrix

| Engineering Challenge | Naive / Legacy Approach | `pdf2zh` & `BabelDOC` Approach | `MinerU` & `Marker` Approach | LayoutLingua Implementation |
| :--- | :--- | :--- | :--- | :--- |
| **Math Formulas** | Untranslated or static glossary | Font inspection (`CM*`) + token masking (`[v:N]`) | YOLO-MFD model extracting LaTeX | **Font Heuristics + Token Shield (`<b0></b0>`) + Self-Healing** |
| **Fragmented Text Spans** | Translate fragments separately $\rightarrow$ Overflow | Merge lines inside blocks | Baseline matching algorithm $\Delta Y \le 0.35 \times h$ | **Horizontal Baseline Fragment Merging** in `parser.py` |
| **TOC Dot-Leaders (`.....`)** | MT copies 70 dots $\rightarrow$ Overflow | Detect TOC, separate title from page num | Parse structured TOC tree | **Elastic Dot-Leader (`\dotfill`)**: Dynamic dot calculation in `fitting.py` |
| **Text Expansion** | Fixed font size $\rightarrow$ Overwrite | Stepwise font downscaling & line tightening | Full-page reflow (regenerates PDF) | **Multi-Stage Adaptive Fitting**: Dynamic line-height + binary search font fitting + cluster clearance |
| **Technical Glossaries** | Monolithic JSON dictionary | System prompt + contextual LLM | Contextual LLM injection | **Domain Glossary Manager**: Normalized token-safe regex injection |

---

## 4. Key Architectural Implementations in LayoutLingua

1. **Horizontal Baseline Line Merging (`parser.py`)**:
   - Groups text blocks sharing vertical overlap $\ge 65\%$ and horizontal gap $\le 18\text{pt}$ into cohesive sentences while strictly safeguarding multi-column layouts.
2. **Elastic Dot-Leader Harmonization (`fitting.py`)**:
   - Implements LaTeX `\dotfill` algorithm for TOC dot leaders (`.....`), dynamically adjusting leader length to guarantee that page numbers align cleanly to the right margin.
3. **Cluster-Level Clearance & Non-Contracting Expansion (`protection.py` & `engine.py`)**:
   - Groups spans by baseline clusters, eliminating coarse bounding-box collisions with grouping braces and fraction denominators.
   - Preserves original paragraph width without contracting below $x_1$.

---

## 5. Primary Source Citations

1. **pdf2zh:** [https://github.com/ByByMe/pdf2zh](https://github.com/ByByMe/pdf2zh) — Source: `converter.py`, `high_level.py`.
2. **BabelDOC:** [https://github.com/funstory-ai/BabelDOC](https://github.com/funstory-ai/BabelDOC) — ACL 2024 Paper: *"BabelDOC: An Open-Source Framework for Layout-Preserving PDF Translation via Intermediate Representation Layer"*.
3. **MinerU (Magic-PDF):** [https://github.com/opendatalab/MinerU](https://github.com/opendatalab/MinerU) — Source: `para_split.py` & layout pipeline documentation.
4. **Marker:** [https://github.com/datalab-to/marker](https://github.com/datalab-to/marker) — Source: `marker/processors/line_merge.py`.
5. **Nougat:** [https://github.com/facebookresearch/nougat](https://github.com/facebookresearch/nougat) — Meta AI ArXiv: 2308.13418.
