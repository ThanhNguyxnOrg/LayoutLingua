# Core Mathematical & Typesetting Algorithms (`docs/ALGORITHM.md`)

<p>
  <img src="https://img.shields.io/badge/Algorithm-Sub--Line%20Formula%20Pinning-0D9488?style=for-the-badge" alt="Sub-Line Formula Pinning" />
  <img src="https://img.shields.io/badge/Classification-vflag%20%2B%20Style--Switch-6366F1?style=for-the-badge" alt="vflag" />
  <img src="https://img.shields.io/badge/Typesetting-Anisotropic%20Tz%20%2B%20Ray--Cast-0284C7?style=for-the-badge" alt="Anisotropic Tz" />
</p>

---

## 1. Sub-Line Formula Pinning & `vflag` Classification

Given a baseline row $R = \{c_1, c_2, \dots, c_m\}$ of structured glyphs extracted from MuPDF, LayoutLingua segments $R$ into word tokens $W = \{w_1, w_2, \dots, w_k\}$ at whitespace boundaries, Symbol/non-Symbol font transitions, and hyperlink color boundaries ($\|\mathbf{c}_i - \mathbf{c}_{i-1}\|_2 > 0.35$).

### 1.1 Primary Token Classifier (`isMathWordToken`)
A word token $w$ is classified as a mathematical candidate (`isMath = true`) if any of the following language-agnostic conditions hold:

1. **2D Subscript / Superscript / Vector Overbar Adjacency (`hasAdjacentSubSup`)**:
   $$\exists s \in \mathcal{S}_{\text{subsup}} \cup \mathcal{S}_{\text{symbol}} : \; x_0(w) - 3 \le x_0(s) \le x_1(w) + 9 \;\land\; |\text{oy}(s) - \text{oy}(w)| \ge 1.5\text{pt}$$
   This guarantees that $P_n.$, $a_i^k$, $M_0$, and $\overrightarrow{AB}$ are immediately pinned as 2D mathematical obstacles before any prefix or punctuation rule runs.
2. **Symbol / Math Font Flag (`vflag`)**:
   $$\text{font}(w) \sim \texttt{/symbol|mt extra|math|cmmi|cmsy/i} \implies \text{isMath}(w) = \text{true}$$
   Every glyph rendered in `Symbol`, `MT Extra`, or TeX Math fonts (such as the 4 PUA glyphs `0xF075, 0xF075, 0xF075, 0xF072` forming the vector arrow over $\overrightarrow{AB}$) is preserved as math.
3. **Explicit Mathematical Operators & Differentials**:
   - Contains explicit operators (`=`, `<`, `>`, `≠`, `≤`, `≥`, `±`, `∑`, `∏`, `∫`, `√`, `∞`, `∂`, `∇`, `∈`, `⊂`, `⇒`, `⇔`).
   - Matches ISO 80000-2 function names (`sin`, `cos`, `tan`, `cot`, `ln`, `log`, `lim`, `det`, `sup`, `inf`, `dx`, `dy`, `dt`) or fused operator-argument expressions (`sinx`, `cosxdx`, `ABcos`).
   - Consonant-only lowercase algebraic clusters without vowels (`kl`, `mn`, `pq`, `xy`).
4. **Typographic Italic Switch**:
   - In upright paragraphs, 2-to-3 letter ASCII italic tokens (`ab`, `ax`, `py`, `uv`) represent implicit variable products under ISO 80000-2.

### 1.2 Contextual Recovery Pass
When a line contains natural prose (`proseWordCount >= 1`), a contextual pass recovers 1D tokens that belong to the natural sentence flow:
- **Paragraph-Relative Italic Check (`lineIsMostlyItalic`)**: If $\ge 60\%$ of the unambiguous prose words on the line are already italic, italic is the paragraph's base style (e.g., an italic theorem or biographical note), so 2-to-3 letter italic words containing vowels are recovered as prose.
- **Parenthetical 1D Variable Prefix**: If a 1D variable token starts with an opening parenthesis (e.g. `(n` in `P_n = n! (n giai thừa)`) and is immediately followed by prose (`giai thừa)`), it is recovered into the parenthetical prose span (`(n factorial)`).

---

## 2. Bidirectional Pixmap Ray-Cast Clearance

For each `ProseSpan` $s$ with bounding box $[x_0, y_0, x_1, y_1]$ and median background color $\mathbf{b}_s \in [0, 1]^3$:

1. **Obstacle Clipping**: Clips `rightClearanceX` and `leftClearanceX` against all `MathObstacle`s and sibling `ProseSpan`s whose vertical overlap exceeds $1.2\text{pt}$.
2. **Pixmap Ray-Cast**: Scans the 1x RGB page pixmap horizontally from $x_1 + 5$ to `maxRight` (and from $x_0 - 4$ down to `minLeft`). At each $x$, if any pixel $y \in [y_0 + 1, y_1 - 1]$ satisfies:
   $$|R(x,y) - b_{s,R}| + |G(x,y) - b_{s,G}| + |B(x,y) - b_{s,B}| > 0.28$$
   the ray terminates at $x - 2\text{pt}$. This detects vertical curly braces (`}`), circle/triangle diagrams, and vertical table rules with sub-point accuracy.

---

## 3. Parallel Table Row Separation (`canMerge`)

Two vertically consecutive `ProseSpan`s (`lastSpan` and `sp`) in the same column band merge into a multi-line `ProseGroup` if and only if:
1. **Typographic & Chromatic Continuity**: Identical bold/italic style, font size within $\pm 1.0\text{pt}$, vertical gap $\Delta y \in [-2.5\text{pt}, \max(8.5\text{pt}, 0.85 \times \text{size})]$, and matching foreground/background colors.
2. **Wrapped Line Fill Ratio**:
   $$x_1(\text{lastSpan}) - x_0(\text{lastSpan}) \ge \max\!\Big(0.24 \cdot W_{\text{page}},\; 0.56 \cdot (\min(C_R(\text{lastSpan}), C_R(\text{sp})) - x_0)\Big)$$
   and $x_1(\text{sp}) \le x_1(\text{lastSpan}) + 28\text{pt}$ (preventing short table cells from merging into wider rows below them).
3. **Parallel Symbol/Formula Row Guard**:
   - `hasNewLeftSymbolRow`: Rejects merging if `sp` is in a right-hand description column and a new `MathObstacle` appears to its left on `sp`'s vertical band.
   - `hasDistinctRightFormulaRows`: Rejects merging if both `lastSpan` and `sp` pair with distinct single-row `MathObstacle`s aligned to their right ($|x(m_1) - x(m_2)| \le 30\text{pt}$).
   - `hitsHorizontalBorder`: Rejects merging if a horizontal ruled line ($\ge 75\%$ ink density across $[x_0, x_1]$) separates `lastSpan` and `sp`.

---

## 4. Two-Pass Selective Erasure & Anisotropic `Tz` Fitting

### Pass 1: Obstacle-Clipped Prose Erasure
For each `ProseSpan` $s$ in a translated `ProseGroup`:
- Computes `[eraseX0, eraseY0, eraseX1, eraseY1]` with a $0.8\text{pt}$ de-aliasing pad, then clips all four edges against every `MathObstacle` $m$ so vector arrows, radical signs, and subscripts are never touched.

### Pass 2: Anisotropic `Tz` + Multi-Line Fitting
- **Single-Line Slot (`spans.length === 1`)**:
  Computes $r = W_{\text{clearance}} / W_{\text{text}}(\text{size}_0)$. Combines horizontal PDF scaling $\text{Tz} = \max(82\%, \min(100\%, r \times 100\%))$ with vertical font scaling $s_v = \max(s_{\min}, \min(1.0, r / (\text{Tz}/100)))$.
- **Multi-Line Slot (`spans.length > 1`)**:
  Searches $s \in [1.0, s_{\min}]$ in steps of $0.02$. If standard wrapping at $s_{\min}$ exceeds `maxBottomY`, applies multi-stage horizontal condensation ($\text{Tz} \in \{92\%, 86\%, 80\%\}$) to increase effective line capacity by $100/\text{Tz}$, guaranteeing 100% of translated lines are rendered without truncation.
