# Research: Multilingual Academic Glossary Expansion Across 17 Research Languages

## 1. Background & Objectives
In LayoutLingua 2.0, the UI and typesetting engine were expanded from 7 to 17 global research languages:
- **Latin / European & Southeast Asian:** English (`en`), Vietnamese (`vi`), French (`fr`), German (`de`), Spanish (`es`), Italian (`it`), Portuguese (`pt`), Indonesian (`id`), Dutch (`nl`), Polish (`pl`), Turkish (`tr`).
- **Pan-CJK:** Simplified Chinese (`zh`), Traditional Chinese (`zh-tw`), Japanese (`ja`), Korean (`ko`).
- **Cyrillic:** Russian (`ru`), Ukrainian (`uk`).

To ensure that machine translation preserves domain-specific terminology across all STEM disciplines (e.g. avoiding "Awake rate" for Wake rate, or preserving mathematical/physical terms), the community glossaries in `layoutlingua/resources/glossary/` must be expanded to cover all 17 languages across all 6 core academic domains:
1. `math` (Mathematical concepts, theorems, operations, objects)
2. `physics` (Physical quantities, mechanics, quantum theory, thermodynamics)
3. `chemistry` (Compounds, elements, reactions, molecular bonds)
4. `biology` (Cell biology, genetics, molecular biology, physiology)
5. `cs` (Computer science, AI, machine learning, algorithms, data structures)
6. `statistics` (Probability distributions, estimators, tests, regression)

---

## 2. Primary Source Analysis: Wikidata SPARQL Endpoint

### 2.1 Wikidata Multi-Label Architecture
Wikidata items (QIDs) represent language-agnostic semantic concepts. Each item contains language-tagged labels (`rdfs:label`) following BCP-47 / ISO-639 language subtags:
- `en`: English
- `vi`: Vietnamese
- `zh`: Chinese (Simplified / Common)
- `zh-tw` / `zh-hant`: Chinese (Traditional)
- `ja`: Japanese
- `ko`: Korean
- `fr`: French
- `de`: German
- `es`: Spanish
- `ru`: Russian
- `it`: Italian
- `pt`: Portuguese
- `id`: Indonesian
- `nl`: Dutch
- `pl`: Polish
- `tr`: Turkish
- `uk`: Ukrainian

### 2.2 Query Structure
The SPARQL query uses `VALUES ?lang { ... }` with `?item (wdt:P31|wdt:P279) ?root` to retrieve labels across all 17 language codes in a single optimized pass per domain, ensuring identical semantic concept alignment (QID equivalence) across every language pair.

---

## 3. Interlingua Pivot Routing & Dual Inversion
With $N = 17$ languages, direct bilingual pairs would require $17 \times 16 = 272$ files per domain ($1,632$ files total), which is redundant.
By following the BabelDOC / Interlingua standard:
1. **Canonical Pivot:** English (`en`) is the central interlingua hub.
2. **File Footprint:** Only $N - 1 = 16$ JSON files are needed per domain ($16 \times 6 = 96$ files total).
3. **Dynamic Bidirectional Inversion:** `GlossaryManager` automatically inverts `academic_{domain}_en_{lang}.json` to provide `{lang} -> en` without duplicating files on disk.
4. **Pivot Path Routing:** Any non-English pair (e.g., `vi -> de`, `ko -> vi`, `ru -> fr`) is automatically resolved at runtime via the two-hop composition:
   $$\text{Term}_{A \rightarrow B} = \text{Pivot}_{A \rightarrow \text{en}} \circ \text{Pivot}_{\text{en} \rightarrow B}$$

---

## 4. Execution Plan
1. Update `SUPPORTED_LANGUAGES` in `scripts/harvest_wikidata_glossary.py` to all 17 ISO codes.
2. Execute the harvester across all 6 domains with offline concept fallback guarantees for network resiliency.
3. Verify recursive multi-folder glossary loading via `pytest tests/test_glossary.py`.
