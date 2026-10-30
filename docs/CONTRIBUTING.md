# 🤝 Contributing to LayoutLingua (`CONTRIBUTING.md`)

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
  <img src="https://img.shields.io/badge/🙌_PRs-Welcome-10B981?style=for-the-badge" alt="PRs Welcome" />
  <img src="https://img.shields.io/badge/🚫_Code_Policy-Zero_Hardcode-EF4444?style=for-the-badge" alt="Zero Hardcode Policy" />
  <img src="https://img.shields.io/badge/🔷_TypeScript-Strict_Mode-3178C6?style=for-the-badge" alt="TypeScript Strict" />
  <img src="https://img.shields.io/badge/🐍_Python_Engine-Tested_(245_tests)-3776AB?style=for-the-badge" alt="Python Engine" />
</p>

Thank you for contributing to **LayoutLingua**! 🎉 To keep the PDF translation and typesetting engine reliable across all 17 supported languages and arbitrary academic PDF layouts, all contributions must adhere to the architectural standards below. 📐

---

## 1. 🏆 Golden Engineering Rules

### 🚫 Rule 1: Strict Zero-Hardcode Policy
- **Never hardcode natural-language word lists** inside the translation engine to fix a document-specific bug (e.g., never add lists of Vietnamese/English/German stopwords or caption words in the classifiers).
- Always solve classification and layout challenges using:
  1. **🏷️ Font-table flags (`vflag`)**: `Symbol`, `MT Extra`, `CMMI`, `CMSY`, `bold`, `italic`, `serif`, `mono`.
  2. **📐 2D Coordinate Geometry**: Baseline offsets ($\Delta oy$), glyph size ratios, column fill ratios, and pixmap ray-casting.
  3. **🔤 Unicode Character Properties**: `\p{Lu}`, `\p{Ll}`, `\p{Lo}`, `\p{N}`, and script ranges.
  4. **📊 Statistical Trigram Models (`franc-min`)**: For language identification.

### 🛡️ Rule 2: Non-Destructive Vector Preservation
- Pass 1 erasure rectangles must **only** cover `ProseSpan` bounding boxes and must be clipped against every nearby `MathObstacle`.
- Never use whole-block union rectangles that could erase vertical curly braces (`}`), fraction bars, or geometric diagrams between lines.

### 🌍 Rule 3: 17-Language Parity
- When adding domain terms to `layoutlingua/resources/glossary/`, keep every `academic_*_*.json` file synchronized so English-pivot translation works identically across all 272 language pairs.

### 🔁 Rule 4: Honest Providers
- Every provider must be genuinely available at translate time — a missing API key or runtime stops the job with an explicit error. Never silently substitute another provider.

---

## 2. 🛠 Development Workflow

### 🌐 Web Stack (TS engine, port 3000)
```bash
npm install          # 📦 dependencies
npm run dev          # 🚀 Express + Vite dev server
npm run lint         # 🧹 TypeScript strict check
npm run build        # 📦 production build
```

### 🖥 Web Studio Stack (Python engine, port 8765 + Web Studio UI, port 3000)
```bash
python -m venv .venv && .venv\Scripts\Activate.ps1   # 🐧 Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"                              # 🐍 engine + dev tools
pytest tests/ -q                                     # 🧪 274 engine tests

npm install --legacy-peer-deps                       # 📦 web studio dependencies
npm run dev                                          # 🚀 web studio + engine (localhost:3000)
```

### 📝 Commit Messages
Use [Conventional Commits](https://www.conventionalcommits.org/) — the repo history follows `feat(scope):`, `fix(scope):`, `docs:`, `chore:`.

---

## 3. ✅ Pull Request Checklist

- [ ] `npm run build` and `npm run lint` succeed with zero TypeScript or Vite errors. 🧹
- [ ] `pytest tests/ -v` passes if the Python engine changed. 🐍
- [ ] Zero hardcoded word lists introduced in the engine. 🚫
- [ ] Both engines kept in parity for any REST contract change. 🔁
- [ ] Tested on multi-page mathematical PDFs (including TOC pages, symbol tables, footnotes with links, and geometric figures) with `0` PUA leaks and `0` overflow fallbacks. 📐
- [ ] Relevant documentation (`README.md`, `ARCHITECTURE.md`, or `CHANGELOG.md`) updated. 📚
