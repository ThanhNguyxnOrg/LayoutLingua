# Research: Architecture Patterns in Open-Source Layout-Preserving PDF Translation

## Executive Summary

Translating scientific, technical, and academic PDF documents while preserving their visual layout, mathematical equations, and tabular structures is one of the most notoriously difficult problems in document engineering. Unlike HTML or Word documents, PDFs are purely geometric **page-description files** consisting of low-level drawing operators, absolute glyph placements, and embedded font subsets, with no inherent semantic structure or automatic text reflow.

This document investigates the architectural patterns, engineering solutions, and root-cause failure modes observed in state-of-the-art open-source engines:
1. **`pdf2zh` / `PDFMathTranslate` / `PDFMathTranslate-next`** (Byaidu / PDFMathTranslate community)
2. **`BabelDOC`** (`funstory-ai/BabelDOC`)
3. **`MinerU` / `magic-pdf`** (`opendatalab/MinerU`)
4. **`BilingualBookMaker`** (`yihong0618/bilingual_book_maker`)
5. Native **PyMuPDF / MuPDF** typesetting pipelines

It documents how these projects prevent layout collapse, isolate formulas, handle Unicode font encoding, and resolve desktop GUI deadlocks.

---

## 1. The Core Engineering Challenge: Why Naive PDF Translation Fails

### 1.1 The Absence of Flow Semantics
A PDF contains no concept of paragraphs, lines, or margins. Instead, text is positioned using low-level drawing operators:
```postscript
BT
/F1 12 Tf
72 712 Td
(Hello World) Tj
ET
```
If `"Hello World"` is translated to Vietnamese (*"Xin chào Thế giới"*), the translated text is **30% longer** in character count. In a naive system, this causes:
1. **Text Overlap (Overstrike)**: Translated strings spill into subsequent columns, diagrams, or page margins.
2. **Vertical Collision**: Multi-line expansions collide with adjacent paragraphs or table borders.

### 1.2 The Math Corruption Problem
Scientific papers embed mathematics as:
- Vector curves (paths),
- Raw single-character glyphs with specialized math fonts (e.g., Computer Modern `CMMI10`, `CMSY10`),
- Inline symbols mixed directly with prose (e.g., *"where $x_k \in \mathbb{R}^d$ denotes..."*).

When these passages are fed directly to an LLM or Neural Machine Translation (NMT) model:
- Subscripts and superscripts are mangled (e.g., $x_{i,j}$ becomes $x i j$),
- Greek letters and operators are translated as words (e.g., $\Delta$ translated as "Difference" or "Triangle"),
- Spacing and punctuation inside formulas are disrupted.

---

## 2. Deep Dive: Leading Open-Source Architectures

### 2.1 `pdf2zh` & `PDFMathTranslate-next`
`pdf2zh` (the core engine behind `PDFMathTranslate`) is one of the most widely used open-source academic PDF translation tools.

```
┌─────────────────────────────────────────────────────────────┐
│                       Input PDF File                        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Layout Segmentation (DocLayout-YOLO / ONNX / BabelDOC)   │
│    - Classifies blocks: Text, Figure, Table, Equation       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Math & Formula Isolation                                 │
│    - Font Pattern: Regex matching CM[^RT], Math fonts       │
│    - Spatial Masking: Masks equation bounding boxes         │
│    - Placeholder Injection: Replaces inline formulas        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Multi-Threaded Translation Dispatch                      │
│    - Batch translation via DeepL / OpenAI / Ollama / Google │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Low-Level Stream Rewriting & Typesetting                 │
│    - Custom PDFMiner interpreter (PDFPageInterpreterEx)     │
│    - Redacts source text; writes target text with font scale│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│           Dual / Mono Layout-Preserved Output PDF           │
└─────────────────────────────────────────────────────────────┘
```

#### Formula Preservation Strategies in `pdf2zh`:
1. **Spatial Masking via Layout Detection**:
   Using an ONNX vision model (`DocLayout-YOLO`), all bounding boxes classified as display equations (`Formula`) are excluded from text extraction. Their exact vector curves and pixel positions are untouched.
2. **Font & Character Regex Pattern Filtering**:
   For inline formulas embedded within prose blocks, `pdf2zh` uses command-line flags:
   - `--formular-font-pattern`: Matches font names used by TeX engines (e.g., `^CM`, `Math`, `Sym`, `Times-Italic`).
   - `--formular-char-pattern`: Matches standalone mathematical operators (`=`, `+`, `-`, `\int`, `\sum`) and digits.
   Characters matching these criteria are retained in their original coordinates and substituted with indexed placeholder markers (`__FORMULA_0__`, `__FORMULA_1__`) before dispatching to the translator. Upon receiving the translated prose, the markers are swapped back into their exact visual positions.

#### How `pdf2zh` Fixes Font Overlap (GitHub Issue Tracker Analysis):
In early v1.x builds, `pdf2zh` suffered heavily from text overlapping across columns. The v2.0 (`PDFMathTranslate-next`) overhaul resolved this through:
- **`font_size_offset` & Dynamic Ratio Scaling**: When replacement fonts (e.g., Source Han Serif / Noto Sans) have larger ascenders/descenders than the original font (Helvetica / Times), text runs are scaled horizontally using PDF operator `Tz` and font size is stepped down by 0.5pt increments.
- **`--ultrafast` vs `--mode precise`**: Provides a heuristic fast-path (`pdf-inspector`) for clean digital PDFs, while routing complex multi-column papers through vision-based boundary verification (`BabelDOC`).

---

### 2.2 `BabelDOC` (`funstory-ai/BabelDOC`)
`BabelDOC` is a next-generation layout-preserving document translation framework designed specifically to address the limitations of `pdf2zh`.

#### Core Architectural Innovations in `BabelDOC`:
1. **Intermediate Representation (IR)**:
   Instead of translating directly within the PDF parsing loop, BabelDOC decouples the document into an explicit **Document IR**:
   - `VisualGeometry`: Absolute bounding box, z-index, reading order.
   - `TypographyMetrics`: Font family, weight, baseline, line floor.
   - `SemanticUnit`: Translatable prose segment vs. immutable formula/table token.
2. **Adaptive Typesetting Engine**:
   When translated text expands (e.g., English to Vietnamese/German), BabelDOC does not just shrink font size blindly; it computes a multi-line wrapping budget within the block rectangle:
   - Calculates line height floors to prevent ascender/descender clipping.
   - Re-anchors paragraphs to original baseline coordinates.
3. **Cross-Page Glossaries & Context**:
   Maintains a global document glossary so technical terms remain consistent across 50+ page documents.

---

### 2.3 `MinerU` / `magic-pdf` (`opendatalab/MinerU`)
`MinerU` is a state-of-the-art PDF extraction system developed by OpenDataLab.

#### How `MinerU` Overcomes Formatting Corruption:
1. **Formula-to-LaTeX Conversion**:
   Unlike engines that attempt to translate around raw PDF glyphs, MinerU's model (`PDF-Extract-Kit`) identifies both inline and display equations and converts them into standard **LaTeX** syntax (`$...$` and `$$...$$`).
2. **Table Structural Reconstruction**:
   Rather than treating table text as loose floating words, MinerU parses the table grid lines and generates clean HTML/Markdown tables.
3. **Downstream Translation Pattern (`mineru-pdf-translate`)**:
   Translators ingest the structured Markdown output, protect LaTeX formulas and HTML table tags using prompt constraints, and typeset the translated document without ever touching low-level PDF stream bytes.

---

### 2.4 `BilingualBookMaker` (`yihong0618/bilingual_book_maker`)
`BilingualBookMaker` specializes in EPUB and PDF bilingual translations.

#### Key Engineering Lessons:
1. **Atomic Checkpointing (`cache.json`)**:
   Long translations often fail halfway due to LLM rate limits or network drops. `BilingualBookMaker` caches every translated paragraph on disk. If a process terminates, restarting resumes from the exact paragraph without re-translating or incurring extra API costs.
2. **Token Windowing & Exponential Backoff**:
   Implements automatic retry logic on HTTP 429 (Rate Limit) and HTTP 500 errors with jittered backoff.

---

## 3. Font Encoding & Vietnamese/Unicode Mojibake

### 3.1 The Identity-H & CMap Requirement
In PDF specifications, standard 14 PostScript fonts (Helvetica, Times-Roman, Courier) use 8-bit `WinAnsiEncoding` or `MacRomanEncoding`. They cannot represent:
- Vietnamese tone marks (ă, â, đ, ê, ô, ơ, ư, etc.),
- Mathematical symbols ($\nabla, \in, \mathbb{R}, \approx$),
- CJK characters.

Attempting to draw Vietnamese text using standard Helvetica causes immediate **mojibake** (characters turn into `?` or produce visual garbage).

### 3.2 The SOTA Solution
Modern layout engines (including LayoutLingua, `pdf2zh`, and `BabelDOC`):
1. Embed TrueType/OpenType font files directly into the PDF.
2. Use **`Type0` fonts with `Identity-H` encoding**.
3. Generate a complete **`ToUnicode` mapping CMap** stream so that readers (Adobe Acrobat, Preview, Chrome) can both render the glyphs and allow users to select, copy, and search the translated text.

---

## 4. UI/UX Architecture & Desktop Integration Pitfalls

### 4.1 The React Re-render & Effect Cancellation Trap (Root Cause Analysis)
In desktop wrappers (Tauri, Electron), naive asynchronous implementations frequently encounter this failure pattern:

```typescript
// ❌ ANTI-PATTERN: State dependency in translation trigger
useEffect(() => {
  if (phase !== 'processing') return;

  const timer = setInterval(() => {
    fetch('/api/progress').then(res => setDone(res.page));
  }, 300);

  fetch('/api/translate').then(() => setPhase('done'));

  return () => {
    // 💥 CRITICAL BUG: When setDone() updates, React unmounts this effect!
    // timer is cleared AND in-flight HTTP request is cancelled!
    clearInterval(timer);
  };
}, [phase, done]); // <--- 'done' causes an infinite restart loop!
```

**Why this froze our UI earlier:**
1. Translation began $\rightarrow$ `phase = 'processing'`.
2. First page finished $\rightarrow$ background poll updated `done = 1`.
3. Because `done` was in the dependency array, React immediately ran the effect cleanup, cancelling the active translation request.
4. React then immediately started a *new* `/api/translate` call.
5. On the next progress tick, it cancelled again.
6. The app got stuck in an infinite cancellation loop, freezing at `page 4 of 4` without ever reaching `done`.

**The Solution:**
Decouple the translation trigger from progress polling using an idempotent `isTranslatingRef` and a separate polling listener that never unmounts the parent worker:

```typescript
// ✅ SOTA PATTERN: Single-flight ref with decoupled progress listener
const isTranslatingRef = useRef(false);

useEffect(() => {
  if (phase !== 'processing') {
    isTranslatingRef.current = false;
    return;
  }
  if (isTranslatingRef.current) return;
  isTranslatingRef.current = true;

  let active = true;
  // Trigger exactly once; track progress safely without effect churn
  runTranslation(() => active);
  
  return () => { active = false; };
}, [phase, docId]); // NEVER include progress counters!
```

---

## 5. Architectural Comparison Matrix

| Dimension | `pdf2zh` (v2.0) | `BabelDOC` | `MinerU` | LayoutLingua v2.0 |
| :--- | :--- | :--- | :--- | :--- |
| **Extraction Engine** | PDFMiner + PyMuPDF | PyMuPDF + Custom IR | PDF-Extract-Kit + YOLO | PyMuPDF (fitz) C/C++ engine |
| **Formula Strategy** | Spatial Mask + Font Regex (`CM[^RT]`) | IR Formula Tokenizer | Vision to LaTeX (`$...$`) | Bounding Box Isolation + Math Token Shielding |
| **Typesetting Method** | Stream Rewriting (`Tz`/`Tf`) | Adaptive Box Rewrapping | Markdown to PDF Recompile | Page Redaction + Transactional Staging (`TypesetEngine`) |
| **Error Recovery** | Full file restart | File restart | Pipeline restart | **Page-Level Transaction Rollback** (`DocumentAccumulator`) |
| **Translation Models** | DeepL, OpenAI, Google, Zhipu | DeepL, LLMs, Glossaries | Any LLM via Markdown | **Google RPC (Zero setup)**, Gemini 2.5, OpenAI, Ollama |
| **Desktop Experience** | Web UI (Gradio) / CLI | NiceGUI / Docker WebUI | CLI / API service | **Native Tauri 2.0 (Rust) + React 19** |
| **Packaging & Setup** | Requires Python + Pip + Models | Requires Docker / Python | Requires PyTorch + GPU/CUDA | **Standalone 1-click `.exe` (Self-contained)** |

---

## 6. Synthesis: Key Takeaways Applied to LayoutLingua

1. **Formula Token Shielding (from `BabelDOC` & `pdf2zh`)**:
   Inline math must always be converted to invariant tokens (`«MATH_0»`) before passing to Google RPC or LLMs, preventing translation models from inventing symbols or altering indices.
2. **Adaptive Font Scaling with Line Floors (from `BabelDOC`)**:
   When translating into verbose languages like Vietnamese (+25% length), reduce font size dynamically with a hard minimum floor (7.5pt) and line-spacing constraints to prevent collision with adjacent blocks.
3. **Decoupled Telemetry Architecture (from Tauri / Desktop SOTA)**:
   Action dispatching (initiating translation) must never share lifecycle dependencies with polling listeners. Single-flight refs ensure zero cancellation churn.
4. **Zero-Setup Usability**:
   While `pdf2zh` and `MinerU` require extensive Python/Docker/CUDA setups that confuse non-technical end users, LayoutLingua bundles the engine into a clean native desktop executable that runs immediately.
