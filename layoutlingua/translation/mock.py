"""Deterministic, offline, zero-network mock translation provider.

Implements BaseTranslationProvider for Slice 3 resilience and batching,
while retaining backward compatibility for DocumentIR and single-segment translation.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from layoutlingua.core.ir import DocumentIR, GlyphSpan, PageIR, TextBlock
from layoutlingua.translation.errors import RateLimitError
from layoutlingua.translation.models import (
    BatchTranslationRequest,
    BatchTranslationResult,
    ProviderCapabilities,
)
from layoutlingua.translation.provider import BaseTranslationProvider

_FORMULA_TAG_PATTERN = re.compile(r"(<b\d+></b\d+>)")
_OPAQUE_FORMULA_PATTERN = re.compile(r"(⟦LL_FORMULA_\d+⟧)")


@dataclass(slots=True)
class TranslationRecord:
    """Audit record maintaining the mapping between source segment ID, source text, and translation."""

    segment_id: str
    source_text: str
    translated_text: str
    target_lang: str


class MockTranslationProvider(BaseTranslationProvider):
    """Deterministic offline translation provider for contracts and verification.

    Features:
    - Never makes network connections.
    - Strictly deterministic output.
    - Preserves formula tokens (<b0></b0> and ⟦LL_FORMULA_0000⟧) verbatim.
    - Configurable failure simulation (rate limits, auth errors, token corruption, retries).
    """

    def __init__(
        self,
        prefix_tag: bool = True,
        capabilities: ProviderCapabilities | None = None,
        simulate_error: Exception | None = None,
        fail_first_n_calls: int = 0,
        fail_with_error: Exception | None = None,
        corrupt_tokens: bool = False,
        reorder_segments: bool = False,
    ) -> None:
        self.prefix_tag = prefix_tag
        self._capabilities = capabilities or ProviderCapabilities(
            supports_structured_json=True,
            requires_data_use_consent=False,
            tier="offline",
            policy_version="1.0",
            max_batch_segments=10,
            max_batch_chars=2000,
            requests_per_minute=600.0,
        )
        self.simulate_error = simulate_error
        self.fail_first_n_calls = fail_first_n_calls
        self.fail_with_error = fail_with_error or RateLimitError("Mock 429", retry_after=0.01)
        self.corrupt_tokens = corrupt_tokens
        self.reorder_segments = reorder_segments

        self.call_count = 0
        self.records: list[TranslationRecord] = []

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return "deterministic-v1"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        """Translate a batch of TextSegments for BaseTranslationProvider interface."""
        self.call_count += 1

        if self.simulate_error:
            raise self.simulate_error

        if self.call_count <= self.fail_first_n_calls:
            raise self.fail_with_error

        translations: dict[str, str] = {}
        for seg in request.segments:
            translated = self.translate_segment(
                segment_id=seg.segment_id,
                text=seg.masked_text,
                target_lang=request.target_language,
            )
            if self.corrupt_tokens:
                # Intentionally remove formula tokens to simulate broken LLM output
                translated = re.sub(r"⟦LL_FORMULA_\d+⟧", "", translated)
                translated = re.sub(r"<b\d+></b\d+>", "", translated)

            translations[seg.segment_id] = translated

        if self.reorder_segments:
            # Reverse order of dictionary items to test that coordinator reassembles by ID
            reversed_translations = {k: translations[k] for k in reversed(list(translations.keys()))}
            return BatchTranslationResult(translations=reversed_translations)

        return BatchTranslationResult(translations=translations)

    def translate_segment(self, segment_id: str, text: str, target_lang: str) -> str:
        """Deterministically translate a single text segment preserving formula tags."""
        if not text or not text.strip():
            self.records.append(TranslationRecord(segment_id, text, text, target_lang))
            return text

        # Split string around both <bN></bN> and ⟦LL_FORMULA_N⟧
        tokens = re.split(r"(<b\d+></b\d+>|⟦LL_FORMULA_\d+⟧)", text)
        translated_parts: list[str] = []

        for part in tokens:
            if _FORMULA_TAG_PATTERN.fullmatch(part) or _OPAQUE_FORMULA_PATTERN.fullmatch(part):
                # Formula placeholder token: preserve exactly
                translated_parts.append(part)
            else:
                # Normal text: apply deterministic prefix/transformation
                stripped = part.strip()
                if not stripped:
                    translated_parts.append(part)
                else:
                    transformed = f"[{target_lang.upper()}] {stripped}" if self.prefix_tag else f"mock_{stripped}"
                    leading = part[: len(part) - len(part.lstrip())]
                    trailing = part[len(part.rstrip()) :]
                    translated_parts.append(f"{leading}{transformed}{trailing}")

        result = "".join(translated_parts)
        self.records.append(TranslationRecord(segment_id, text, result, target_lang))
        return result

    def translate_document(self, doc_ir: DocumentIR, target_lang: str) -> DocumentIR:
        """Produce a translated clone of DocumentIR with all geometry and IDs intact."""
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
