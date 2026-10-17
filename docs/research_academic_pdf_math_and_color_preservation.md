# Research: Academic PDF Math Preservation, Span-Level Color Fidelity, and Typography Regeneration

## Executive Summary

This research report investigates the root causes and open-source solutions for four interrelated defects observed in real-world academic/scientific document translation (exemplified by the Vietnamese-to-English translation of *Sổ tay Toán học*):
1. **Formula Token Leakage (`<b0></b0>`, `(k n <b>0></b>)`)**: Placeholders designed to shield math formulas leaked raw XML tags into the typeset PDF.
2. **Color Bleeding (Unintended Blue / Accent Prose)**: Section headings and paragraph bodies merged into single blocks, causing heading accent colors (e.g. `#1B4F72`) to paint over entire paragraphs.
3. **Untranslated Hybrid Math Sentences**: Introductory clauses containing inline math (e.g., *"Số lượng hoán vị lặp bằng $P_n$..."*) were falsely classified as formulas and skipped.
4. **Typography & Font Degeneration**: Vector serif mathematical typography defaulted to uniform sans-serif (`DejaVuSans`), corrupting math aesthetics and font hierarchy.

We analyze primary architectures from **`funstory-ai/BabelDOC`** (ACL 2024), **`PDFMathTranslate` (`pdf2zh`)**, **`opendatalab/MinerU` (`magic-pdf`)**, and **PyMuPDF's low-level `TextWriter` / `insert_textbox`** rendering engine to establish robust production fixes.

---

## 1. Defect Analysis from Real-World Testcases

### 1.1 Formula Token Leaks: The Missing Unmasking Pipeline
In `layoutlingua/processing/formula/isolator.py`, mathematical spans within text blocks are replaced with placeholder tokens:
```python
placeholder = f"<b{token_id_counter}></b{token_id_counter}>"
```
During machine translation (Google Translate, DeepL, or LLMs), several transformations occur:
- **Spacing modifications**: The translator inserts spaces inside tags: `<b 0></b0>` or `<b0> </b0>`.
- **Character corruptions**: Under certain prompt patterns, punctuation or bracket nesting causes deformed tags: `(k n <b>0></b>)`.
- **Pipeline omission**: In `server.py`, the translated batch dictionary was passed directly into `translated_segments` without ever calling `isolator.restore_translation(segment, translated_text)`.

Because unmasking was bypassed, PyMuPDF printed literal string tokens into the final PDF.

### 1.2 Color Bleeding: Block-Level vs Span-Level Quantization
In the source PDF, Page 10 features:
- A heading: `"3. Chỉnh hợp (không lặp)"` styled in **Blue** (RGB: `(0.106, 0.31, 0.447)`).
- A body line immediately below: `"Cho n phần tử khác nhau..."` styled in **Black** (RGB: `(0.0, 0.0, 0.0)`).

Because PyMuPDF's default block clustering aggregates lines within $1.2 \times \text{line\_height}$ into a single `fitz.Block`, the extractor grouped the heading and the subsequent body sentence into one `TextBlock`. 
In `TypesetEngine._extract_dominant_color()`, a voting algorithm picked the color with the highest glyph count. If the heading had heavy formatting or occurred early, the entire block was tagged as blue. `scratch_page.insert_textbox(rect, text, color=dominant_color)` then rendered all body prose in blue.

### 1.3 False-Positive Formula Exclusion (Untranslated Prose)
Equations in textbooks often have lead-in phrases:
- *"Số lượng chỉnh hợp lặp chập k có thể tạo thành từ n phần tử:"*
- *"Số các tổ hợp lặp chập k có thể tạo thành từ n phần tử bằng:"*

When parsed, `is_math_span()` triggered on embedded symbols ($k$, $n$, $P_n$, $\ge$). Because the block had high symbol density or was misclassified as a `formula` block by layout heuristic, the entire block was preserved from source without translation.

---

## 2. Open-Source Architectural Solutions

### 2.1 Pattern A: Robust Token Masking & Hallucination Repair (`BabelDOC` & `pdf2zh`)
*Source: `funstory-ai/BabelDOC`, `PDFMathTranslate/PDFMathTranslate-next`*

`BabelDOC` uses a three-tier protection system for math formulas and inline symbols:
1. **Syntactically Invariant Placeholder**: Rather than HTML/XML tags (`<b0></b0>`), which MT engines routinely mangle or mistake for formatting tags, modern engines use delimiter-safe tokens:
   - `⟦MATH_0⟧` (Unicode mathematical brackets U+27E6 / U+27E7) or `⦃M0⦄`.
   - MT models treat Unicode mathematical white brackets as untranslatable named entities.
2. **Fuzzy Tag Normalization Prior to Extraction**:
   Before matching tokens, run a regex sanitizer to collapse MT-induced whitespace and punctuation:
   ```python
   # Collapses <b 0></b 0>, <b0> </b0>, < b 0 >, <b>0></b>
   text = re.sub(r"<\s*b\s*(\d+)\s*>\s*<\s*/\s*b\s*\1\s*>", r"<b\1></b\1>", text)
   text = re.sub(r"<\s*b\s*(\d+)\s*>\s*<\s*/\s*>\s*", r"<b\1></b\1>", text)
   text = re.sub(r"<\s*b\s*(\d+)\s*>", r"<b\1></b\1>", text)
   text = re.sub(r"⟦\s*MATH\s*[-_]?\s*(\d+)\s*⟧", r"⟦MATH_\1⟧", text)
   ```
3. **Fail-Safe Token Verification Gate**:
   If a token was deleted or multiplied by the MT engine:
   - Extract surviving tokens.
   - If token count mismatches, perform sequence alignment: match tokens by order and interpolate missing math expressions at original positions rather than dropping the whole paragraph.

### 2.2 Pattern B: Multi-Span & Sub-Line Layout Decomposition
*Source: PyMuPDF Documentation, MuPDF C API (`fz_show_text`)*

To prevent color bleeding, modern layout translation systems do not treat a `TextBlock` as an atomic styling unit. Instead:
1. **Sub-Block Color Segmentation**:
   If a `TextBlock` contains spans with significantly different colors ($\Delta E > 15$ or Euclidean RGB distance $> 0.2$):
   - Group spans by color into sub-lines or sub-blocks.
   - Headings (different font size or color) are detached into their own distinct bounding box.
   - Body prose is given its own bounding box with black/dark-gray text color.
2. **Selective Redaction per Line Rect**:
   Instead of wiping the entire block bounding box, redact only the exact lines (`tight_line_rects`), and write back:
   - Heading text into the heading rect with heading color.
   - Body text into the body rect with body color.

### 2.3 Pattern C: Inline Math vs Display Math Classification (`MinerU` & `DocLayout-YOLO`)
*Source: `opendatalab/MinerU`, DocLayout-YOLO Benchmarks*

To prevent introductory prose like *"Số lượng hoán vị lặp bằng"* from staying untranslated:
1. **Classification Criteria**:
   - **Display Math (Block)**: A block whose text contains no lowercase natural language words ($\ge 3$ consecutive letters) and consists entirely of operators, numerals, or centered equations. $\rightarrow$ **Preserve completely**.
   - **Inline Math (Sentence)**: A block containing natural language sentences with interspersed math variables ($k, n, x \in \mathbb{R}$). $\rightarrow$ **Isolate inline variables with tokens, translate all surrounding prose**.
2. **Strict Regex for Prose Detection**:
   If a block contains words of length $\ge 3$ from a human language dictionary or character set (including accented Vietnamese: *Số lượng, hoán vị, chỉnh hợp*), it **must not** be marked as a Display Math block.

### 2.4 Pattern D: Academic Typography & Font Pairing
*Source: TeX Gyre Project, Google Fonts Noto / Source Serif*

Academic documents are primarily set in Serif typography (Computer Modern, Times New Roman, Palatino). Forcing a sans-serif font (`DejaVuSans`) degrades readability and disrupts visual balance.
1. **Primary Academic Font Hierarchy**:
   - **Serif Documents**: Use `Source Serif 4` / `DejaVuSerif` / `Times-Roman` with full Unicode coverage for Vietnamese diacritics and European accents.
   - **Sans Documents**: Use `Manrope` / `DejaVuSans` / `Helvetica`.
2. **Dynamic Weight & Slope Preservation**:
   - Spans with `flags & 2` (Italic) or font names containing `Italic` / `Oblique` $\rightarrow$ Render using the Italic variant.
   - Spans with `flags & 16` (Bold) or font names containing `Bold` $\rightarrow$ Render using the Bold variant.

---

## 3. Engineering Implementation Blueprint for LayoutLingua

### Component 1: `server.py` Translation Pipeline Hook
```python
# Unmask formula tokens and restore exact mathematical glyphs
for s_id, t_text in raw_batch_res.items():
    seg = segment_lookup.get(s_id)
    if seg and seg.tokens:
        t_text = isolator.restore_translation(seg, t_text)
    translated_segments[s_id] = t_text
```

### Component 2: `google_rpc.py` Token Sanitizer
```python
def _sanitize_translated_tokens(text: str) -> str:
    # Repair deformed XML tags from Google/LLM translations
    text = re.sub(r"<\s*b\s*(\d+)\s*>\s*<\s*/\s*b\s*\1\s*>", r"<b\1></b\1>", text)
    text = re.sub(r"<\s*b\s*(\d+)\s*[/]?>", r"<b\1></b\1>", text)
    text = re.sub(r"<\s*/\s*b\s*(\d+)\s*>", r"<b\1></b\1>", text)
    text = re.sub(r"<\s*b\s*(\d+)\s*>\s*<\s*b\s*\1\s*>", r"<b\1></b\1>", text)
    return text
```

### Component 3: `engine.py` Color-Aware Sub-Block Splitting
When a block contains a colored heading and black body text:
- Partition the block into distinct sub-units by `span.color`.
- Redact and typeset each sub-unit with its native color and font weight.

---

## 4. Conclusion & Verification Plan
By implementing:
1. Mandatory formula unmasking in `server.py`,
2. Token hallucination repair in `google_rpc.py`,
3. Sub-line color preservation in `engine.py`,
4. Prose-safety checks in `isolator.py`,

the typesetting engine will completely eliminate `<b0>` tag leaks, preserve original heading colors without bleeding, translate 100% of mathematical introductory prose, and maintain authentic academic typography.
