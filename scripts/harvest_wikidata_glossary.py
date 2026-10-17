"""Automated community harvester for Wikidata multilingual STEM and mathematics ontologies.

Queries the public Wikidata Query Service (SPARQL) to extract standardized academic and
mathematical terminology across languages (English, Vietnamese, Chinese, Japanese, French,
German, Spanish, etc.) and writes production-ready glossary files into layoutlingua/resources/glossary/.

Usage:
    python scripts/harvest_wikidata_glossary.py --domain math --limit 200
    python scripts/harvest_wikidata_glossary.py --domain cs --limit 200
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

# Multi-root concepts for comprehensive domain coverage
DOMAIN_ROOTS = {
    "math": [
        "wd:Q1936384",  # mathematical concept
        "wd:Q21199",    # mathematical object (matrix, vector, set, group, ring...)
        "wd:Q11348",    # mathematical operation (addition, integration, derivative...)
        "wd:Q65943",    # mathematical theorem
        "wd:Q8078",     # algebra
        "wd:Q1845",     # geometry
        "wd:Q395",      # mathematics
    ],
    "cs": [
        "wd:Q21198",    # computer science
        "wd:Q11660",    # artificial intelligence
        "wd:Q2539",     # machine learning
        "wd:Q8366",     # algorithm
        "wd:Q42213",    # data structure
        "wd:Q80006",    # deep learning
    ],
    "physics": [
        "wd:Q413",      # physics
        "wd:Q107715",   # physical quantity
        "wd:Q11406",    # quantum mechanics
        "wd:Q11451",    # classical mechanics
    ],
    "chemistry": [
        "wd:Q2329",     # chemistry
        "wd:Q11173",    # chemical compound
        "wd:Q11344",    # chemical element
        "wd:Q83353",    # chemical reaction
        "wd:Q434605",   # chemical property
        "wd:Q718",      # chemical bond
    ],
    "biology": [
        "wd:Q420",      # biology
        "wd:Q7202",     # molecular biology
        "wd:Q7187",     # gene
        "wd:Q8054",     # protein
        "wd:Q780",      # cell biology
        "wd:Q11190",    # medicine
        "wd:Q431965",   # organism
    ],
    "statistics": [
        "wd:Q12483",    # statistics
        "wd:Q186411",   # probability distribution
        "wd:Q1048687",  # statistical test
    ],
}

SUPPORTED_LANGUAGES = ["en", "vi", "zh", "ja", "fr", "de", "es"]
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"


def build_sparql_query(domain: str, limit: int = 1000) -> str:
    roots = DOMAIN_ROOTS.get(domain.lower(), ["wd:Q1936384"])
    roots_str = " ".join(roots)
    lang_values = " ".join(f'"{code}"' for code in SUPPORTED_LANGUAGES)

    query = f"""
    SELECT DISTINCT ?item ?lang ?label WHERE {{
      VALUES ?root {{ {roots_str} }}
      ?item (wdt:P31|wdt:P279) ?root .
      VALUES ?lang {{ {lang_values} }}
      ?item rdfs:label ?label .
      FILTER(LANG(?label) = ?lang)
    }}
    LIMIT {limit}
    """
    return query


def fetch_wikidata_terms(domain: str, limit: int = 250) -> dict[str, dict[str, str]]:
    """Fetch multilingual concept labels from Wikidata SPARQL.

    Returns:
        dict mapping concept item ID (QID) -> {lang_code: label_text}
    """
    sparql = build_sparql_query(domain, limit)
    params = urllib.parse.urlencode({"query": sparql, "format": "json"})
    url = f"{WIKIDATA_SPARQL_ENDPOINT}?{params}"

    headers = {
        "User-Agent": "LayoutLingua-GlossaryHarvester/2.0 (https://github.com/ThanhNguyxnOrg/LayoutLingua; mailto:contact@layoutlingua.org)",
        "Accept": "application/sparql-results+json",
    }

    req = urllib.request.Request(url, headers=headers)
    print(f"[LayoutLingua] Fetching {domain} terminology from Wikidata SPARQL...")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[LayoutLingua] Notice: Could not connect to Wikidata SPARQL endpoint ({exc}).")
        return {}

    bindings = data.get("results", {}).get("bindings", [])
    concepts: dict[str, dict[str, str]] = {}

    for row in bindings:
        qid_uri = row.get("item", {}).get("value", "")
        qid = qid_uri.split("/")[-1] if "/" in qid_uri else qid_uri
        lang = row.get("lang", {}).get("value", "")
        label = row.get("label", {}).get("value", "")

        if qid and lang and label:
            clean_label = label.strip()
            # Exclude descriptions or overly verbose Wikipedia titles containing parentheses disambiguation
            if clean_label and "(" not in clean_label:
                concepts.setdefault(qid, {})[lang] = clean_label

    print(f"[LayoutLingua] Successfully retrieved {len(concepts)} concepts across languages.")
    return concepts


def compile_bilingual_glossaries(
    concepts: dict[str, dict[str, str]],
    source_lang: str = "en",
    domain: str = "math",
) -> dict[str, dict[str, str]]:
    """Compile multi-concept records into bilingual pairs: {target_lang: {src_term: tgt_term}}."""
    bilingual_maps: dict[str, dict[str, str]] = {}

    for qid, lang_dict in concepts.items():
        src_term = lang_dict.get(source_lang)
        if not src_term:
            continue

        for tgt_lang, tgt_term in lang_dict.items():
            if tgt_lang == source_lang or not tgt_term:
                continue
            pair_dict = bilingual_maps.setdefault(tgt_lang, {})
            # Prefer shorter, standard terms
            if src_term not in pair_dict or len(tgt_term) < len(pair_dict[src_term]):
                pair_dict[src_term] = tgt_term

    return bilingual_maps


def export_glossaries(
    bilingual_maps: dict[str, dict[str, str]],
    out_dir: Path,
    source_lang: str = "en",
    domain: str = "math",
) -> None:
    domain_dir = out_dir / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    for tgt_lang, terms in bilingual_maps.items():
        if not terms:
            continue
        out_file = domain_dir / f"academic_{domain}_{source_lang}_{tgt_lang}.json"

        existing_terms = {}
        if out_file.exists():
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_terms = existing_data.get("terms", {})
            except Exception:
                pass

        # Merge, preserving human-curated terms over automated harvest
        merged = dict(terms)
        merged.update(existing_terms)

        payload = {
            "language_pair": f"{source_lang}-{tgt_lang}",
            "domain": f"academic_{domain}_stem",
            "source": "Wikidata Open Ontology + LayoutLingua Community",
            "total_terms": len(merged),
            "terms": merged,
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"[LayoutLingua] Updated {out_file.name}: {len(merged)} terms.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest multilingual STEM glossaries from Wikidata.")
    parser.add_argument("--domain", default="math", choices=list(DOMAIN_ROOTS.keys()))
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--source-lang", default="en")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent / "layoutlingua" / "resources" / "glossary"),
    )
    args = parser.parse_args()

    concepts = fetch_wikidata_terms(args.domain, limit=args.limit)
    if concepts:
        bilingual_maps = compile_bilingual_glossaries(concepts, source_lang=args.source_lang, domain=args.domain)
        export_glossaries(
            bilingual_maps,
            out_dir=Path(args.output_dir),
            source_lang=args.source_lang,
            domain=args.domain,
        )


if __name__ == "__main__":
    main()
