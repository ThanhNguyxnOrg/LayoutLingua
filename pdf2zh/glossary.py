"""Document-Level Terminology and Global Glossary Manager for LayoutLingua.

Ensures consistent technical translation across all document pages by enforcing
user-provided glossaries and automatic acronym/named-entity extraction.
Addresses pain points from Immersive Translate #3573, PolyglotPDF, and BabelDOC.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Pattern to discover technical acronyms and capitalized terminology
ACRONYM_PATTERN = re.compile(r"\b[A-Z]{2,8}(?:-[A-Z0-9]+)?\b")


@dataclass
class GlossaryEntry:
    """A single glossary terminology mapping."""
    term: str
    translation: str
    case_sensitive: bool = False


class GlossaryManager:
    """Manages document-level terminology memory and custom glossary substitution."""

    def __init__(self, initial_glossary: Optional[Dict[str, str]] = None):
        self.entries: Dict[str, GlossaryEntry] = {}
        if initial_glossary:
            for term, trans in initial_glossary.items():
                self.add_term(term, trans)

    def add_term(self, term: str, translation: str, case_sensitive: bool = False) -> None:
        """Add or update a glossary mapping."""
        key = term if case_sensitive else term.lower()
        self.entries[key] = GlossaryEntry(
            term=term,
            translation=translation,
            case_sensitive=case_sensitive,
        )

    def load_from_file(self, file_path: str | Path) -> int:
        """Load glossary mappings from a JSON or CSV file.

        Returns:
            Number of terms loaded.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Glossary file not found: {path}")

        count = 0
        if path.suffix.lower() == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    self.add_term(str(k), str(v))
                    count += 1
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "term" in item and "translation" in item:
                        self.add_term(item["term"], item["translation"], item.get("case_sensitive", False))
                        count += 1
        elif path.suffix.lower() in (".csv", ".tsv"):
            delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    if len(row) >= 2 and row[0].strip():
                        self.add_term(row[0].strip(), row[1].strip())
                        count += 1

        logger.info("Loaded %d glossary entries from %s", count, path)
        return count

    def pre_mask_terms(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Protect glossary terms before sending to translation service.

        Replaces matched terms with temporary token markers <gN></gN>.
        Returns:
            (masked_text, token_to_translation_map)
        """
        if not self.entries or not text:
            return text, {}

        # Sort terms by descending length to match longest phrases first
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: len(e.term),
            reverse=True,
        )

        masked_text = text
        token_map: Dict[str, str] = {}
        idx = 0

        for entry in sorted_entries:
            pattern = re.compile(
                r"\b" + re.escape(entry.term) + r"\b",
                0 if entry.case_sensitive else re.IGNORECASE,
            )
            matches = list(pattern.finditer(masked_text))
            if matches:
                token = f"<g{idx}>"
                token_map[token] = entry.translation
                masked_text = pattern.sub(token, masked_text)
                idx += 1

        return masked_text, token_map

    def post_restore_terms(self, text: str, token_map: Dict[str, str]) -> str:
        """Restore protected glossary tokens with their enforced translations."""
        if not token_map or not text:
            return text

        restored = text
        for token, target_translation in token_map.items():
            # Match token with possible MT spaces: e.g. <g0>, < g0 >, <g 0>
            tid = re.search(r"\d+", token).group(0)
            token_pattern = re.compile(rf"<\s*g\s*{tid}\s*>", re.IGNORECASE)
            restored = token_pattern.sub(target_translation, restored)

        return restored

    @staticmethod
    def extract_document_acronyms(text: str) -> Set[str]:
        """Extract all technical acronyms (e.g. CNN, LSTM, BLEU) from raw document text."""
        return set(ACRONYM_PATTERN.findall(text))
