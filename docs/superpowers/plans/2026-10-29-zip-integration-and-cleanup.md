# Zip Integration, Desktop UI Sync, Cleanup, and Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate high-value engine and UI enhancements from `layoutlingua.zip` into the single-runtime architecture, achieve 100% test pass (265/265), clean up obsolete AI Studio web scaffold files, and synchronize all project documentation.

**Architecture:** Incrementally update the Python typesetter, font registry, core parser, and server cache; selectively merge desktop UI improvements into `desktop/src/` while strictly keeping the desktop IPC contract; discard temporary AI Studio scaffold files; and update all project markdown files.

**Tech Stack:** Python 3.10+, PyMuPDF (fitz), React 19, TypeScript 5+, Vite, TailwindCSS, Tauri.

**Spec:** [2026-10-29-zip-integration-and-cleanup-design.md](file:///d:/Code/LayoutLingua/docs/superpowers/specs/2026-10-29-zip-integration-and-cleanup-design.md)

## Global Constraints

- Never re-introduce the Node/TS server or root web runtime; `layoutlingua/` is the single engine and `desktop/src/` is the single UI.
- `desktop/src/services/api.ts` MUST maintain `API_BASE = 'http://127.0.0.1:8765'`.
- All 265 test cases must pass cleanly without regressions.
- Preserve existing docstrings, copyright headers, and formatting.

## Review Focus

1. **Font loading failure:** Missing or corrupted TTF files in `layoutlingua/typesetting/assets/fonts/` cause fallbacks or runtime errors. Verify checksums/presence for all 21 fonts.
2. **Desktop API breakage:** If `api.ts` is changed to relative URLs, Tauri desktop fails to contact the engine. Verify `API_BASE` points to `http://127.0.0.1:8765`.
3. **Session Cache directory traversal:** Malicious or malformed `doc_id` in `/api/recent-sessions` or `/api/save`. Verify `_sanitize_doc_id` and `_is_safe_export_directory` prevent escapes.
4. **CJK Fallback rendering:** Mixing CJK characters in Latin text must not produce replacement squares (tofu) or crash PyMuPDF.
5. **Overwritten root README:** AI Studio generic 15-line README must never overwrite the real 20KB repository documentation.

---

### Task 1: Font Assets & Typesetting Multi-Family Engine

**Files:**
- Create: `layoutlingua/typesetting/assets/fonts/*.ttf` (21 TTF files from zip)
- Modify: `layoutlingua/typesetting/fonts.py`
- Modify: `layoutlingua/typesetting/fitting.py`
- Modify: `layoutlingua/typesetting/engine.py`

**Interfaces:**
- Consumes: TTF font files on disk
- Produces: `CJK_FONT_ALIASES`, `hyphenate_word`, `adapt_narrow_multiline_if_needed`, `_insert_text_with_cjk_fallback`

- [ ] **Step 1: Extract the 21 TrueType font files from layoutlingua.zip into layoutlingua/typesetting/assets/fonts/**
- [ ] **Step 2: Update fonts.py with CJK font aliases and multi-family font variant mapping**
- [ ] **Step 3: Update fitting.py with phonological syllabic hyphenation and narrow multiline adaptation**
- [ ] **Step 4: Update engine.py with CJK text insertion fallback**
- [ ] **Step 5: Run typesetting tests to verify:**
  Run: `.venv\Scripts\pytest tests/test_slice4a_typesetting.py tests/test_slice4b_fitting_and_metrics.py -v`
  Expected: All pass
- [ ] **Step 6: Commit:**
  `git add layoutlingua/typesetting/`
  `git commit -m "feat(typeset): add multi-family font assets, CJK fallback, and syllabic hyphenation"`

---

### Task 2: Core Parser Enhancements & Token Classifier Synchronization

**Files:**
- Modify: `layoutlingua/core/parser.py`
- Modify: `layoutlingua/processing/formula/word_tokens.py`
- Modify: `layoutlingua/processing/formula/isolator.py`
- Modify: `layoutlingua/processing/text_sanitizer.py`

**Interfaces:**
- Consumes: PyMuPDF rawdict page structures
- Produces: Enhanced DocumentIR with divider line detection, gap splitting, and stable formula token classification

- [ ] **Step 1: Update layoutlingua/core/parser.py with full 1,946-line implementation from zip**
- [ ] **Step 2: Sync word_tokens.py and isolator.py from zip to restore 100% token classification accuracy**
- [ ] **Step 3: Update text_sanitizer.py from zip**
- [ ] **Step 4: Run parser and formula tests:**
  Run: `.venv\Scripts\pytest tests/test_slice2_processing.py tests/test_academic_e2e_pipeline.py -v`
  Expected: All pass (resolves the 2 previously failing tests)
- [ ] **Step 5: Commit:**
  `git add layoutlingua/core/parser.py layoutlingua/processing/`
  `git commit -m "feat(parser): integrate vertical dividers, gap splitting, and faithful formula token classifier"`

---

### Task 3: Server Session Recovery & Mathematical Glossaries

**Files:**
- Modify: `layoutlingua/server.py`
- Modify: `layoutlingua/translation/glossary.py`
- Modify: `layoutlingua/translation/service.py`
- Modify: `layoutlingua/resources/glossary/math/academic_math_en_*.json`

**Interfaces:**
- Consumes: Disk cache directories
- Produces: `/api/recent-sessions` endpoint, safe export validation, updated glossaries

- [ ] **Step 1: Update layoutlingua/server.py with session recovery, safe export checks, and recent sessions endpoint**
- [ ] **Step 2: Update glossary.py and service.py**
- [ ] **Step 3: Update mathematical glossary JSON resources from zip**
- [ ] **Step 4: Run server and glossary tests:**
  Run: `.venv\Scripts\pytest tests/test_glossary.py tests/test_translation_cache.py -v`
  Expected: All pass
- [ ] **Step 5: Commit:**
  `git add layoutlingua/server.py layoutlingua/translation/ layoutlingua/resources/`
  `git commit -m "feat(server): add disk session recovery, safe export guards, and expanded math glossaries"`

---

### Task 4: Integrate New Test Suites & Complete Python Test Verification

**Files:**
- Create: `tests/test_multilingual_layout_and_hyphenation.py`
- Create: `tests/test_glossary_and_single_line_fitting.py`
- Create: `tests/test_ts_engine_port.py`

**Interfaces:**
- Consumes: Complete `layoutlingua` package
- Produces: 265 verified test cases

- [ ] **Step 1: Extract 3 new test files from zip into tests/**
- [ ] **Step 2: Run the full pytest test suite across all 38 test files:**
  Run: `.venv\Scripts\pytest -q`
  Expected: **265 passed in ~30s**
- [ ] **Step 3: Commit:**
  `git add tests/`
  `git commit -m "test: add test suites for multilingual hyphenation, glossary healing, and engine parity"`

---

### Task 5: Desktop UI Selective Integration & Verification

**Files:**
- Modify: `desktop/src/components/OpenScreen.tsx`
- Modify: `desktop/src/components/PdfPage.tsx`
- Modify: `desktop/src/components/Workspace.tsx`

**Interfaces:**
- Consumes: `/api/recent-sessions`, `/api/page`
- Produces: Enhanced desktop UI with session rehydration, lazy rendering, and 17+ language mapping

- [ ] **Step 1: Update desktop/src/components/OpenScreen.tsx with server session discovery and error detail handling**
- [ ] **Step 2: Update desktop/src/components/PdfPage.tsx with IntersectionObserver lazy rendering and retry handling**
- [ ] **Step 3: Update desktop/src/components/Workspace.tsx with langCodeMap and layout inspection**
- [ ] **Step 4: Verify desktop/src/services/api.ts remains pointing to http://127.0.0.1:8765**
- [ ] **Step 5: Verify desktop/src/components/ExportDialog.tsx retains native folder picker**
- [ ] **Step 6: Run desktop TypeScript check:**
  Run: `cd desktop; npm run build`
  Expected: Successful compilation without errors
- [ ] **Step 7: Commit:**
  `git add desktop/src/`
  `git commit -m "feat(desktop): add session rehydration, lazy page loading, and multilingual language mapping"`

---

### Task 6: Repository Cleanup

**Files:**
- Delete: `tests/test_live_output.png`
- Remove: `layoutlingua.zip` (or archive after user verification)
- Ensure no untracked AI Studio root files (`server.ts`, `bun.lock`, `package.json`, `index.html`, root `src/`, root `public/`, `test_api.mjs`) exist

- [ ] **Step 1: Remove untracked artifact tests/test_live_output.png**
- [ ] **Step 2: Verify git status is clean and no root AI Studio files were leaked**
- [ ] **Step 3: Remove layoutlingua.zip**
- [ ] **Step 4: Commit cleanup:**
  `git commit -m "chore: clean up test artifacts and temporary archives"` (if any tracked changes)

---

### Task 7: Documentation Synchronization

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/API_REFERENCE.md`

**Interfaces:**
- Consumes: Integrated codebase capabilities
- Produces: Up-to-date accurate documentation for developers and users

- [ ] **Step 1: Update README.md with multi-family fonts, CJK fallback, hyphenation, session caching, and 265 test count**
- [ ] **Step 2: Update docs/ARCHITECTURE.md with typography pipeline and session cache architecture**
- [ ] **Step 3: Update docs/CHANGELOG.md documenting v2.0 improvements**
- [ ] **Step 4: Update docs/API_REFERENCE.md with /api/recent-sessions**
- [ ] **Step 5: Commit documentation changes:**
  `git add README.md docs/`
  `git commit -m "docs: sync architecture, changelog, api reference, and readme for multi-family engine and session recovery"`

