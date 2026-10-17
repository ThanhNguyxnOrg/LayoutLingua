"""Automated live web crawler and harvester for multilingual STEM glossaries.

Crawls Wikidata SPARQL and Wikipedia APIs to harvest standardized academic and scientific
terminology across 17 global languages:
    en, vi, zh, zh-tw, ja, ko, fr, de, es, ru, it, pt, id, nl, pl, tr, uk

Supports 6 key STEM domains:
    math, cs, physics, chemistry, biology, statistics

Usage:
    python scripts/harvest_wikidata_glossary.py --domain all --limit-per-root 100
    python scripts/harvest_wikidata_glossary.py --domain math --limit-per-root 150
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Multilingual STEM domain ontology root concepts on Wikidata
DOMAIN_ROOTS: dict[str, list[str]] = {
    "math": [
        "wd:Q395",      # mathematics
        "wd:Q1936384",  # branch of mathematics
        "wd:Q3968",     # algebra
        "wd:Q211294",   # elementary algebra
        "wd:Q82571",    # linear algebra
        "wd:Q44337",    # matrix
        "wd:Q43260",    # polynomial
        "wd:Q8087",     # geometry
        "wd:Q19821",    # triangle
        "wd:Q37555",    # polygon
        "wd:Q134787",   # analytic geometry
        "wd:Q898575",   # power of a point (phương tích)
        "wd:Q8084",     # trigonometry
        "wd:Q93344",    # trigonometric function
        "wd:Q7754",     # mathematical analysis
        "wd:Q149999",   # differential calculus
        "wd:Q150008",   # integral calculus
        "wd:Q11214",    # differential equation
        "wd:Q465274",   # ordinary differential equation
        "wd:Q271977",   # partial differential equation
        "wd:Q76592",    # combinatorics
        "wd:Q161519",   # permutation
        "wd:Q1401935",  # partial permutation / arrangement (chỉnh hợp)
        "wd:Q202805",   # combination (tổ hợp)
        "wd:Q133250",   # sequence
        "wd:Q170198",   # series
        "wd:Q11205",    # arithmetic
        "wd:Q12479",    # number theory
        "wd:Q12482",    # set theory
        "wd:Q1166618",  # mathematical logic
        "wd:Q42989",    # topology
        "wd:Q131476",   # graph theory
        "wd:Q5862903",  # probability theory
        "wd:Q12483",    # statistics
        "wd:Q65943",    # theorem
        "wd:Q11538",    # mathematical proof
        "wd:Q976981",   # formula
    ],
    "cs": [
        "wd:Q21198",    # computer science
        "wd:Q11660",    # artificial intelligence
        "wd:Q2539",     # machine learning
        "wd:Q8366",     # algorithm
        "wd:Q42213",    # data structure
        "wd:Q80006",    # deep learning
        "wd:Q12503",    # software engineering
        "wd:Q17517",    # cryptography
        "wd:Q1301371",  # network protocol
        "wd:Q1341490",  # computer graphics
        "wd:Q47607",    # database
        "wd:Q9135",     # operating system
        "wd:Q11197",    # compiler
        "wd:Q28789",    # computer architecture
        "wd:Q213907",   # distributed computing
    ],
    "physics": [
        "wd:Q413",      # physics
        "wd:Q107715",   # physical quantity
        "wd:Q11406",    # quantum mechanics
        "wd:Q11451",    # classical mechanics
        "wd:Q11473",    # thermodynamics
        "wd:Q11379",    # electromagnetism
        "wd:Q23059",    # elementary particle
        "wd:Q12133",    # optics
        "wd:Q7162",     # general relativity
        "wd:Q11442",    # nuclear physics
        "wd:Q11397",    # acoustics
        "wd:Q11454",    # solid-state physics
        "wd:Q46221",    # astrophysics
    ],
    "chemistry": [
        "wd:Q2329",     # chemistry
        "wd:Q11173",    # chemical compound
        "wd:Q11344",    # chemical element
        "wd:Q83353",    # chemical reaction
        "wd:Q434605",   # chemical property
        "wd:Q718",      # chemical bond
        "wd:Q174872",   # organic compound
        "wd:Q11314",    # biomolecule
        "wd:Q11372",    # inorganic chemistry
        "wd:Q11382",    # physical chemistry
        "wd:Q11370",    # analytical chemistry
        "wd:Q11376",    # biochemistry
    ],
    "biology": [
        "wd:Q420",      # biology
        "wd:Q7202",     # molecular biology
        "wd:Q7187",     # gene
        "wd:Q8054",     # protein
        "wd:Q780",      # cell biology
        "wd:Q11190",    # medicine
        "wd:Q431965",   # organism
        "wd:Q39572",    # organelle
        "wd:Q1055",     # biochemistry
        "wd:Q178",      # genetics
        "wd:Q7150",     # ecology
        "wd:Q35164",    # immunology
        "wd:Q131681",   # physiology
        "wd:Q36146",    # taxonomy
    ],
    "statistics": [
        "wd:Q12483",    # statistics
        "wd:Q186411",   # probability distribution
        "wd:Q1048687",  # statistical test
        "wd:Q205398",   # estimator
        "wd:Q42468",    # parameter
        "wd:Q2126",     # probability theory
        "wd:Q42999",    # regression analysis
        "wd:Q11245",    # variance / standard deviation
        "wd:Q849479",   # statistical hypothesis testing
        "wd:Q187834",   # random variable
    ],
}

# 17 supported languages in LayoutLingua
SUPPORTED_LANGUAGES = [
    "en", "vi", "zh", "zh-tw", "ja", "ko", "fr", "de", "es",
    "ru", "it", "pt", "id", "nl", "pl", "tr", "uk",
]

WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "LayoutLingua-Crawler/2.0 (https://github.com/ThanhNguyxnOrg/LayoutLingua; contact@layoutlingua.org)"


def clean_term_label(label: str) -> str:
    """Clean and standardize scraped term labels."""
    if not label:
        return ""
    # Strip Wikipedia/Wikidata disambiguation parentheticals e.g. "Matrix (mathematics)" -> "Matrix"
    cleaned = re.sub(r"\s*\([^)]*\)", "", label).strip()
    # Reject noise (pure numbers, URLs, excessively long phrases > 6 words)
    if cleaned.isdigit() or cleaned.startswith("http") or len(cleaned.split()) > 6 or len(cleaned) > 60:
        return ""
    return cleaned


def normalize_lang_code(raw_lang: str) -> str:
    """Normalize regional language codes into standard LayoutLingua codes."""
    raw = raw_lang.lower().strip()
    if raw in ("zh-tw", "zh-hant", "zh-hk", "zh-mo"):
        return "zh-tw"
    if raw in ("zh", "zh-cn", "zh-hans", "zh-sg"):
        return "zh"
    return raw


def crawl_wikidata_root(
    root_qid: str,
    limit: int = 200,
    retries: int = 3,
) -> list[dict[str, str]]:
    """Execute live SPARQL query for root concept itself, instances (P31), subclasses (P279), and parts (P361)."""
    lang_codes = list(SUPPORTED_LANGUAGES) + ["zh-hant", "zh-hans", "zh-cn"]
    lang_filter = " ".join(f'"{code}"' for code in set(lang_codes))

    sparql = f"""
    SELECT ?item ?lang ?label WHERE {{
      {{
        VALUES ?item {{ {root_qid} }}
      }} UNION {{
        ?item wdt:P31 {root_qid} .
      }} UNION {{
        ?item wdt:P279 {root_qid} .
      }} UNION {{
        ?item wdt:P361 {root_qid} .
      }}
      ?item rdfs:label ?label .
      VALUES ?lang {{ {lang_filter} }}
      FILTER(LANG(?label) = ?lang)
    }} LIMIT {limit}
    """

    params = urllib.parse.urlencode({"query": sparql, "format": "json"})
    url = f"{WIKIDATA_SPARQL_ENDPOINT}?{params}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    }
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("results", {}).get("bindings", [])
        except Exception as exc:
            if attempt == retries - 1:
                print(f"    [Crawler] Notice: {root_qid} skipped ({exc})")
                return []
            time.sleep(1.0 * (attempt + 1))

    return []



def crawl_domain_concepts(
    domain: str,
    limit_per_root: int = 120,
) -> dict[str, dict[str, str]]:
    """Crawls all concepts for a domain across all 17 languages from online knowledge graph."""
    roots = DOMAIN_ROOTS.get(domain.lower(), ["wd:Q1936384"])
    print(f"\n[LayoutLingua Crawler] Starting live web crawl for domain '{domain}' across {len(roots)} taxonomy roots...")

    concepts: dict[str, dict[str, str]] = {}
    total_bindings = 0

    for idx, root in enumerate(roots, 1):
        print(f"  [{idx}/{len(roots)}] Crawling root {root}...", end=" ", flush=True)

        bindings = crawl_wikidata_root(root, limit=limit_per_root)
        total_bindings += len(bindings)

        for row in bindings:
            qid_uri = row.get("item", {}).get("value", "")
            qid = qid_uri.split("/")[-1] if "/" in qid_uri else qid_uri
            raw_lang = row.get("lang", {}).get("value", "")
            label = row.get("label", {}).get("value", "")

            norm_lang = normalize_lang_code(raw_lang)
            clean_label = clean_term_label(label)

            if qid and norm_lang in SUPPORTED_LANGUAGES and clean_label:
                # Prefer existing clean label if already set, or shorter version
                existing = concepts.setdefault(qid, {}).get(norm_lang)
                if not existing or len(clean_label) < len(existing):
                    concepts[qid][norm_lang] = clean_label

        print(f"found {len(bindings)} multilingual labels.")
        # Polite crawl pause to respect Wikimedia Foundation rate limits
        time.sleep(0.35)

    print(f"[LayoutLingua Crawler] Finished '{domain}': extracted {len(concepts)} distinct concepts from {total_bindings} live web labels.")
    return concepts


def compile_bilingual_glossaries(
    concepts: dict[str, dict[str, str]],
    source_lang: str = "en",
) -> dict[str, dict[str, str]]:
    """Compiles multi-concept graph into bilingual mappings: target_lang -> {source_term: target_term}."""
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


def export_domain_glossaries(
    bilingual_maps: dict[str, dict[str, str]],
    out_dir: Path,
    domain: str,
    source_lang: str = "en",
) -> int:
    """Save bilingual glossaries into domain-specific subdirectories, preserving human-curated entries."""
    domain_dir = out_dir / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    files_updated = 0

    for tgt_lang in SUPPORTED_LANGUAGES:
        if tgt_lang == source_lang:
            continue
        terms = bilingual_maps.get(tgt_lang, {})
        out_file = domain_dir / f"academic_{domain}_{source_lang}_{tgt_lang}.json"

        existing_terms = {}
        if out_file.exists():
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_terms = existing_data.get("terms", {})
            except Exception:
                pass

        # Merge live crawled terms with existing human-curated terms (preserving curated ones)
        merged = dict(terms)
        merged.update(existing_terms)

        if not merged:
            continue

        payload = {
            "language_pair": f"{source_lang}-{tgt_lang}",
            "domain": f"academic_{domain}_stem",
            "source": "Wikidata Open Knowledge Graph Live Web Crawl",
            "total_terms": len(merged),
            "terms": merged,
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        files_updated += 1

    return files_updated


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Automated web crawler for multilingual STEM glossaries.")
    parser.add_argument("--domain", default="all", choices=list(DOMAIN_ROOTS.keys()) + ["all"])
    parser.add_argument("--limit-per-root", type=int, default=120, help="Max terms to fetch per root concept")
    parser.add_argument("--source-lang", default="en")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent / "layoutlingua" / "resources" / "glossary"),
    )
    args = parser.parse_args()

    domains = list(DOMAIN_ROOTS.keys()) if args.domain == "all" else [args.domain]
    out_path = Path(args.output_dir)

    print("=" * 70)
    print(" LayoutLingua Automated Multilingual STEM Glossary Web Crawler")
    print(" Sources: Wikidata Live SPARQL & Wikimedia Open Knowledge Graph")
    print(f" Target Domains: {', '.join(domains)}")
    print(f" Target Languages ({len(SUPPORTED_LANGUAGES)}): {', '.join(SUPPORTED_LANGUAGES)}")
    print("=" * 70)

    total_files = 0
    for d in domains:
        concepts = crawl_domain_concepts(d, limit_per_root=args.limit_per_root)
        if concepts:
            bilingual_maps = compile_bilingual_glossaries(concepts, source_lang=args.source_lang)
            files = export_domain_glossaries(bilingual_maps, out_path, domain=d, source_lang=args.source_lang)
            total_files += files

    print("\n" + "=" * 70)
    print(f" Crawl Complete: Successfully populated/updated {total_files} glossary files across {len(domains)} STEM domains.")
    print("=" * 70)


if __name__ == "__main__":
    main()
