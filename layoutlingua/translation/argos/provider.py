"""Concrete adapter integrating Argos Translate offline engine with BaseTranslationProvider."""

from __future__ import annotations

from layoutlingua.translation.argos.manager import ArgosModelManager
from layoutlingua.translation.errors import ProviderUnavailableError
from layoutlingua.translation.models import (
    BatchTranslationRequest,
    BatchTranslationResult,
    ProviderCapabilities,
)
from layoutlingua.translation.provider import BaseTranslationProvider


class ArgosTranslationProvider(BaseTranslationProvider):
    """Zero-key, 100% offline neural translation provider powered by Argos Translate & CTranslate2."""

    def __init__(self, manager: ArgosModelManager | None = None) -> None:
        self.manager = manager or ArgosModelManager()
        self._capabilities = ProviderCapabilities(
            supports_structured_json=False,
            requires_data_use_consent=False,
            tier="offline",
            policy_version="1.0",
            max_batch_segments=50,
            max_batch_chars=8000,
            requests_per_minute=10000.0,
        )

    @property
    def name(self) -> str:
        return "argos"

    @property
    def model(self) -> str:
        return "ctranslate2-local"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        """Translate a batch of text segments through local direct or pivot model routes."""
        # 1. Guard: check if argostranslate library is installed
        if not self.manager.is_runtime_available():
            raise ProviderUnavailableError(
                "Argos Translate runtime is not installed in the current environment. "
                "To enable zero-key offline translation, please install the optional runtime: "
                "pip install argostranslate"
            )

        # 2. Guard: resolve directional route (normalize 'auto' to 'en' if not pre-resolved)
        src_lang = request.source_language if (request.source_language and request.source_language != "auto") else "en"
        route = self.manager.plan_route(src_lang, request.target_language)
        if route is None:
            raise ProviderUnavailableError(
                f"No offline translation route available from '{src_lang}' to '{request.target_language}'. "
                "The directional model package does not exist in the Argos catalog."
            )

        # 3. Guard: check if all required route packages are installed locally
        if not route.is_fully_installed:
            missing_pkgs = [s.package_name for s in route.steps if not s.is_installed]
            raise ProviderUnavailableError(
                f"Translation route ({route.describe()}) requires uninstalled offline packages: {missing_pkgs}. "
                f"Please download and install these models first via ArgosModelManager."
            )

        # 4. Perform sequential execution across hops (e.g. ja -> en -> vi)
        import argostranslate.translate  # type: ignore
        from layoutlingua.translation.google_rpc import _sanitize_translated_tokens

        # Pre-resolve translation handles for each step
        translators = [
            argostranslate.translate.get_translation_from_codes(step.from_code, step.to_code)
            for step in route.steps
        ]

        translations: dict[str, str] = {}
        for seg in request.segments:
            current_text = seg.masked_text
            if not current_text or not current_text.strip():
                translations[seg.segment_id] = current_text
                continue

            for translator in translators:
                if translator is None:
                    raise ProviderUnavailableError("Underlying Argos CTranslate2 translation handle was None.")
                current_text = translator.translate(current_text)

            translations[seg.segment_id] = _sanitize_translated_tokens(current_text)

        return BatchTranslationResult(translations=translations)

