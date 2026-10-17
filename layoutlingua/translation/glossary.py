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
    def load_builtin_glossary(cls, source_lang: str = "en", target_lang: str = "vi") -> dict[str, str]:
        """Load built-in academic and STEM glossary for the given language pair."""
        s_lang = (source_lang or "en").lower().strip()
        t_lang = (target_lang or "vi").lower().strip()
        lang_map = {
            "vietnamese": "vi",
            "chinese": "zh",
            "zh-cn": "zh",
            "zh-tw": "zh",
            "japanese": "ja",
            "german": "de",
            "french": "fr",
            "spanish": "es",
            "english": "en",
        }
        s_code = lang_map.get(s_lang, s_lang)
        t_code = lang_map.get(t_lang, t_lang)
        cache_key = f"{s_code}_{t_code}"

        if cache_key in cls._builtin_cache:
            return cls._builtin_cache[cache_key].copy()

        glossary_file = _RESOURCE_DIR / f"academic_math_{s_code}_{t_code}.json"
        if not glossary_file.exists():
            cls._builtin_cache[cache_key] = {}
            return {}

        try:
            with open(glossary_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                terms = data.get("terms", {})
                cls._builtin_cache[cache_key] = terms
                return terms.copy()
        except Exception:
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
        terms = cls.load_builtin_glossary(source_lang, target_lang)
        custom_terms = cls.parse_custom_glossary(custom_glossary)
        terms.update(custom_terms)
        return terms

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
            for term in sorted_terms:
                if not term.strip():
                    continue
                replacement = glossary[term]
                pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
                if not pattern.search(processed_part):
                    continue

                def _replace_match(m: re.Match) -> str:
                    matched_str = m.group(0)
                    if matched_str.istitle() and len(replacement) > 1:
                        return replacement[0].upper() + replacement[1:]
                    elif matched_str.isupper() and len(matched_str) > 1:
                        return replacement.upper()
                    return replacement

                processed_part = pattern.sub(_replace_match, processed_part)

            new_parts.append(processed_part)

        return "".join(new_parts)
