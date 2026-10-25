# Contributing to LayoutLingua (`CONTRIBUTING.md`)

<p>
  <img src="https://img.shields.io/badge/PRs-Welcome-10B981?style=for-the-badge" alt="PRs Welcome" />
  <img src="https://img.shields.io/badge/Code%20Policy-Zero%20Hardcode-EF4444?style=for-the-badge" alt="Zero Hardcode Policy" />
  <img src="https://img.shields.io/badge/TypeScript-Strict%20Mode-3178C6?style=for-the-badge" alt="TypeScript Strict" />
</p>

Thank you for contributing to **LayoutLingua**! To keep the PDF translation and typesetting engine reliable across all 17 supported languages and arbitrary academic PDF layouts, all contributions must adhere to the architectural standards below.

---

## 1. Golden Engineering Rules

### 🚫 Rule 1: Strict Zero-Hardcode Policy
- **Never hardcode natural-language word lists** inside `src/engine/pdfTranslator.ts` to fix a document-specific bug (e.g., never add lists of Vietnamese/English/German stopwords or caption words to `isMathWordToken` or `canMerge`).
- Always solve classification and layout challenges using:
  1. **Font-table flags (`vflag`)**: `Symbol`, `MT Extra`, `CMMI`, `CMSY`, `bold`, `italic`, `serif`, `mono`.
  2. **2D Coordinate Geometry**: Baseline offsets ($\Delta oy$), glyph size ratios, column fill ratios, and pixmap ray-casting.
  3. **Unicode Character Properties**: `\p{Lu}`, `\p{Ll}`, `\p{Lo}`, `\p{N}`, and script ranges.
  4. **Statistical Trigram Models (`franc-min`)**: For language identification.

### 📐 Rule 2: Non-Destructive Vector Preservation
- Pass 1 erasure rectangles must **only** cover `ProseSpan` bounding boxes and must be clipped against every nearby `MathObstacle`.
- Never use whole-block union rectangles that could erase vertical curly braces (`}`), fraction bars, or geometric diagrams between lines.

### 🌍 Rule 3: 17-Language Parity
- When adding domain terms to `src/engine/glossaries/`, keep all 16 `academic_math_en_*.json` files synchronized so English-pivot translation works identically across all 272 language pairs.

---

## 2. Development Workflow

```bash
# 1. Install dependencies
npm install

# 2. Start full-stack dev server (Express + Vite on port 3000)
npm run dev

# 3. Type-check and build production bundle
npm run lint
npm run build
```

---

## 3. Pull Request Checklist

- [ ] `npm run build` succeeds with zero TypeScript or Vite errors.
- [ ] Zero hardcoded word lists introduced in `src/engine/pdfTranslator.ts`.
- [ ] Tested on multi-page mathematical PDFs (including TOC pages, symbol tables, footnotes with links, and geometric figures) with `0` PUA leaks and `0` overflow fallbacks.
- [ ] Relevant documentation (`ARCHITECTURE.md`, `docs/ALGORITHM.md`, or `CHANGELOG.md`) updated.
