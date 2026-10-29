# Design Specification: AI Studio Zip Integration, Cleanup, and Documentation Sync

**Date:** 2026-10-29  
**Status:** Approved in Principle  
**Author:** AI Pair Programmer & User  
**Target:** LayoutLingua Repository (`D:\Code\LayoutLingua`)  

---

## 1. Overview & Context

A new archive (`layoutlingua.zip`) was exported from Google AI Studio (`https://ai.studio/apps/a5edd4c4-9c0e-4e88-be38-024739b08958`) containing substantial enhancements to the Python engine (extended parsing, hyphenation, multi-family fonts, session caching) alongside UI improvements and test suites.

However, the archive also contains scaffold files from AI Studio's temporary web runtime (Express `server.ts`, root `index.html`, `bun.lock`, `package.json`, generic 15-line `README.md`, etc.). Because LayoutLingua committed to a **Single-runtime Desktop App architecture** (commit `497432b`), these web scaffold files are obsolete and must not pollute the repository.

This design specifies the precise integration of all high-value code, font assets, and tests, the selective porting of UI enhancements to `desktop/src/`, the safe cleanup of junk files, and the comprehensive synchronization of all markdown documentation.

---

## 2. Core Python Engine Integration (`layoutlingua/`)

### 2.1 Parser (`layoutlingua/core/parser.py`)
- Incorporate full 1,946-line parser enhancements:
  - `_split_lines_across_horizontal_gaps`: column split resolution across whitespace gaps.
  - `_extract_page_vertical_dividers`: detection of vertical graphic divider strokes.
  - `_merge_vertical_hyphenated_fragments`: rejoining syllables broken across lines with soft/hard hyphens.
  - `_tight_line_x_bounds`: tight bounding box calculation for refined line grouping.
  - `_normalize_raw_block_1d_scripts`: baseline and sub/superscript script normalization.

### 2.2 Typesetting Engine & Font Assets (`layoutlingua/typesetting/`)
- **Assets (`layoutlingua/typesetting/assets/fonts/`)**:
  - Extract and place all 21 TrueType font files:
    - `DejaVuSans-BoldOblique.ttf`, `DejaVuSans-Oblique.ttf`, `DejaVuSansMono.ttf`, `DejaVuSansMono-Bold.ttf`, `DejaVuSansMono-Oblique.ttf`, `DejaVuSansMono-BoldOblique.ttf`
    - `DejaVuSerif.ttf`, `DejaVuSerif-Bold.ttf`, `DejaVuSerif-Italic.ttf`, `DejaVuSerif-BoldItalic.ttf`, `DejaVuSerifCondensed-Bold.ttf`, `DejaVuSerifCondensed-Italic.ttf`, `DejaVuSerifCondensed-BoldItalic.ttf`
    - `FreeSans.ttf`, `FreeSansBold.ttf`, `FreeSansOblique.ttf`, `FreeSansBoldOblique.ttf`
    - `FreeSerif.ttf`, `FreeSerifBold.ttf`, `FreeSerifItalic.ttf`, `FreeSerifBoldItalic.ttf`
- **Fonts (`layoutlingua/typesetting/fonts.py`)**:
  - Support multi-family font selection (`DejaVuSans`, `DejaVuSerif`, `FreeSans`, `FreeSerif`, `DejaVuSansMono`).
  - Configure CJK fallback aliases (`CJK_FONT_ALIASES`, `CJK_EMBED_FONTS`).
- **Fitting (`layoutlingua/typesetting/fitting.py`)**:
  - Add phonological syllabic hyphenation (`hyphenate_word`) for Western/Latin languages.
  - Add `adapt_narrow_multiline_if_needed`, `_longest_word_fits`, `_extract_non_cjk_words`, `_try_textbox`.
- **Engine (`layoutlingua/typesetting/engine.py`)**:
  - Implement `_insert_text_with_cjk_fallback` for mixed-script rendering without tofu boxes.

### 2.3 Formula Word Tokenization (`layoutlingua/processing/formula/word_tokens.py`)
- Sync clean token classifier matching the 265-test suite, resolving recent test regressions on variable clusters.

### 2.4 Server & Session Recovery (`layoutlingua/server.py`)
- Implement session persistence & recovery:
  - `_ensure_session_doc_ir`: retrieve parsed IR from disk cache when memory cache expires.
  - `/api/recent-sessions`: return list of cached sessions for frontend rehydration.
  - `_is_safe_export_directory` & `_validate_provider_base_url`: hardening against arbitrary path traversals or unsafe SSRF.

### 2.5 Resources & Glossaries (`layoutlingua/resources/glossary/math/`)
- Update and expand 9 language mathematical glossaries.

---

## 3. Desktop UI Integration (`desktop/src/`)

Selectively port UI improvements from `zip/src/` into `desktop/src/` while strictly maintaining desktop contracts:

1. **`desktop/src/components/OpenScreen.tsx`**:
   - Query `/api/recent-sessions` on mount to restore persistent sessions across application reboots.
   - Support `errDetail` for informative error feedback.
2. **`desktop/src/components/PdfPage.tsx`**:
   - Add viewport intersection observer for lazy page rendering (`isVisible`).
   - Add retry mechanism (`retryCount`) for heavy PDF pages.
   - Accept `targetLang` prop.
3. **`desktop/src/components/Workspace.tsx`**:
   - Add `langCodeMap` covering 17+ languages (Chinese, Japanese, Korean, French, German, Spanish, Russian, Vietnamese, etc.).
   - Support rich layout region inspection (coordinates and bounding box in details pane).
4. **Preserved Desktop Invariants**:
   - **`desktop/src/services/api.ts`**: MUST remain `API_BASE = 'http://127.0.0.1:8765'`.
   - **`desktop/src/components/ExportDialog.tsx`**: Retain desktop-native folder picker and timeout fallback.

---

## 4. Test Suite & Verification

1. Add the 3 new test files from the zip into `tests/`:
   - `tests/test_multilingual_layout_and_hyphenation.py`
   - `tests/test_glossary_and_single_line_fitting.py`
   - `tests/test_ts_engine_port.py`
2. Run full pytest suite: Target **265 passed, 0 failed, 0 warnings**.
3. Run desktop UI TypeScript check (`npm run build` or `tsc --noEmit` in `desktop/`).

---

## 5. Junk File Cleanup Policy

### 5.1 Files to Discard (from Zip / Unused Web Scaffold)
The following files from the zip are scaffolding for Google AI Studio web hosting and must NOT be added to root:
- `bun.lock`
- `package.json` (AI Studio `react-example`)
- `server.ts`
- `index.html`
- `public/`
- Root `src/` (already mapped into `desktop/src/`)
- Zip's `README.md` (AI Studio generic)
- Zip's `.gitignore` (AI Studio generic)
- Any temporary script such as `test_api.mjs`

### 5.2 Repository Artifacts to Clean
- Untracked test output artifacts (e.g., `tests/test_live_output.png`).
- Stale caches or temp files.
- `layoutlingua.zip` can be safely removed once integration is verified.

---

## 6. Documentation Synchronization

Update project documentation to reflect all newly incorporated capabilities:
- **`README.md`**:
  - Document multi-family font selection (`DejaVuSans`, `DejaVuSerif`, `FreeSans`, `FreeSerif`, `DejaVuSansMono`).
  - Document CJK mixed-script fallback rendering.
  - Document syllabic hyphenation and narrow-column text fitting.
  - Update test count badge / section to 265 passed tests.
- **`docs/ARCHITECTURE.md`**:
  - Detail the updated Typesetting Engine font pipeline and CJK fallback cascade.
  - Detail the Server Disk Cache and session recovery architecture.
- **`docs/CHANGELOG.md`**:
  - Record the v2.0 enhancements (font families, hyphenation, session caching, expanded test suite).
- **`docs/API_REFERENCE.md`**:
  - Document the `/api/recent-sessions` endpoint.
