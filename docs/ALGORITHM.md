# 🧮 Core Mathematical & Typesetting Algorithms (`docs/ALGORITHM.md`)

<p align="center">
  <a href="../README.md">🏠 README</a> ·
  <a href="ARCHITECTURE.md">🏛 Architecture</a> ·
  <a href="ALGORITHM.md">🧮 Algorithms</a> ·
  <a href="API_REFERENCE.md">🔌 API</a> ·
  <a href="CHANGELOG.md">📜 Changelog</a> ·
  <a href="CONTEXT.md">🧭 Context</a> ·
  <a href="CONTRIBUTING.md">🤝 Contributing</a> ·
  <a href="CODE_OF_CONDUCT.md">🌈 Conduct</a> ·
  <a href="SECURITY.md">🔐 Security</a>
</p>

---

<p>
  <img src="https://img.shields.io/badge/Algorithm-Sub--Line%20Formula%20Pinning-0D9488?style=for-the-badge" alt="Sub-Line Formula Pinning" />
  <img src="https://img.shields.io/badge/Classification-vflag%20%2B%20Style--Switch-6366F1?style=for-the-badge" alt="vflag" />
  <img src="https://img.shields.io/badge/Typesetting-Anisotropic%20Tz%20%2B%20Ray--Cast-0284C7?style=for-the-badge" alt="Anisotropic Tz" />
  <img src="https://img.shields.io/badge/Zero%20Hardcode-100%25%20Algorithmic-22C55E?style=for-the-badge" alt="Zero Hardcode" />
  <img src="https://img.shields.io/badge/Tests-276%20Passed-059669?style=for-the-badge" alt="Tests" />
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
- **Paragraph-Relative Italic Check (`lineIsMostlyItalic`)**: If $\ge 60\text{\%}$ of the unambiguous prose words on the line are already italic, italic is the paragraph's base style (e.g., an italic theorem or biographical note), so 2-to-3 letter italic words containing vowels are recovered as prose.
- **Parenthetical 1D Variable Prefix**: If a 1D variable token starts with an opening parenthesis (e.g., `(n` in `P_n = n! (n factorial)`) and is immediately followed by prose (such as `factorial`), it is recovered into the parenthetical prose span (`(n factorial)`).

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

### Pass 1: MuPDF-Native Prose Redaction (Pre-Pass on a Private Document Copy) 🔬
For each `ProseSpan` $s$ in a translated `ProseGroup`:
- Computes an obstacle-clipped rectangle `[rx, topY, rw, botY]` whose directional pads shrink to zero whenever a `MathObstacle` sits within reach — vector arrows, radical signs, and subscripts are never touched.
- The rectangles become MuPDF `Redact` annotations applied via `applyRedactions(black_boxes=false, image_method=0, line_art_method=1, text_method=0)`, physically removing the source prose glyphs from the content stream while keeping every surviving vector, form XObject, and font reference intact. Copy/paste from the exported PDF yields *only* translated text + original math. 📋
- 🔑 **The redaction runs as a pre-pass on a private copy of the document**, which is saved and then reloaded by `pdf-lib`. Redacting the live page and transplanting only its content stream would dangle MuPDF's restructured Form XObjects (`Fm1..Fn`) and silently blank every display formula — the private-copy pre-pass keeps the output file fully self-consistent.
- 🛡️ **Fail-closed fallback**: pages whose redaction fails are painted with background-matched rectangles instead (`paintOverProse`), preserving the original glyphs underneath.

### Pass 2: Anisotropic `Tz` + Multi-Line Fitting
- **Single-Line Slot (`spans.length === 1`)**:
  Computes $r = W_{\text{clearance}} / W_{\text{text}}(\text{size}_0)$. Combines horizontal PDF scaling $\text{Tz} = \max(T_{\text{floor}}, \min(100\%, r \times 100\%))$ with vertical font scaling $s_v = \max(s_{\min}, \min(1.0, r / (\text{Tz}/100)))$, where the condensation floor is $T_{\text{floor}} = \max\!\big(64\%,\; \min(100\%,\, \tfrac{r}{s_{\min}} \times 100\%)\big)$. Because $s_v = r / T_{\text{floor}}$, any span with $r \ge 0.64 \cdot s_{\min}$ lands exactly on the vertical floor instead of falling through it - so a lone word (no wrap points, tolerant of the same 64-78% squeeze the TOC and multi-line paths already use) sandwiched between two `MathObstacle`s (e.g. a 10 pt slot such as "from") can never trigger `OVERFLOW_FALLBACK` while staying legible ($s_v \ge s_{\min}$, $\text{Tz} \ge 64\%$).
- **Multi-Line Slot (`spans.length > 1`)**:
  Searches $s \in [1.0, s_{\min}]$ in steps of $0.02$. If standard wrapping at $s_{\min}$ exceeds `maxBottomY`, applies multi-stage horizontal condensation ($\text{Tz} \in \{92\%, 86\%, 80\%\}$) to increase effective line capacity by $100/\text{Tz}$, guaranteeing 100% of translated lines are rendered without truncation.
