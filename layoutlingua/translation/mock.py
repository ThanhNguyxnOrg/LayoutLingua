"""Deterministic, offline, zero-network mock translation provider.

Guarantees 100% reproducible results for automated regression testing,
preserves formula token pairs (<bN></bN>), and maintains segment ID mappings.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from layoutlingua.core.ir import DocumentIR, GlyphSpan, PageIR, TextBlock

_FORMULA_TAG_PATTERN = re.compile(r"(<b\d+></b\d+>)")


@dataclass(slots=True)
class TranslationRecord:
    """Audit record maintaining the mapping between source segment ID, source text, and translation."""

    segment_id: str
    source_text: str
    translated_text: str
    target_lang: str


class MockTranslationProvider:
    """Deterministic offline translation provider for contracts and verification.

    Rules:
    - Never makes network connections.
    - Strictly deterministic: identical input string always produces identical output.
    - Preserves formula tokens (<b0></b0>, etc.) verbatim.
    - Preserves Unicode characters accurately.
    - Tracks translation records for verification of segment loss or reordering.
    """

    def __init__(self, prefix_tag: bool = True) -> None:
        self.prefix_tag = prefix_tag
        self.records: list[TranslationRecord] = []

    def translate_segment(self, segment_id: str, text: str, target_lang: str) -> str:
        """Deterministically translate a single text segment preserving formula tags."""
        if not text or not text.strip():
            self.records.append(TranslationRecord(segment_id, text, text, target_lang))
            return text

        # Split string around formula tags: e.g. "Let <b0></b0> be true" -> ["Let ", "<b0></b0>", " be true"]
        tokens = _FORMULA_TAG_PATTERN.split(text)
        translated_parts: list[str] = []

        for part in tokens:
            if _FORMULA_TAG_PATTERN.fullmatch(part):
                # Formula placeholder token: preserve exactly
                translated_parts.append(part)
            else:
                # Normal text: apply deterministic prefix/transformation
                stripped = part.strip()
                if not stripped:
                    translated_parts.append(part)
                else:
                    # Deterministic transformation: e.g. "[VI] Let" or mock translated token
                    transformed = f"[{target_lang.upper()}] {stripped}" if self.prefix_tag else f"mock_{stripped}"
                    # Preserve leading and trailing whitespace
                    leading = part[: len(part) - len(part.lstrip())]
                    trailing = part[len(part.rstrip()) :]
                    translated_parts.append(f"{leading}{transformed}{trailing}")

        result = "".join(translated_parts)
        self.records.append(TranslationRecord(segment_id, text, result, target_lang))
        return result

    def translate_document(self, doc_ir: DocumentIR, target_lang: str) -> DocumentIR:
        """Produce a translated clone of DocumentIR with all geometry and IDs intact."""
        # Deep clone to avoid mutating source IR
        cloned_doc = copy.deepcopy(doc_ir)

        for page in cloned_doc.pages:
            for block in page.blocks:
                for span in block.spans:
                    span.text = self.translate_segment(
                        segment_id=span.span_id,
                        text=span.text,
                        target_lang=target_lang,
                    )

        cloned_doc.metadata["translated_by"] = "MockTranslationProvider"
        cloned_doc.metadata["target_language"] = target_lang
        return cloned_doc
