# Research & Architectural Design: Multilingual Academic & STEM Glossary System

**Author:** LayoutLingua Core Engineering  
**Date:** October 2026  
**Status:** Approved for Implementation  
**Skills:** `/research`, `/codebase-design`, `/brainstorming`

---

## 1. Executive Summary

Document translation across academic and STEM domains (mathematics, physics, computer science, biology) frequently suffers from two major failures when using statistical machine translation (NMT):
1. **Terminology Hallucination & Literal Misinterpretation:** Specialized terms with colloquial homophones are translated into everyday idioms (e.g. Vietnamese *"Tỷ lệ thức"* $\to$ English *"Awake rate"*, *"Chỉnh hợp"* $\to$ *"Alignment"*, *"Hay A = B"* $\to$ *"Good A = B"*).
2. **Coverage Bottlenecks of Manual Glossaries:** Writing hand-crafted dictionaries for every language pair ($N \times (N-1)$) is incomplete, unscalable, and fragile.

This document investigates how leading open-source projects (**pdf2zh**, **BabelDOC**, **Wikidata STEM Ontologies**, **thosgood/maths-dictionary**) structure, harvest, and apply multilingual terminology datasets, and establishes the deep-module architecture for `GlossaryManager` in LayoutLingua.

---

## 2. Primary Source Investigation & Comparative Analysis

### 2.1 BabelDOC & pdf2zh (PDFMathTranslate)
- **Format:** BabelDOC standardizes on CSV files with columns `source,target,tgt_lng` (or 2-column `source,target`).
- **File Organization:** Files are organized by subject/domain (e.g., `math.csv`, `cs.csv`) and loaded via `--glossary-files "glossary1.csv,glossary2.csv"`.
- **Application Strategy:**
  - *For LLMs:* Matches terms in segmented text blocks and dynamically injects constraints into system prompts:
    > `"Adhere strictly to the following terminology: 'source_term' -> 'target_term'"`
  - *For MT (Google/DeepL):* Relies on pre-translation masking with opaque placeholders or post-translation normalization.
- **Auto-Extraction:** Supports 2-pass translation where Pass 1 extracts key domain terms from document headings and Pass 2 applies the cached glossary across all pages.

### 2.2 Wikidata SPARQL Ontology (The Universal Source)
Wikidata is the largest open multilingual ontology in existence. In Wikidata:
- Concepts are language-agnostic Q-IDs (e.g., `Q1135449` for *Proportion*, `Q11423` for *Permutation*, `Q141488` for *Combination*, `Q11205` for *Arithmetic mean*).
- Labels (`rdfs:label`) are maintained across 100+ languages by academic communities and verified translators.
- **SPARQL Harvesting:** A single SPARQL query against `https://query.wikidata.org/sparql`:
  ```sparql
  SELECT ?item ?lang ?label WHERE {
    ?item wdt:P31/wdt:P279* wd:Q1936384. # Mathematical concepts
    VALUES ?lang { "en" "vi" "zh" "ja" "fr" "de" "es" "ko" "ru" }
    ?item rdfs:label ?label.
    FILTER(LANG(?label) = ?lang)
  }
  ```
  allows harvesting thousands of validated academic terms with zero manual authoring.

### 2.3 Community Repositories (`thosgood/maths-dictionary`)
- The open-source project `thosgood/maths-dictionary` catalogs mathematical translations across English, French, German, and Spanish to handle non-literal mathematical vocabulary (e.g., English *field* vs French *corps* vs German *Körper*).

---

## 3. Codebase Design: Deep Module Architecture

Following the principles of **Codebase Design** (depth-as-leverage, small interface, high locality, clean seams):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       GlossaryManager Interface                             │
│  - load_effective_glossary(source_lang, target_lang, custom, domain)        │
│  - apply_glossary(text, source_lang, target_lang, custom)                   │
│  - normalize_translation(source_text, translated_text, s_lang, t_lang)      │
├─────────────────────────────────────────────────────────────────────────────┤
│                         Deep Implementation (Hidden)                         │
│  1. Multi-Format Directory Scanner:                                         │
│     - Scans layoutlingua/resources/glossary/ for:                           │
│       * JSON key-value maps                                                 │
│       * CSV 2-column (source, target)                                       │
│       * CSV 3-column (source, target, tgt_lng - BabelDOC compatibility)     │
│       * TSV term lists                                                      │
│  2. Graph Inversion & Pivot Engine:                                         │
│     - Direct pair lookup: {src}_{tgt}                                       │
│     - Bidirectional inversion: {tgt}_{src} -> inverted                      │
│     - Interlingua pivot: {src} -> en -> {tgt}                               │
│  3. Unicode & CJK-Safe Tokenizer:                                           │
│     - Smart boundaries for Latin/Accented Unicode                           │
│     - Direct matching without \b for CJK characters                         │
│  4. Automated Harvesting Script:                                            │
│     - scripts/harvest_wikidata_glossary.py queries SPARQL and dumps JSON    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Interface Leverage
Callers (`server.py`, `service.py`, `toc.py`) only call:
`GlossaryManager.normalize_translation(source_text, translated_text, s_lang, t_lang)`
and
`GlossaryManager.apply_glossary(text, s_lang, t_lang)`.

They do not know or care whether a term came from:
- A built-in JSON file
- A community-dropped CSV from `BabelDOC`
- An inverted dictionary
- An interlingua pivot route
- A user custom override string

---

## 4. Implementation Plan

1. **Multi-Format Ingestion in `GlossaryManager`:**
   - Scan all `*.json`, `*.csv`, `*.tsv` in `layoutlingua/resources/glossary/`.
   - Parse CSVs with automatic delimiter detection (`comma`, `tab`) and column headers (`source,target,tgt_lng` or raw pairs).
2. **Community Glossary Subfolder Organization:**
   - Allow domain-specific filenames: `math_en_vi.csv`, `physics_en_vi.json`, `cs_en_vi.csv`.
3. **Wikidata Harvesting Utility (`scripts/harvest_wikidata_glossary.py`):**
   - Provide an offline/CI tool that can refresh or expand mathematical and STEM terms directly from Wikidata Query Service.
4. **Verification & Tests:**
   - Comprehensive test suite covering multi-file loading, CSV ingestion, bidirectional inversion, pivot lookup, and healing of mistranslations.
