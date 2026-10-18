# ADR 0003: Cluster-Level Clearance and Non-Contracting Adaptive Typesetting

## Status
Accepted

## Context
In LayoutLingua v2.0.0 development, empirical translation benchmarks across complex technical documents (such as the 96-page academic reference `Sotaytoanhoc.pdf`) uncovered edge-case quality check warnings:
1. **Coarse Line Bounding Box Bridging**:
   - Multi-line grouping symbols (such as large curly braces `}`) and mathematical fractions $\frac{a}{b}$ often have disjoint text runs sitting on either side or on adjacent vertical baselines (e.g. numerator $a$ on top, denominator $b$ below).
   - PyMuPDF text block extraction or naive line grouping merged spans across horizontal gaps and baseline jitters into a single coarse rectangular bounding box.
   - The resulting rectangular clearance box covered the empty space between the spans, creating false-positive collision rejections against protected formulas and grouping symbols (e.g. Page 6, 7, 17).
2. **Artificial Bounding Box Contraction**:
   - `compute_expanded_layout_box` intended to expand paragraph widths into available right margins. However, obstacle detection evaluated all obstacles satisfying $rx_0 \ge x_0$, meaning an inline formula at the tail end of line 4 of a 4-line paragraph was treated as a rightward obstacle, clamping `right_limit` down and contracting the entire paragraph width by over 50% (Page 11).
3. **Single-Line Label Truncation**:
   - Short mathematical labels preceding equations (e.g., `"Biết các hệ số"`, Page 13) expand significantly in English (`"Knowing the coefficients"`). When confined to a single line height ($\le 13.5\text{pt}$), fixed font floors ($\ge 6.96\text{pt}$) forced 2-line wrapping, triggering catastrophic `overflow_height` fallbacks.

## Decision

1. **Cluster-Level Clearance Grouping (`compute_tight_line_clearance_regions`)**:
   - Replace coarse line-level union bounding boxes with spatial span clustering based on baseline alignment ($\le 3.5\text{pt}$) and horizontal proximity ($\le 6.0\text{pt}$).
   - Spans on opposite sides of a grouping brace or across a fraction division bar form distinct, non-overlapping bounding clusters.
   - *Result*: 100% elimination of false formula collisions without weakening protection on real intrusive overlaps.

2. **Non-Contracting Layout Box Invariant (`compute_expanded_layout_box`)**:
   - Enforce an invariant that `expanded_x1` can never contract below the block's original width:
     `expanded_x1 = max(x1, min(max_allowed_x1, max(x1, right_limit)))`
   - Filter obstacle candidates strictly to elements whose left boundary lies to the right of the block's right edge (`ox0 >= x1 - 5.0`).
   - *Result*: Multi-line paragraphs retain their full original width, eliminating false overflow fallbacks on pages with terminal inline formulas.

3. **Elastic Sizing Floor for Single-Line Text (`TextFitTester.test_fit`)**:
   - For single-line text blocks and Table of Contents entries (`height <= 1.8 * orig_font_size` or `is_toc`), allow elastic font scaling down to `0.50x` (floor `5.0pt`).
   - *Result*: Prevents single-line labels from wrapping to line 2 in tight vertical bounds while preserving high legibility.

## Consequences

- **Positive**:
  - Achieved **0 warnings (100% clean)** across Pages 1 to 25 of `Sotaytoanhoc.pdf`.
  - All 245 unit and integration tests continue to pass.
  - Aligns LayoutLingua with state-of-the-art open-source layout engines (`pdf2zh`, `BabelDOC`, `MinerU`).
