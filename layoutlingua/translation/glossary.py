"""Academic and mathematical terminology glossary management with token-safe substitution."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

_RESOURCE_DIR = Path(__file__).parent.parent / "resources" / "glossary"
_FORMULA_OR_TAG_PATTERN = re.compile(r"(⟦LL_FORMULA_\d+⟧|⟦LL_REF_\d+⟧|⟦LL_ABBR_\d+⟧|⟦SPLIT_SEP⟧|</?b\d+>)")


class GlossaryManager:
    """Manages domain-specific glossaries and token-safe terminology replacements."""

    _builtin_cache: dict[str, dict[str, str]] = {}

    @classmethod
    def _parse_file_terms(cls, file_path: Path, target_lang_code: str = "") -> dict[str, str]:
        """Parse terms from a JSON, CSV (including BabelDOC 3-column), or TSV file."""
        if not file_path.exists():
            return {}
        suffix = file_path.suffix.lower()
        terms: dict[str, str] = {}
        t_clean = (target_lang_code or "").lower().strip()

        if suffix == ".json":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        raw_terms = data.get("terms", data)
                        if isinstance(raw_terms, dict):
                            for k, v in raw_terms.items():
                                if str(k).strip() and str(v).strip():
                                    terms[str(k).strip()] = str(v).strip()
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                s = item.get("source", "").strip()
                                t = item.get("target", "").strip()
                                tgt_lng = item.get("tgt_lng", "").strip().lower()[:2]
                                if s and t and (not t_clean or not tgt_lng or tgt_lng == t_clean):
                                    terms[s] = t
            except Exception:
                pass
        elif suffix in (".csv", ".tsv"):
            try:
                import csv

                delimiter = "\t" if suffix == ".tsv" else ","
                with open(file_path, "r", encoding="utf-8", newline="") as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    first_row = next(reader, None)
                    if not first_row:
                        return terms
                    headers = [h.strip().lower() for h in first_row]
                    if "source" in headers and "target" in headers:
                        s_idx = headers.index("source")
                        t_idx = headers.index("target")
                        lng_idx = headers.index("tgt_lng") if "tgt_lng" in headers else -1
                        for row in reader:
                            if len(row) > max(s_idx, t_idx):
                                s = row[s_idx].strip()
                                t = row[t_idx].strip()
                                lng = row[lng_idx].strip().lower()[:2] if lng_idx != -1 and len(row) > lng_idx else ""
                                if s and t and (not t_clean or not lng or lng == t_clean):
                                    terms[s] = t
                    else:
                        # Raw 2-column format without named headers
                        if len(first_row) >= 2 and first_row[0].strip() and first_row[1].strip():
                            terms[first_row[0].strip()] = first_row[1].strip()
                        for row in reader:
                            if len(row) >= 2 and row[0].strip() and row[1].strip():
                                terms[row[0].strip()] = row[1].strip()
            except Exception:
                pass

        return terms

    @classmethod
    def load_builtin_glossary(cls, source_lang: str = "en", target_lang: str = "vi") -> dict[str, str]:
        """Load built-in academic and STEM glossary for the given language pair with multi-file scanning, bidirectional inversion, and pivot support."""
        s_lang = (source_lang or "en").lower().strip()
        t_lang = (target_lang or "vi").lower().strip()
        lang_map = {
            "vietnamese": "vi",
            "chinese": "zh",
            "chinese-simplified": "zh",
            "zh": "zh",
            "zh-cn": "zh",
            "zh-hans": "zh",
            "chinese-traditional": "zh-tw",
            "zh-tw": "zh-tw",
            "zh-hant": "zh-tw",
            "japanese": "ja",
            "ja": "ja",
            "korean": "ko",
            "ko": "ko",
            "german": "de",
            "de": "de",
            "french": "fr",
            "fr": "fr",
            "spanish": "es",
            "es": "es",
            "english": "en",
            "en": "en",
            "russian": "ru",
            "ru": "ru",
            "italian": "it",
            "it": "it",
            "portuguese": "pt",
            "pt": "pt",
            "indonesian": "id",
            "id": "id",
            "dutch": "nl",
            "nl": "nl",
            "polish": "pl",
            "pl": "pl",
            "turkish": "tr",
            "tr": "tr",
            "ukrainian": "uk",
            "uk": "uk",
        }
        s_code = lang_map.get(s_lang, s_lang)
        t_code = lang_map.get(t_lang, t_lang)
        if s_code == t_code:
            return {}

        cache_key = f"{s_code}_{t_code}"
        if cache_key in cls._builtin_cache:
            return cls._builtin_cache[cache_key].copy()

        scanned_terms: dict[str, str] = {}
        if _RESOURCE_DIR.exists():
            for f in sorted(_RESOURCE_DIR.rglob("*")):
                if not f.is_file() or f.suffix.lower() not in (".json", ".csv", ".tsv"):
                    continue
                fname = f.stem.lower()

                # Direct match: e.g. academic_math_en_vi, community_ai_cs_en_vi, math_en_vi
                if fname.endswith(f"_{s_code}_{t_code}"):
                    scanned_terms.update(cls._parse_file_terms(f, t_code))
                # Inverse match: e.g. academic_math_vi_en inverted from en_vi
                elif fname.endswith(f"_{t_code}_{s_code}"):
                    inv_terms = cls._parse_file_terms(f, s_code)
                    for k, v in inv_terms.items():
                        if v and k and v not in scanned_terms:
                            scanned_terms[v] = k
                # General domain file with tgt_lng column (e.g. math.csv, ai.csv)
                elif not any(fname.endswith(f"_{s}_{t}") for s in lang_map.values() for t in lang_map.values()):
                    file_terms = cls._parse_file_terms(f, t_code)
                    scanned_terms.update(file_terms)

        if scanned_terms:
            cls._builtin_cache[cache_key] = scanned_terms
            return scanned_terms.copy()

        # Pivot via English: (s_code -> en) + (en -> t_code)
        if s_code != "en" and t_code != "en":
            s_to_en = cls.load_builtin_glossary(s_code, "en")
            en_to_t = cls.load_builtin_glossary("en", t_code)
            if s_to_en and en_to_t:
                pivoted: dict[str, str] = {}
                for s_term, en_term in s_to_en.items():
                    if en_term in en_to_t:
                        pivoted[s_term] = en_to_t[en_term]
                    else:
                        en_lower = en_term.lower()
                        for k, v in en_to_t.items():
                            if k.lower() == en_lower:
                                pivoted[s_term] = v
                                break
                if pivoted:
                    cls._builtin_cache[cache_key] = pivoted
                    return pivoted.copy()

        cls._builtin_cache[cache_key] = {}
        return {}

    @classmethod
    def parse_custom_glossary(cls, custom: str | Mapping[str, str] | None) -> dict[str, str]:
        """Parse user custom glossary from a dictionary or delimited string."""
        if not custom:
            return {}

        if isinstance(custom, Mapping):
            return {str(k).strip(): str(v).strip() for k, v in custom.items() if str(k).strip()}

        if isinstance(custom, str):
            custom_str = custom.strip()
            if not custom_str:
                return {}
            if custom_str.startswith("{") and custom_str.endswith("}"):
                try:
                    data = json.loads(custom_str)
                    if isinstance(data, dict):
                        return {str(k).strip(): str(v).strip() for k, v in data.items() if str(k).strip()}
                except Exception:
                    pass

            result: dict[str, str] = {}
            for line in custom_str.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    parts = line.split("=", 1)
                    k, v = parts[0].strip(), parts[1].strip()
                    if k and v:
                        result[k] = v
                elif ":" in line:
                    parts = line.split(":", 1)
                    k, v = parts[0].strip(), parts[1].strip()
                    if k and v:
                        result[k] = v
            return result

        return {}

    @classmethod
    def get_effective_glossary(
        cls,
        source_lang: str = "en",
        target_lang: str = "vi",
        custom_glossary: str | Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Get unified glossary where user custom terms take precedence over built-in terms."""
        terms = cls.load_builtin_glossary(source_lang, target_lang).copy()
        custom_terms = cls.parse_custom_glossary(custom_glossary)
        if custom_terms:
            # Case-insensitive override: remove built-in terms matching custom terms
            custom_lower = {k.lower() for k in custom_terms}
            terms = {k: v for k, v in terms.items() if k.lower() not in custom_lower}
            terms.update(custom_terms)
        return terms

    _term_regex_cache: dict[tuple[str, bool], re.Pattern] = {}

    @classmethod
    def _get_term_pattern(cls, term: str, is_cjk: bool) -> re.Pattern:
        key = (term, is_cjk)
        pat = cls._term_regex_cache.get(key)
        if pat is None:
            if is_cjk:
                pat = re.compile(re.escape(term))
            else:
                pat = re.compile(
                    rf"(?<![\w\u00C0-\u024F\u1EA0-\u1EF9]){re.escape(term)}(?![\w\u00C0-\u024F\u1EA0-\u1EF9])",
                    re.IGNORECASE,
                )
            if len(cls._term_regex_cache) > 4096:
                cls._term_regex_cache.clear()
            cls._term_regex_cache[key] = pat
        return pat

    @classmethod
    def apply_glossary(
        cls,
        text: str,
        source_lang: str = "en",
        target_lang: str = "vi",
        custom_glossary: str | Mapping[str, str] | None = None,
    ) -> str:
        """Apply terminology substitutions to text while strictly preserving formulas and tags."""
        if not text:
            return text

        glossary = cls.get_effective_glossary(source_lang, target_lang, custom_glossary)
        if not glossary:
            return text

        sorted_terms = sorted(glossary.keys(), key=len, reverse=True)
        parts = _FORMULA_OR_TAG_PATTERN.split(text)
        new_parts = []

        for part in parts:
            if not part:
                continue
            if _FORMULA_OR_TAG_PATTERN.fullmatch(part):
                new_parts.append(part)
                continue

            processed_part = part
            part_lower = processed_part.lower()
            for term in sorted_terms:
                if not term.strip():
                    continue
                # Fast Boyer-Moore substring pre-filter in C: skips non-matching terms instantly
                if term.lower() not in part_lower:
                    continue

                replacement = glossary[term]
                is_cjk = any("\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff" or "\uac00" <= c <= "\ud7af" for c in term)
                pattern = cls._get_term_pattern(term, is_cjk)

                if not pattern.search(processed_part):
                    continue

                def _replace_match(m: re.Match) -> str:
                    matched_str = m.group(0)
                    if matched_str and matched_str[0].isupper() and len(replacement) > 1:
                        return replacement[0].upper() + replacement[1:]
                    elif matched_str.isupper() and len(matched_str) > 1:
                        return replacement.upper()
                    return replacement

                processed_part = pattern.sub(_replace_match, processed_part)
                part_lower = processed_part.lower()

            new_parts.append(processed_part)

        return "".join(new_parts)

    # Source-anchored MT polysemy corrections for mathematical/scientific terms
    # Only triggered when the source text actually contains the specific source domain term.
    _MT_POLYSEMY_HEALING_VI_EN: tuple[tuple[str, re.Pattern, str], ...] = (
        ("trung bình điều hòa", re.compile(r"\bair[- ]conditioning average\b", re.IGNORECASE), "harmonic mean"),
        ("nghiệm đúng với mọi", re.compile(r"\b(?:the )?experience is true for everyone\b", re.IGNORECASE), "holds for all"),
        ("nghiệm đúng với", re.compile(r"\b(?:correct experience with|with all true solutions)\b", re.IGNORECASE), "holds for"),
        ("nghiệm kép", re.compile(r"\bdouble (?:test|solution)\b", re.IGNORECASE), "double root"),
        ("nghiệm", re.compile(r"\b(?:experience|test)\b", re.IGNORECASE), "root"),
        ("tính chât", re.compile(r"\b(?:quality|tính chât)\b", re.IGNORECASE), "properties"),
        ("logarith", re.compile(r"\blogarith\b", re.IGNORECASE), "logarithm"),
        ("chỉnh hợp", re.compile(r"\b(?:convolutions?|alignments?|concordances?|convolutional concordances?)\b", re.IGNORECASE), "arrangements"),
        ("tổ hợp", re.compile(r"\bconvolutional combinations?\b", re.IGNORECASE), "combinations"),
        ("cấp số nhân lùi vô hạn", re.compile(r"\b(?:(?:the )?exponential progression goes back infinitely|infinite backward multiplier)\b", re.IGNORECASE), "infinite geometric progression"),
        ("cấp số nhân", re.compile(r"\b(?:exponential progressions?|exponential)\b", re.IGNORECASE), "geometric progression"),
        ("tâm sai", re.compile(r"\b(?:the )?wrong center\b", re.IGNORECASE), "eccentricity"),
        ("tham số tiêu", re.compile(r"\btarget parameters?\b", re.IGNORECASE), "focal parameter"),
        ("cosin chỉ phương", re.compile(r"\b(?:the )?cosine indicates the direction\b", re.IGNORECASE), "direction cosines"),
        ("hệ số pháp dạng", re.compile(r"\bformat coefficients?\b", re.IGNORECASE), "normalizing factor"),
        ("tiết diện", re.compile(r"\bsecretions?\b", re.IGNORECASE), "cross-section"),
        ("tiết", re.compile(r"\bsecretions?\b", re.IGNORECASE), "cross-sections"),
        ("trong đó", re.compile(r"\bin measuring buzzing\b", re.IGNORECASE), "where"),
        ("trong đo", re.compile(r"\bin measuring buzzing\b", re.IGNORECASE), "where"),
        ("k là số loại", re.compile(r"\bk is the number of types\b", re.IGNORECASE), "k: number of types"),
        ("hàm lồi", re.compile(r"\bconvex jaw\b", re.IGNORECASE), "convex function"),
        ("viên phân", re.compile(r"\bfecal pellets\b", re.IGNORECASE), "circular segment"),
        ("quạt tròn", re.compile(r"\bround fan\b", re.IGNORECASE), "circular sector"),
        ("tâm đẳng phương", re.compile(r"\bisometric mind\b", re.IGNORECASE), "radical center"),
        ("trục đẳng phương", re.compile(r"\bisometric axis\b", re.IGNORECASE), "radical axis"),
        ("công bội", re.compile(r"\bcontribution\b", re.IGNORECASE), "common ratio"),
        ("công sai", re.compile(r"\bjustice\b", re.IGNORECASE), "common difference"),
        ("tiệm cận", re.compile(r"\b(?:nearsight|shops?)\b", re.IGNORECASE), "asymptote"),
        ("tiện cận", re.compile(r"\bnearsight\b", re.IGNORECASE), "asymptote"),
        ("khai triển", re.compile(r"\bdevelopment\b", re.IGNORECASE), "expansion"),
        ("khối tròn xoay", re.compile(r"\bcircular block\b", re.IGNORECASE), "solid of revolution"),
    )

    _MT_POLYSEMY_HEALING_VI_RU: tuple[tuple[str, re.Pattern, str], ...] = (
        ("lũy thừa", re.compile(r"\bв силу\b", re.IGNORECASE), "в степени"),
        ("cơ số", re.compile(r"\b(?:система счисления|базовый номер|по основанию)\b", re.IGNORECASE), "основание"),
        ("có vô số nghiệm", re.compile(r"\bсуществует бесчисленное множество решений\b", re.IGNORECASE), "бесконечно много решений"),
        ("vô số nghiệm", re.compile(r"\bбесчисленное множество решений\b", re.IGNORECASE), "бесконечно много решений"),
        ("nghiệm đúng với mọi", re.compile(r"\b(?:опыт верен для всех|верно для всех опытов)\b", re.IGNORECASE), "верно при всех"),
        ("nghiệm đúng với", re.compile(r"\b(?:правильный опыт с|со всеми верными решениями|опыт верен с)\b", re.IGNORECASE), "верно при"),
        ("vô nghiệm", re.compile(r"\b(?:неэффективно|бесполезно)\b", re.IGNORECASE), "нет решений"),
        ("đơn vị ảo", re.compile(r"\bвиртуальный блок\b", re.IGNORECASE), "мнимая единица"),
        ("đoạn thẳng", re.compile(r"\bсегмент линии\b", re.IGNORECASE), "отрезок"),
        ("trong đó", re.compile(r"\bв этом\b", re.IGNORECASE), "где"),
        ("trong đo", re.compile(r"\bв измерении жужжания\b", re.IGNORECASE), "где"),
    )

    @classmethod
    def normalize_translation(
        cls,
        source_text: str,
        translated_text: str,
        source_lang: str = "auto",
        target_lang: str = "en",
        custom_glossary: str | Mapping[str, str] | None = None,
        masked_source_text: str | None = None,
    ) -> str:
        """Heal untranslated terms and MT terminology drifts using structural layout anchors from source text."""
        if not translated_text:
            return translated_text

        result = translated_text
        glossary = cls.get_effective_glossary(source_lang, target_lang, custom_glossary)
        if not glossary:
            return result

        source_lower = source_text.lower()
        uses_xml_tags = bool(re.search(r"<b\d+></b\d+>", result))
        anchor_src = re.sub(r"<b(\d+)></b\1>", r"⟦LL_FORMULA_\1⟧", masked_source_text or source_text)
        result_opaque = re.sub(r"<b(\d+)></b\1>", r"⟦LL_FORMULA_\1⟧", result)

        # 0. Exact standalone phrase match (ignoring outer whitespace, section/list prefixes like '3. ' or 'a) ',
        # surrounding formula placeholders ⟦LL_FORMULA_k⟧, and trailing punctuation or index page references like ' · 29')
        for cand_src in (anchor_src, source_text) if anchor_src != source_text else (source_text,):
            m_outer = re.match(
                r"^(\s*(?:(?:\d+|[a-zA-Z]|[IVXLCDM]+)[\.\)]\s+|[•\-\*]\s+|[\(\[\{\.\,\:\;\—\–\-]\s*|⟦LL_FORMULA_\d+⟧\s*)*)([^\s⟦⟧].*?[^\s⟦⟧]|[^\s⟦⟧])(\s*(?:⟦LL_FORMULA_\d+⟧\s*|[·•]\s*\d+(?:\s*,\s*\d+)*|[\:\.\,;!\?\)\]\}])*\s*)$",
                cand_src,
                re.DOTALL,
            )
            if m_outer:
                lead_punct, core_src, trail_punct = m_outer.group(1), m_outer.group(2), m_outer.group(3)
                if "⟦LL_FORMULA_" not in core_src:
                    src_formulas = re.findall(r"⟦LL_FORMULA_\d+⟧", cand_src)
                    res_formulas = re.findall(r"⟦LL_FORMULA_\d+⟧", result_opaque)
                    if not src_formulas or src_formulas == res_formulas:
                        core_lower = core_src.lower()
                        for s_term, t_term in glossary.items():
                            if s_term.lower() == core_lower:
                                if core_src[0].isupper() and len(t_term) > 1:
                                    t_rep = t_term[0].upper() + t_term[1:]
                                elif core_src.isupper() and len(core_src) > 1:
                                    t_rep = t_term.upper()
                                else:
                                    t_rep = t_term
                                lead_clean = re.sub(r"([(\[{])\s+$", r"\1", lead_punct.lstrip())
                                trail_clean = re.sub(r"\s+([)\]}.,:;!?])", r"\1", trail_punct.rstrip())
                                if trail_clean.startswith("⟦LL_FORMULA_"):
                                    trail_clean = " " + trail_clean
                                out_str = f"{lead_clean}{t_rep}{trail_clean}"
                                if uses_xml_tags:
                                    out_str = re.sub(r"⟦LL_FORMULA_(\d+)⟧", r"<b\1></b\1>", out_str)
                                return out_str

        # 0b. Source-anchored polysemy healing for VI -> EN / VI -> RU mathematical terms
        tgt_norm = (target_lang or "en").lower().strip()
        if tgt_norm.startswith("en"):
            for src_trigger, mt_pat, fix_str in cls._MT_POLYSEMY_HEALING_VI_EN:
                if src_trigger in source_lower and mt_pat.search(result):
                    def _heal_poly(m: re.Match, _fix: str = fix_str) -> str:
                        s = m.group(0)
                        return _fix[0].upper() + _fix[1:] if s and s[0].isupper() else _fix
                    result = mt_pat.sub(_heal_poly, result)
        elif tgt_norm.startswith("ru"):
            for src_trigger, mt_pat, fix_str in cls._MT_POLYSEMY_HEALING_VI_RU:
                if src_trigger in source_lower and mt_pat.search(result):
                    def _heal_poly_ru(m: re.Match, _fix: str = fix_str) -> str:
                        s = m.group(0)
                        return _fix[0].upper() + _fix[1:] if s and s[0].isupper() else _fix
                    result = mt_pat.sub(_heal_poly_ru, result)

        result_lower = result.lower()

        # Scan for glossary terms that appear in source_text (ordered by term length descending)
        for s_term, t_term in sorted(glossary.items(), key=lambda x: len(x[0]), reverse=True):
            if not s_term.strip() or len(s_term) < 2:
                continue

            # Fast Boyer-Moore substring pre-filter in C: skips 99.9% of non-matching terms instantly
            s_lower = s_term.lower()
            if s_lower not in source_lower and s_lower not in result_lower:
                continue

            is_cjk_src = any("\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff" or "\uac00" <= c <= "\ud7af" for c in s_term)
            p_src = cls._get_term_pattern(s_term, is_cjk_src)

            m_src = p_src.search(anchor_src) or p_src.search(source_text)
            if not m_src:
                continue

            # If target term is already correctly present in translated text, no healing needed
            if t_term.lower() in result_lower:
                is_cjk_tgt = any("\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff" or "\uac00" <= c <= "\ud7af" for c in t_term)
                p_tgt = cls._get_term_pattern(t_term, is_cjk_tgt)
                if p_tgt.search(result):
                    continue

            # 1. Direct healing: if untranslated s_term exists in translated text
            if p_src.search(result):
                def _rep(m: re.Match) -> str:
                    return t_term[0].upper() + t_term[1:] if m.group(0).istitle() else t_term
                result = p_src.sub(_rep, result)
                result_lower = result.lower()
                continue

            # 2. Structural layout anchor alignment: find shared pre/suf tokens (indices, dot leaders, tags, formulas)
            active_src = anchor_src if p_src.search(anchor_src) else source_text
            m_src_active = p_src.search(active_src)
            if not m_src_active:
                continue
            m_pre = re.search(r"(\d+[\.\)]\s*|[•\-\*]\s*|\S+\s*)$", active_src[:m_src_active.start()])
            pre_anchor = m_pre.group(0) if m_pre else ""

            m_suf = re.search(r"^(\s*[\.\:\-_–—…]{2,}\s*\d+|\s*[\.\:\-_–—…]+|\s*⟦LL_[^⟧]+⟧)", active_src[m_src_active.end():])
            suf_anchor = m_suf.group(0) if m_suf else ""

            if pre_anchor and suf_anchor:
                anchor_pat = re.compile(
                    rf"({re.escape(pre_anchor.strip())}\s+)(.*?)(\s*{re.escape(suf_anchor.strip())})",
                    re.DOTALL,
                )
                if anchor_pat.search(result):
                    result = anchor_pat.sub(rf"\g<1>{t_term}\g<3>", result)
                    result_lower = result.lower()
                    continue

        return result
